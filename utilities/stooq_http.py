from __future__ import annotations

from collections.abc import Callable
import hashlib
import importlib
import importlib.util
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen
import sys

# Browser-like headers used by Stooq CSV endpoints.  They are intentionally kept
# cookie-free by default so the fetcher does not depend on a developer's personal
# browser session, but still looks like a normal navigation request when the
# urllib fallback is used.
STOOQ_BROWSER_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en-PL;q=0.8,en;q=0.7,en-US;q=0.6",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
}

_CURL_SESSION = None


def _debug_enabled() -> bool:
    value = os.getenv("STOOQ_HTTP_DEBUG", "")
    return value.lower() not in {"", "0", "false", "no", "off"}


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    query_pairs = parse_qs(parsed.query, keep_blank_values=True)
    redacted_pairs: list[tuple[str, str]] = []
    for name, values in query_pairs.items():
        for value in values:
            if name.lower() in {"apikey", "api_key", "key", "token"}:
                value = "***"
            redacted_pairs.append((name, value))
    redacted_query = urlencode(redacted_pairs)
    return urlunparse(parsed._replace(query=redacted_query))


def _text_kind(text: str) -> str:
    stripped = text.lstrip("\ufeff\r\n\t ")
    lowered = stripped[:500].lower()
    if not stripped:
        return "empty"
    if lowered.startswith(("date,open,high,low,close", "date;open;high;low;close")):
        return "csv-en"
    if lowered.startswith((
        "data,otwarcie,najwyzszy,najnizszy,zamkniecie",
        "data;otwarcie;najwyzszy;najnizszy;zamkniecie",
    )):
        return "csv-pl"
    if _looks_like_stooq_challenge(text):
        return "stooq-js-challenge"
    if lowered.startswith("<!doctype html") or lowered.startswith("<html"):
        return "html"
    return "text"


def _debug(message: str) -> None:
    if _debug_enabled():
        print(f"[stooq-http] {message}", file=sys.stderr)


def _browser_headers_for_url(url: str) -> dict[str, str]:
    headers = dict(STOOQ_BROWSER_HEADERS)
    parsed = urlparse(url)
    symbol = parse_qs(parsed.query).get("s", [""])[0]
    if parsed.netloc and symbol:
        referer_query = urlencode({"s": symbol})
        headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/q/d/?{referer_query}"
    return headers


def _curl_cffi_requests_module():
    if importlib.util.find_spec("curl_cffi") is None:
        return None
    if importlib.util.find_spec("curl_cffi.requests") is None:
        return None
    return importlib.import_module("curl_cffi.requests")


def _curl_session(requests):
    global _CURL_SESSION
    if _CURL_SESSION is None:
        _CURL_SESSION = requests.Session()
    return _CURL_SESSION


def _download_with_urllib(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> str:
    request_headers = headers or _browser_headers_for_url(url)
    _debug(f"urllib GET {_redact_url(url)} timeout={timeout}s headers={len(request_headers)}")
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
    _debug(f"urllib response kind={_text_kind(text)} bytes={len(text.encode('utf-8'))}")
    return text


def _download_with_curl(requests, url: str, timeout: int, headers: dict[str, str]) -> str:
    impersonate = os.getenv("STOOQ_CURL_IMPERSONATE", "chrome")
    _debug(
        f"curl_cffi GET {_redact_url(url)} timeout={timeout}s "
        f"impersonate={impersonate} headers={len(headers)}"
    )
    response = _curl_session(requests).get(
        url,
        headers=headers,
        impersonate=impersonate,
        timeout=timeout,
    )
    response.raise_for_status()
    text = response.content.decode(response.encoding or "utf-8", errors="replace")
    status = getattr(response, "status_code", "unknown")
    _debug(
        f"curl_cffi response status={status} "
        f"kind={_text_kind(text)} bytes={len(response.content)}"
    )
    return text


def _playwright_fallback_enabled() -> bool:
    value = os.getenv("STOOQ_PLAYWRIGHT_FALLBACK", "1")
    return value.lower() not in {"", "0", "false", "no", "off"}


def _playwright_sync_api_module():
    if importlib.util.find_spec("playwright") is None:
        return None
    if importlib.util.find_spec("playwright.sync_api") is None:
        return None
    return importlib.import_module("playwright.sync_api")


def _playwright_stealth_module():
    if importlib.util.find_spec("playwright_stealth") is None:
        return None
    return importlib.import_module("playwright_stealth")


def _apply_playwright_stealth(page, context) -> bool:
    stealth = _playwright_stealth_module()
    if stealth is None:
        _debug("playwright-stealth unavailable; continuing without stealth patches")
        return False

    if hasattr(stealth, "stealth_sync"):
        stealth.stealth_sync(page)
        _debug("playwright-stealth applied via stealth_sync(page)")
        return True

    if hasattr(stealth, "apply_stealth_sync"):
        try:
            stealth.apply_stealth_sync(context)
            _debug("playwright-stealth applied via apply_stealth_sync(context)")
            return True
        except TypeError:
            stealth.apply_stealth_sync(page)
            _debug("playwright-stealth applied via apply_stealth_sync(page)")
            return True

    stealth_class = getattr(stealth, "Stealth", None)
    if stealth_class is not None:
        stealth_instance = stealth_class()
        if hasattr(stealth_instance, "apply_stealth_sync"):
            try:
                stealth_instance.apply_stealth_sync(context)
                _debug("playwright-stealth applied via Stealth.apply_stealth_sync(context)")
                return True
            except TypeError:
                stealth_instance.apply_stealth_sync(page)
                _debug("playwright-stealth applied via Stealth.apply_stealth_sync(page)")
                return True

    _debug("playwright-stealth installed but no supported sync API found")
    return False


def _download_with_playwright(url: str, timeout: int) -> str:
    if not _playwright_fallback_enabled():
        raise RuntimeError("Playwright fallback disabled by STOOQ_PLAYWRIGHT_FALLBACK")
    sync_api = _playwright_sync_api_module()
    if sync_api is None:
        raise RuntimeError("Playwright fallback unavailable: playwright.sync_api not installed")

    timeout_ms = max(1000, timeout * 1000)
    _debug(f"playwright GET {_redact_url(url)} timeout={timeout}s headless=true")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                locale="pl-PL",
                user_agent=STOOQ_BROWSER_HEADERS["User-Agent"],
                extra_http_headers={"Accept-Language": STOOQ_BROWSER_HEADERS["Accept-Language"]},
            )
            page = context.new_page()
            _apply_playwright_stealth(page, context)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            text = ""
            for attempt in range(1, 11):
                try:
                    page.wait_for_load_state("networkidle", timeout=1500)
                except Exception:
                    pass
                try:
                    text = page.locator("body").inner_text(timeout=1500)
                except Exception:
                    text = page.content()
                _debug(f"playwright attempt {attempt}/10 kind={_text_kind(text)} chars={len(text)}")
                if text and not _looks_like_stooq_challenge(text):
                    return text
                page.wait_for_timeout(500)
            return text
        finally:
            browser.close()


