from __future__ import annotations

import importlib
import importlib.util
import os
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

# Browser-like headers used by Stooq CSV endpoints.  They are intentionally kept
# cookie-free so the fetcher does not depend on a developer's personal browser
# session, but still looks like a normal navigation request when the urllib
# fallback is used.
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


def _download_with_urllib(url: str, timeout: int) -> str:
    request = Request(url, headers=_browser_headers_for_url(url))
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def download_stooq_text(url: str, timeout: int = 20) -> str:
    """Download Stooq text using browser TLS impersonation when available.

    Stooq can return a JavaScript browser-verification page to Python's default
    urllib TLS fingerprint.  curl_cffi's browser impersonation sends a real
    browser-like TLS/HTTP fingerprint, which is the fastest reliable path for the
    CSV API.  The urllib fallback keeps a complete browser header set for
    environments where curl_cffi is not installed yet.
    """
    requests = _curl_cffi_requests_module()
    if requests is None:
        return _download_with_urllib(url, timeout)

    curl_error: Exception | None = None
    try:
        impersonate = os.getenv("STOOQ_CURL_IMPERSONATE", "chrome")
        response = requests.get(
            url,
            headers=_browser_headers_for_url(url),
            impersonate=impersonate,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.content.decode(response.encoding or "utf-8", errors="replace")
    except Exception as exc:
        curl_error = exc

    try:
        return _download_with_urllib(url, timeout)
    except Exception as urllib_error:
        message = (
            f"Stooq download failed with curl_cffi ({curl_error}) "
            f"and urllib ({urllib_error})"
        )
        raise ValueError(message) from urllib_error