def _download_with_playwright_after_challenge(url: str, timeout: int, text: str) -> str:
    if not _looks_like_stooq_challenge(text):
        return text
    if not _playwright_fallback_enabled():
        _debug("playwright fallback disabled; returning challenge page")
        return text
    try:
        fallback_text = _download_with_playwright(url, timeout)
    except Exception as exc:
        _debug(f"playwright fallback failed: {type(exc).__name__}: {exc}")
        return text
    if _looks_like_stooq_challenge(fallback_text):
        _debug("playwright fallback still returned Stooq JS challenge")
    return fallback_text


def _looks_like_stooq_challenge(text: str) -> bool:
    lowered = text.lower()
    return (
        "textencoder" in lowered
        and "while(1)" in lowered.replace(" ", "")
        and (
            "verify your browser" in lowered
            or "weryfikacji przeglądarki" in lowered
            or "wymaga javascript" in lowered
        )
    )


def _extract_js_number(name: str, text: str) -> int | None:
    match = re.search(rf"(?:const|let|var)\s+{re.escape(name)}\s*=\s*(\d+)", text)
    if not match:
        match = re.search(rf"[,;]\s*{re.escape(name)}\s*=\s*(\d+)", text)
    return int(match.group(1)) if match else None


def _extract_js_string(name: str, text: str) -> str | None:
    match = re.search(rf"(?:const|let|var)\s+{re.escape(name)}\s*=\s*(['\"])(.*?)\1", text)
    if not match:
        match = re.search(rf"[,;]\s*{re.escape(name)}\s*=\s*(['\"])(.*?)\1", text)
    return match.group(2) if match else None


def _pow_message(challenge: str, nonce: int, text: str) -> str:
    match = re.search(r"\.encode\(([^)]*)\)", text)
    expression = re.sub(r"\s+", "", match.group(1)) if match else "c+n"
    if expression in {"n+c", "`${n}${c}`"}:
        return f"{nonce}{challenge}"
    return f"{challenge}{nonce}"


def _solve_pow_nonce(challenge: str, difficulty: int, text: str) -> int:
    prefix = "0" * difficulty
    max_nonce = int(os.getenv("STOOQ_JS_CHALLENGE_MAX_NONCE", "10000000"))
    for nonce in range(max_nonce + 1):
        digest = hashlib.sha256(_pow_message(challenge, nonce, text).encode()).hexdigest()
        if digest.startswith(prefix):
            return nonce
    raise ValueError(f"Stooq JS challenge nonce not found before {max_nonce}")


def _cookie_names_from_challenge(text: str) -> list[str]:
    names = re.findall(r"document\.cookie\s*=\s*(?:`|['\"])\s*([A-Za-z0-9_.-]+)=", text)
    return list(dict.fromkeys(names or ["auth"]))


def _substitute_cookie_template(template: str, challenge: str, nonce: int) -> str:
    replacements = {
        "${c}": challenge,
        "${n}": str(nonce),
        "${c+n}": f"{challenge}{nonce}",
        "${c + n}": f"{challenge}{nonce}",
        "${n+c}": f"{nonce}{challenge}",
        "${n + c}": f"{nonce}{challenge}",
    }
    value = template
    for needle, replacement in replacements.items():
        value = value.replace(needle, replacement)
    return value


def _cookie_pairs_from_template(text: str, challenge: str, nonce: int) -> list[str]:
    pairs: list[str] = []
    for template in re.findall(r"document\.cookie\s*=\s*`([^`]+)`", text):
        cookie_pair = _substitute_cookie_template(template, challenge, nonce).split(";", 1)[0]
        if "=" in cookie_pair:
            pairs.append(cookie_pair.strip())
    for name, expression in re.findall(
        r"document\.cookie\s*=\s*['\"]([A-Za-z0-9_.-]+)=['\"]\s*\+\s*([^;\n]+)",
        text,
    ):
        cleaned = re.sub(r"\s+", "", expression)
        if cleaned.startswith("c+n"):
            pairs.append(f"{name}={challenge}{nonce}")
        elif cleaned.startswith("n+c"):
            pairs.append(f"{name}={nonce}{challenge}")
        elif cleaned.startswith("c"):
            pairs.append(f"{name}={challenge}")
        elif cleaned.startswith("n"):
            pairs.append(f"{name}={nonce}")
    return pairs


def _challenge_cookie_pairs(text: str) -> list[str]:
    challenge = _extract_js_string("c", text)
    difficulty = _extract_js_number("d", text)
    if not challenge or difficulty is None:
        return []

    nonce = _solve_pow_nonce(challenge, difficulty, text)
    digest = hashlib.sha256(_pow_message(challenge, nonce, text).encode()).hexdigest()
    pairs = _cookie_pairs_from_template(text, challenge, nonce)
    for name in _cookie_names_from_challenge(text):
        pairs.extend(
            [
                f"{name}={challenge}{nonce}",
                f"{name}={challenge}:{nonce}",
                f"{name}={challenge}_{nonce}",
                f"{name}={challenge}.{nonce}",
                f"{name}={challenge}-{nonce}",
                f"{name}={nonce}",
                f"{name}={digest}",
            ]
        )
    return list(dict.fromkeys(pairs))


def _download_after_challenge(
    base_headers: dict[str, str],
    challenge_text: str,
    downloader: Callable[[dict[str, str]], str],
) -> str:
    cookie_pairs = _challenge_cookie_pairs(challenge_text)
    _debug(f"JS challenge detected; retry cookie candidates={len(cookie_pairs)}")
    for index, cookie_pair in enumerate(cookie_pairs, start=1):
        headers = dict(base_headers)
        existing_cookie = headers.get("Cookie")
        headers["Cookie"] = f"{existing_cookie}; {cookie_pair}" if existing_cookie else cookie_pair
        cookie_name = cookie_pair.split("=", 1)[0]
        _debug(f"JS challenge retry {index}/{len(cookie_pairs)} cookie={cookie_name}=<redacted>")
        text = downloader(headers)
        _debug(f"JS challenge retry {index} result kind={_text_kind(text)}")
        if not _looks_like_stooq_challenge(text):
            return text
    _debug("JS challenge retries exhausted; returning original challenge page")
    return challenge_text


def download_stooq_text(url: str, timeout: int = 20) -> str:
    """Download Stooq text using browser impersonation and JS challenge retry.

    Stooq can return a JavaScript proof-of-work browser-verification page to
    Python's default TLS fingerprint.  curl_cffi's browser impersonation is the
    preferred path; when Stooq still returns its lightweight JS challenge, the
    downloader solves the SHA-256 nonce and retries with the generated auth
    cookie before handing the text to CSV parsing.
    """
    base_headers = _browser_headers_for_url(url)
    requests = _curl_cffi_requests_module()
    _debug(
        f"start url={_redact_url(url)} timeout={timeout}s "
        f"curl_cffi={'available' if requests is not None else 'unavailable'}"
    )
    curl_error: Exception | None = None
    if requests is not None:
        try:
            text = _download_with_curl(requests, url, timeout, base_headers)
            if _looks_like_stooq_challenge(text):
                text = _download_after_challenge(
                    base_headers,
                    text,
                    lambda headers: _download_with_curl(requests, url, timeout, headers),
                )
                return _download_with_playwright_after_challenge(url, timeout, text)
            return text
        except Exception as exc:
            curl_error = exc
            _debug(f"curl_cffi failed: {type(exc).__name__}: {exc}")

    if requests is None:
        _debug("curl_cffi unavailable; using urllib fallback")
    else:
        _debug("using urllib fallback after curl_cffi failure")

    try:
        text = _download_with_urllib(url, timeout, base_headers)
        if _looks_like_stooq_challenge(text):
            text = _download_after_challenge(
                base_headers,
                text,
                lambda headers: _download_with_urllib(url, timeout, headers),
            )
            return _download_with_playwright_after_challenge(url, timeout, text)
        return text
    except Exception as urllib_error:
        _debug(f"urllib failed: {type(urllib_error).__name__}: {urllib_error}")
        if curl_error is None:
            raise
        message = (
            f"Stooq download failed with curl_cffi ({curl_error}) "
            f"and urllib ({urllib_error})"
        )
        raise ValueError(message) from urllib_error
