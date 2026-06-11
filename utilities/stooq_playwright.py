from __future__ import annotations

from datetime import UTC, datetime, timedelta
import time
import os
import json
import threading
import warnings
import zipfile
from pathlib import Path

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright


_CAPTCHA_INSPECTOR_LOCK = threading.Lock()
_CAPTCHA_OCR_LOCK = threading.Lock()
_EASYOCR_READER = None
_EASYOCR_UNAVAILABLE = False


_POLISH_MONTHS = {
    "sty": "01", "lut": "02", "mar": "03", "kwi": "04", "maj": "05", "cze": "06",
    "lip": "07", "sie": "08", "wrz": "09", "paź": "10", "paz": "10", "lis": "11", "gru": "12",
}


STOOQ_BULK_HISTORY_URL = "https://stooq.com/db/h/"
STOOQ_WIG_BULK_LINK_SELECTOR = "#t4 a[href*='d_pl_txt']"
STOOQ_BULK_TXT_COLUMNS = ["<TICKER>", "<PER>", "<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>", "<VOL>", "<OPENINT>"]


def _is_stooq_bulk_history_url(url: str) -> bool:
    lowered = (url or "").lower().split("?", 1)[0].rstrip("/")
    return lowered in {"https://stooq.com/db/h", "https://stooq.pl/db/h"}


def _return_to_stooq_bulk_history_if_redirected(page, reason: str) -> bool:
    """Keep the flow anchored on https://stooq.com/db/h/ after ads/consent redirects."""
    current_url = page.url
    if _is_stooq_bulk_history_url(current_url):
        return False
    print(
        f"[stooq-bulk] page left bulk history URL after {reason}: {current_url}; "
        f"returning to {STOOQ_BULK_HISTORY_URL}",
        flush=True,
    )
    try:
        page.goto(STOOQ_BULK_HISTORY_URL, wait_until="domcontentloaded")
    except Exception:
        try:
            page.goto(STOOQ_BULK_HISTORY_URL)
        except Exception:
            pass
    return True


def _stooq_bulk_debug_dir() -> Path:
    out_dir = Path(os.getenv("STOCKHELPER_STOOQ_BULK_DEBUG_DIR", "debug/stooq_bulk"))
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _latest_existing_stooq_bulk_zip(download_dir: Path) -> Path | None:
    candidates = sorted(
        (path for path in download_dir.glob("*.zip") if path.is_file() and zipfile.is_zipfile(path)),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _fallback_existing_stooq_bulk_zip(download_dir: Path, reason: str) -> Path | None:
    fallback = _latest_existing_stooq_bulk_zip(download_dir)
    if fallback is None:
        return None
    print(
        f"[stooq-bulk] {reason}; using latest existing valid zip instead: {fallback}",
        flush=True,
    )
    return fallback


def _save_stooq_bulk_download_if_zip(download, download_dir: Path, source: str) -> Path | None:
    suggested = download.suggested_filename or "stooq_d_pl_txt.zip"
    path = download_dir / suggested
    download.save_as(str(path))
    if zipfile.is_zipfile(path):
        print(f"[stooq-bulk] zip download saved from {source}: {path}", flush=True)
        return path
    preview = ""
    try:
        preview = path.read_text(encoding="utf-8", errors="replace")[:300].replace("\n", " ")
    except Exception:
        pass
    print(
        f"[stooq-bulk] ignoring non-zip download from {source}: {path} "
        f"(suggested={suggested!r}, preview={preview!r})",
        flush=True,
    )
    try:
        path.unlink()
    except Exception:
        pass
    return None


def _capture_stooq_bulk_failure(page, reason: str) -> str:
    """Save one screenshot (+ HTML sidecar) for a failing bulk-download step."""
    safe_reason = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in reason)[:80] or "failure"
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_dir = _stooq_bulk_debug_dir()
    png_path = out_dir / f"bulk_{stamp}_{safe_reason}.png"
    html_path = out_dir / f"bulk_{stamp}_{safe_reason}.html"
    try:
        page.screenshot(path=str(png_path), full_page=True)
    except Exception:
        png_path = Path("")
    try:
        html_path.write_text(page.content(), encoding="utf-8")
    except Exception:
        pass
    if png_path:
        print(f"[stooq-bulk] failure screenshot saved: {png_path}", flush=True)
        return str(png_path)
    return ""


def _capture_stooq_bulk_attempt(page, symbol: str, label: str, attempt: int) -> str:
    """Save full-page screenshot and HTML for a captcha attempt state."""
    safe_symbol = (symbol or "wig_bulk").lower().replace(".", "_")
    safe_label = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in (label or "state"))[:60]
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_dir = _stooq_bulk_debug_dir()
    png_path = out_dir / f"{safe_symbol}_attempt{attempt}_{stamp}_{safe_label}.png"
    html_path = out_dir / f"{safe_symbol}_attempt{attempt}_{stamp}_{safe_label}.html"
    saved = ""
    try:
        page.screenshot(path=str(png_path), full_page=True, timeout=5000)
        saved = str(png_path)
    except Exception as exc:
        print(f"[stooq-bulk] attempt {attempt} screenshot failed ({safe_label}): {exc}", flush=True)
    try:
        html_path.write_text(page.content(), encoding="utf-8")
    except Exception:
        pass
    if saved:
        print(f"[stooq-bulk] attempt {attempt} screenshot saved: {saved}", flush=True)
    return saved


_STOOQ_BULK_CONSENT_ACCEPT_TEXTS = (
    "zgadzam się",
    "zgadzam sie",
    "akceptuję",
    "akceptuje",
    "i consent",
    "consent",
    "i agree",
    "agree",
    "accept all",
    "accept",
)
_STOOQ_BULK_CONSENT_MARKERS = (
    "stooq prosi o zgodę",
    "stooq prosi o zgode",
    "wykorzystanie twoich danych osobowych",
    "spersonalizowane reklamy",
)


def _stooq_bulk_contexts(page):
    try:
        return [page] + list(page.frames)
    except Exception:
        return [page]


def _stooq_bulk_page_has_link_or_consent(page) -> bool:
    try:
        for ctx in _stooq_bulk_contexts(page):
            try:
                if ctx.locator("a[href*='d_pl_txt'], #t4 a").count() > 0:
                    return True
            except Exception:
                pass
        text = (page.locator("body").inner_text(timeout=1000) or "").lower()
        return any(marker in text for marker in _STOOQ_BULK_CONSENT_MARKERS)
    except Exception:
        return False


def _stooq_bulk_consent_visible(page) -> bool:
    try:
        text = (page.locator("body").inner_text(timeout=1000) or "").lower()
        return any(marker in text for marker in _STOOQ_BULK_CONSENT_MARKERS)
    except Exception:
        return False


def _click_stooq_bulk_consent_candidate(ctx) -> bool:
    selectors = [
        '.fc-button.fc-cta-consent',
        '.fc-cta-consent',
        'button.fc-button.fc-cta-consent.fc-primary-button',
        'button:has-text("Zgadzam się")',
        'button:has-text("Zgadzam sie")',
        'button:has-text("Akceptuję")',
        'button:has-text("Akceptuje")',
        'button:has-text("Consent")',
        'button:has-text("I consent")',
        'button:has-text("Agree")',
        'button:has-text("I agree")',
        'button:has-text("Accept")',
        'button:has-text("Accept all")',
        '[role="button"]:has-text("Zgadzam się")',
        '[role="button"]:has-text("Zgadzam sie")',
        '[role="button"]:has-text("Akceptuję")',
        '[role="button"]:has-text("Akceptuje")',
        '[role="button"]:has-text("Accept")',
        '[aria-label="Zgadzam się"]',
        '[aria-label="Zgadzam sie"]',
        '[aria-label="I consent"]',
        '[aria-label="Consent"]',
    ]
    for selector in selectors:
        try:
            button = ctx.locator(selector).first
            if button.count() == 0:
                continue
            button.click(timeout=2500, force=True)
            print(f"[stooq-bulk] consent clicked ({selector}).", flush=True)
            return True
        except Exception:
            continue

    try:
        clicked = bool(ctx.evaluate(
            """(acceptTexts) => {
                const norm = (value) => (value || '').toLowerCase().replace(/\\s+/g, ' ').trim();
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const box = el.getBoundingClientRect();
                    return style && style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
                };
                const candidates = Array.from(document.querySelectorAll(
                    'button,[role="button"],a,input[type="button"],input[type="submit"],.fc-button,.fc-cta-consent'
                ));
                for (const el of candidates) {
                    if (!isVisible(el)) continue;
                    const label = norm(el.innerText || el.textContent || el.value || el.getAttribute('aria-label'));
                    if (acceptTexts.some((txt) => label.includes(txt))) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }""",
            list(_STOOQ_BULK_CONSENT_ACCEPT_TEXTS),
        ))
        if clicked:
            print("[stooq-bulk] consent clicked (DOM fallback).", flush=True)
        return clicked
    except Exception:
        return False


def _accept_stooq_bulk_consent_if_present(page) -> None:
    """Accept the Stooq consent manager using Playwright auto-waiting only."""
    try:
        page.wait_for_function("() => document.readyState !== 'loading'", timeout=10000)
    except Exception:
        pass
    try:
        page.wait_for_function(
            """() => {
                const text = (document.body && document.body.innerText || '').toLowerCase();
                return document.querySelector("a[href*='d_pl_txt'], #t4 a")
                    || text.includes('stooq prosi o zgod')
                    || text.includes('wykorzystanie twoich danych osobowych');
            }""",
            timeout=15000,
        )
    except Exception:
        pass

    for _attempt in range(3):
        clicked = False
        for ctx in _stooq_bulk_contexts(page):
            if _click_stooq_bulk_consent_candidate(ctx):
                clicked = True
                _return_to_stooq_bulk_history_if_redirected(page, "consent click")
                break
        if not clicked:
            break
        try:
            page.locator("a[href*='d_pl_txt'], #t4 a").first.wait_for(state="visible", timeout=10000)
            return
        except Exception:
            if not _stooq_bulk_consent_visible(page):
                return


def _clear_stooq_bulk_consent_manager(page, reason: str = "") -> None:
    """Repeatedly clear consent that can reappear after Stooq navigation/reload."""
    for round_idx in range(4):
        _accept_stooq_bulk_consent_if_present(page)
        _return_to_stooq_bulk_history_if_redirected(page, f"consent clear round {round_idx + 1}")
        try:
            page.wait_for_function(
                """() => {
                    const text = (document.body && document.body.innerText || '').toLowerCase();
                    const consentVisible = text.includes('stooq prosi o zgod')
                        || text.includes('wykorzystanie twoich danych osobowych')
                        || text.includes('spersonalizowane reklamy');
                    const bulkLink = document.querySelector("a[href*='d_pl_txt'], #t4 a");
                    const captcha = document.querySelector("#t11 img, tr#t11 img, img[src*='/q/l/s/i/']");
                    return bulkLink || captcha || !consentVisible;
                }""",
                timeout=10000,
            )
        except Exception:
            pass
        if not _stooq_bulk_consent_visible(page):
            return
        if round_idx == 0:
            suffix = f" ({reason})" if reason else ""
            print(f"[stooq-bulk] consent manager reappeared{suffix}; accepting again.", flush=True)
    if _stooq_bulk_consent_visible(page):
        _capture_stooq_bulk_failure(page, "consent_manager_still_visible")


def _trigger_exact_stooq_bulk_link(page, purpose: str) -> dict:
    """Invoke Stooq's exact d_pl_txt link in page JS so ad overlays cannot intercept the click."""
    _return_to_stooq_bulk_history_if_redirected(page, f"before exact d_pl_txt trigger for {purpose}")
    result = page.evaluate(
        """() => {
            const candidates = Array.from(document.querySelectorAll('#t4 a, a'));
            const link = candidates.find((anchor) => {
                const href = anchor.getAttribute('href') || '';
                const onclick = anchor.getAttribute('onclick') || '';
                const oncontext = anchor.getAttribute('oncontextmenu') || '';
                return href.includes('db/d/?b=d_pl_txt')
                    || href.includes('b=d_pl_txt')
                    || onclick.includes('d_pl_txt')
                    || oncontext.includes('d_pl_txt');
            });
            if (!link) {
                return {ok: false, reason: 'exact d_pl_txt anchor not found'};
            }
            const hrefAttr = link.getAttribute('href') || '';
            const absoluteHref = link.href || hrefAttr;
            const rowId = link.closest('tr') ? link.closest('tr').id : '';
            const text = (link.innerText || link.textContent || '').trim();
            if (typeof window.cpt_g === 'function') {
                const ret = window.cpt_g(absoluteHref, 1, 1);
                return {ok: true, via: 'cpt_g', href: absoluteHref, hrefAttr, rowId, text, returnValue: String(ret)};
            }
            link.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
            return {ok: true, via: 'dispatchEvent', href: absoluteHref, hrefAttr, rowId, text};
        }"""
    )
    if not result or not result.get("ok"):
        shot = _capture_stooq_bulk_failure(page, "exact_bulk_link_missing")
        raise ValueError(f"Could not invoke exact Stooq d_pl_txt link for {purpose}: {result}. Screenshot: {shot}")
    print(
        f"[stooq-bulk] invoked exact d_pl_txt link via {result.get('via')} "
        f"(purpose={purpose}, row={result.get('rowId')}, text={result.get('text')!r}, href={result.get('href')}).",
        flush=True,
    )
    return result


def _bulk_download_link(page):
    """Find the WIG d_pl_txt link, preferring the required #t4 table/row."""
    selectors = [
        STOOQ_WIG_BULK_LINK_SELECTOR,
        "#t4 a[href*='db/d/'][href*='b=d_pl_txt']",
        "#t4 a[onclick*='d_pl_txt']",
        "#t4 a[oncontextmenu*='d_pl_txt']",
        "a[href*='d_pl_txt']",
        "a[onclick*='d_pl_txt']",
    ]
    last_error = None
    try:
        contexts = [page] + list(page.frames)
    except Exception:
        contexts = [page]
    for consent_retry in range(4):
        for ctx in contexts:
            for selector in selectors:
                link = ctx.locator(selector).first
                try:
                    if link.count() == 0:
                        continue
                    link.wait_for(state="visible", timeout=20000)
                    href = (link.get_attribute("href") or "").lower()
                    onclick = (link.get_attribute("onclick") or "").lower()
                    oncontext = (link.get_attribute("oncontextmenu") or "").lower()
                    if "d_pl_txt" in href or "d_pl_txt" in onclick or "d_pl_txt" in oncontext:
                        return link
                except Exception as exc:
                    last_error = exc
                    continue
        if consent_retry < 3 and _stooq_bulk_consent_visible(page):
            print("[stooq-bulk] consent manager still visible while looking for bulk link; accepting again.", flush=True)
            _accept_stooq_bulk_consent_if_present(page)
            try:
                contexts = [page] + list(page.frames)
            except Exception:
                contexts = [page]
            continue
        break
    shot = _capture_stooq_bulk_failure(page, "bulk_link_missing")
    body_preview = ""
    try:
        body_preview = (page.locator("body").inner_text(timeout=2000) or "").strip().replace("\n", " ")[:500]
    except Exception:
        pass
    raise ValueError(
        "Could not find visible Stooq WIG bulk d_pl_txt link in #t4 "
        f"(selector={STOOQ_WIG_BULK_LINK_SELECTOR!r}, url={page.url}, screenshot={shot}, "
        f"body_preview={body_preview!r}, last_error={last_error})"
    )


def _click_bulk_link_for_optional_download(page, download_dir: Path, *, timeout: int, purpose: str = "download") -> Path | None:
    """Click the exact d_pl_txt bulk link and return a zip path only when download starts."""
    _return_to_stooq_bulk_history_if_redirected(page, f"before {purpose}")
    _clear_stooq_bulk_consent_manager(page, reason="before bulk link click")
    try:
        with page.expect_download(timeout=timeout) as download_info:
            _clear_stooq_bulk_consent_manager(page, reason="inside download wait")
            print(f"[stooq-bulk] clicking exact WIG d_pl_txt link ({purpose}).", flush=True)
            _trigger_exact_stooq_bulk_link(page, purpose)
        return _save_stooq_bulk_download_if_zip(download_info.value, download_dir, purpose)
    except PlaywrightTimeoutError:
        redirected = _return_to_stooq_bulk_history_if_redirected(page, f"{purpose} click")
        if redirected:
            _clear_stooq_bulk_consent_manager(page, reason="after redirect from bulk link click")
            return None
        if _stooq_bulk_consent_visible(page):
            _clear_stooq_bulk_consent_manager(page, reason="after download timeout")
            try:
                with page.expect_download(timeout=timeout) as download_info:
                    print(f"[stooq-bulk] clicking exact WIG d_pl_txt link ({purpose}, retry after consent).", flush=True)
                    _trigger_exact_stooq_bulk_link(page, f"{purpose}, retry after consent")
                return _save_stooq_bulk_download_if_zip(download_info.value, download_dir, f"{purpose}, retry after consent")
            except PlaywrightTimeoutError:
                return None
        return None


def _bulk_captcha_image(page):
    return page.locator("#t11 img, tr#t11 img, img[src*='/q/l/s/i/']").first


def _page_has_bulk_captcha(page) -> bool:
    try:
        img = _bulk_captcha_image(page)
        return img.count() > 0 and img.is_visible(timeout=500)
    except Exception:
        return False


def _bulk_authorization_success_visible(page) -> bool:
    try:
        body = page.locator("body").inner_text(timeout=1000).lower()
    except Exception:
        try:
            body = page.content().lower()
        except Exception:
            body = ""
    markers = (
        "authorization successful",
        "authorisation successful",
        "download file",
        "autoryzacja",
        "pobierz plik",
    )
    return any(marker in body for marker in markers)


def _click_authorized_bulk_download_link(page, download_dir: Path | None = None) -> bool | Path:
    selectors = (
        'a:has-text("Download file")',
        'a:has-text("Download file...")',
        'a:has-text("Pobierz plik")',
        'a[href*="/db/d/"][href*="d_pl_txt"]',
        'a[href*="b=d_pl_txt"]',
    )
    for selector in selectors:
        try:
            link = page.locator(selector).first
            if link.count() == 0 or not link.is_visible(timeout=500):
                continue
            print(f"[stooq-bulk] clicking authorized download link ({selector}).", flush=True)
            if download_dir is not None:
                try:
                    with page.expect_download(timeout=30000) as download_info:
                        link.click(timeout=2500, force=True)
                    zip_path = _save_stooq_bulk_download_if_zip(download_info.value, download_dir, "authorized download link")
                    if zip_path is not None:
                        return zip_path
                    return True
                except PlaywrightTimeoutError:
                    return True
            link.click(timeout=2500, force=True)
            return True
        except Exception:
            continue
    return False


def _request_new_bulk_captcha_code(page, symbol: str, attempt: int) -> bool:
    try:
        img = _bulk_captcha_image(page)
        old_src = img.get_attribute("src", timeout=1000) if img.count() > 0 else ""
    except Exception:
        old_src = ""
    for selector in ('a:has-text("Change code")', 'a:has-text("Zmień kod")', 'a:has-text("Zmien kod")', 'a[onclick*="cpt_o"]'):
        try:
            link = page.locator(selector).first
            if link.count() == 0:
                continue
            print(f"[stooq-bulk] captcha rejected/uncertain; clicking change-code link ({selector}).", flush=True)
            link.click(timeout=2000, force=True)
            if old_src:
                try:
                    page.wait_for_function(
                        "oldSrc => { const img = document.querySelector('#t11 img, tr#t11 img, img[src*=\'/q/l/s/i/\']'); return img && img.getAttribute('src') !== oldSrc; }",
                        arg=old_src,
                        timeout=2500,
                    )
                except Exception:
                    pass
            return True
        except Exception:
            continue
    try:
        page.evaluate("() => { if (typeof cpt_o === 'function') cpt_o(); }")
        print("[stooq-bulk] captcha rejected/uncertain; requested change-code via cpt_o().", flush=True)
        return True
    except Exception:
        return False


def _submit_bulk_captcha_form(page) -> bool:
    submit_targets = (
        ("Approve role", lambda: page.get_by_role("button", name="Approve").click(timeout=2500)),
        ("Approve input", lambda: page.locator('input#f13[type="submit"], input[type="submit"][value="Approve"]').first.click(timeout=2500, force=True)),
        ("Potwierdzam role", lambda: page.get_by_role("button", name="Potwierdzam").click(timeout=2500)),
        ("Potwierdzam input", lambda: page.locator('input#f13[type="submit"], input[type="submit"][value="Potwierdzam"]').first.click(timeout=2500, force=True)),
        ("generic submit #f13", lambda: page.locator('input#f13[type="submit"], input[type="submit"]').first.click(timeout=2500, force=True)),
    )
    for label, action in submit_targets:
        try:
            action()
            print(f"[stooq-bulk] captcha submit clicked ({label}).", flush=True)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            try:
                page.wait_for_function(
                    """() => document.querySelector('a#cpt_gh, a[onclick*=\"cpt_gh\"]')
                        || (document.body && /wrong code|invalid code|incorrect code|try again|błędny kod|bledny kod|spróbuj ponownie|sprobuj ponownie/i.test(document.body.innerText || ''))
                        || document.querySelector('a[onclick*=\"cpt_o\"]')""",
                    timeout=2500,
                )
            except Exception:
                pass
            return True
        except Exception:
            continue
    _capture_stooq_bulk_failure(page, "captcha_submit_missing")
    return False

def _refresh_bulk_page_after_captcha(page, download_dir: Path | None = None) -> bool | Path:
    for selector in ('a#cpt_gh', 'a:has-text("Refresh page")', 'a:has-text("Odśwież stronę")', 'a:has-text("Odswiez strone")'):
        try:
            link = page.locator(selector).first
            if link.count() == 0:
                continue
            print(f"[stooq-bulk] captcha accepted; clicking refresh link ({selector}).", flush=True)
            if download_dir is not None:
                try:
                    with page.expect_download(timeout=5000) as download_info:
                        link.click(timeout=2500, force=True)
                    zip_path = _save_stooq_bulk_download_if_zip(download_info.value, download_dir, "captcha refresh link")
                    if zip_path is not None:
                        return zip_path
                    return True
                except PlaywrightTimeoutError:
                    # The refresh link often opens an "Authorization successful" modal
                    # with a separate "Download file..." link instead of starting the
                    # download directly, especially in headless mode.
                    download_result = _click_authorized_bulk_download_link(page, download_dir)
                    if download_result:
                        return download_result
            else:
                link.click(timeout=2500, force=True)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            download_result = _click_authorized_bulk_download_link(page, download_dir)
            if download_result:
                return download_result
            if _bulk_authorization_success_visible(page):
                return True
            return True
        except Exception:
            continue
    if _bulk_authorization_success_visible(page):
        print("[stooq-bulk] authorization successful; refresh link missing but download link/state is present.", flush=True)
        download_result = _click_authorized_bulk_download_link(page, download_dir)
        if download_result:
            return download_result
        return True
    print("[stooq-bulk] captcha refresh link not found; not reloading because code may be wrong.", flush=True)
    return False


def _solve_stooq_bulk_download_captcha(page, symbol: str = "wig_bulk", download_dir: Path | None = None) -> bool | Path:
    """Solve the simple Stooq download captcha, saving artifacts for every attempt."""
    max_attempts = max(1, int(os.getenv("STOCKHELPER_STOOQ_CAPTCHA_ATTEMPTS", "5")))
    print(f"[stooq-bulk] resolving download captcha (max attempts={max_attempts})...", flush=True)
    for attempt in range(1, max_attempts + 1):
        try:
            if _bulk_authorization_success_visible(page):
                download_result = _click_authorized_bulk_download_link(page, download_dir)
                if download_result:
                    return download_result
                return True
            img = _bulk_captcha_image(page)
            if img.count() == 0 or not img.is_visible(timeout=1000):
                _capture_stooq_bulk_attempt(page, symbol, "captcha_missing_or_hidden_treat_as_solved", attempt)
                return True
            suffix = "" if attempt == 1 else f"_a{attempt}"
            raw_path = _captcha_artifact_path(symbol, f"_captcha_raw{suffix}")
            cleaned_path = _captcha_artifact_path(symbol, f"_captcha_cleaned{suffix}")
            try:
                img.screenshot(path=str(raw_path), timeout=5000)
            except Exception as exc:
                _capture_stooq_bulk_attempt(page, symbol, "captcha_image_screenshot_failed", attempt)
                print(f"[stooq-bulk] captcha image screenshot failed for attempt {attempt}/{max_attempts}: {exc}", flush=True)
                if attempt < max_attempts:
                    _request_new_bulk_captcha_code(page, symbol, attempt + 1)
                    continue
                return False
            if not _preprocess_stooq_captcha_image(raw_path, cleaned_path):
                _capture_stooq_bulk_attempt(page, symbol, "captcha_preprocess_failed", attempt)
                if attempt < max_attempts:
                    _request_new_bulk_captcha_code(page, symbol, attempt + 1)
                    continue
                return False
            code, engine = _ocr_stooq_captcha(cleaned_path)
            if len(code) != 4:
                _capture_stooq_bulk_attempt(page, symbol, "captcha_ocr_uncertain", attempt)
                if attempt < max_attempts:
                    _request_new_bulk_captcha_code(page, symbol, attempt + 1)
                    continue
                return False
            page.locator('input[name="cpt_t"], input#f15').first.fill(code, timeout=3000)
            print(f"[stooq-bulk] captcha input filled with OCR code {code} (engine={engine}, attempt={attempt}/{max_attempts}).", flush=True)
            if not _submit_bulk_captcha_form(page):
                _capture_stooq_bulk_attempt(page, symbol, "captcha_submit_failed", attempt)
                if attempt < max_attempts:
                    _request_new_bulk_captcha_code(page, symbol, attempt + 1)
                    continue
                return False
            if _captcha_wrong_code_visible(page):
                _capture_stooq_bulk_attempt(page, symbol, "captcha_code_rejected", attempt)
                print(f"[stooq-bulk] captcha code rejected for attempt {attempt}/{max_attempts}; changing code instead of refreshing.", flush=True)
                if attempt < max_attempts:
                    _request_new_bulk_captcha_code(page, symbol, attempt + 1)
                    continue
                return False
            refresh_result = _refresh_bulk_page_after_captcha(page, download_dir=download_dir)
            if isinstance(refresh_result, Path):
                return refresh_result
            if not refresh_result:
                if _bulk_authorization_success_visible(page):
                    download_result = _click_authorized_bulk_download_link(page, download_dir)
                    if download_result:
                        return download_result
                    return True
                _capture_stooq_bulk_attempt(page, symbol, "captcha_refresh_missing", attempt)
                if _captcha_wrong_code_visible(page) or _page_has_bulk_captcha(page):
                    print(f"[stooq-bulk] no success refresh link after submit for attempt {attempt}/{max_attempts}; changing captcha code.", flush=True)
                    if attempt < max_attempts:
                        _request_new_bulk_captcha_code(page, symbol, attempt + 1)
                        continue
                if attempt < max_attempts:
                    continue
                return False
            try:
                page.wait_for_url(lambda url: "stooq.com/db/h" in url or "stooq.pl/db/h" in url or "db/h" in url, timeout=5000)
            except Exception:
                pass
            _return_to_stooq_bulk_history_if_redirected(page, "captcha refresh")
            return True
        except Exception as exc:
            _capture_stooq_bulk_attempt(page, symbol, "captcha_exception", attempt)
            print(f"[stooq-bulk] captcha auto-solve failed for attempt {attempt}/{max_attempts}: {exc}", flush=True)
            if attempt < max_attempts:
                _request_new_bulk_captcha_code(page, symbol, attempt + 1)
                continue
            return False
    return False


def _download_stooq_wig_bulk_zip(download_dir: Path, interactive: bool = False) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not interactive, slow_mo=150 if interactive else 0)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        def _close_unexpected_popup(popup):
            if popup == page:
                return
            try:
                print(f"[stooq-bulk] closing unexpected popup/ad page: {popup.url}", flush=True)
                popup.close()
            except Exception:
                pass

        context.on("page", _close_unexpected_popup)
        page.set_default_timeout(20000)
        page.set_default_navigation_timeout(30000)
        try:
            page.goto(STOOQ_BULK_HISTORY_URL, wait_until="domcontentloaded")
            _return_to_stooq_bulk_history_if_redirected(page, "initial load")
            _clear_stooq_bulk_consent_manager(page, reason="initial load")

            # First required click usually opens Stooq's download captcha. If the
            # captcha is already trusted and a download starts immediately, keep it.
            first_download = _click_bulk_link_for_optional_download(page, download_dir, timeout=3000, purpose="open captcha or immediate download")
            if first_download is not None:
                return first_download

            try:
                _bulk_captcha_image(page).wait_for(state="visible", timeout=5000)
                print("[stooq-bulk] WIG bulk link clicked; captcha is visible.", flush=True)
            except Exception:
                if not _page_has_bulk_captcha(page):
                    _return_to_stooq_bulk_history_if_redirected(page, "missing captcha after first bulk-link click")
                    print("[stooq-bulk] no captcha/download after first bulk-link click; retrying exact d_pl_txt link once.", flush=True)
                    retry_download = _click_bulk_link_for_optional_download(
                        page,
                        download_dir,
                        timeout=3000,
                        purpose="retry opening captcha or immediate download",
                    )
                    if retry_download is not None:
                        return retry_download
                    try:
                        _bulk_captcha_image(page).wait_for(state="visible", timeout=5000)
                        print("[stooq-bulk] WIG bulk link retry opened captcha.", flush=True)
                    except Exception:
                        if not _page_has_bulk_captcha(page):
                            shot = _capture_stooq_bulk_failure(page, "captcha_not_shown_after_first_click")
                            raise ValueError(
                                "Stooq bulk link click did not start a download and no captcha became visible "
                                f"(url={page.url}, screenshot={shot})."
                            )

            if _page_has_bulk_captcha(page):
                captcha_result = _solve_stooq_bulk_download_captcha(page, download_dir=download_dir)
                if isinstance(captcha_result, Path):
                    return captcha_result
                if not captcha_result:
                    if interactive:
                        shot = _capture_stooq_bulk_failure(page, "captcha_auto_solve_failed_before_inspector")
                        print(
                            "[stooq-bulk] captcha auto-solve failed; opening Playwright inspector. "
                            f"Solve/download manually or fix the page, then resume. Screenshot: {shot}",
                            flush=True,
                        )
                        page.pause()
                    else:
                        fallback = _fallback_existing_stooq_bulk_zip(download_dir, "Stooq captcha flow did not produce a valid zip")
                        if fallback is not None:
                            return fallback
                        shot = _capture_stooq_bulk_failure(page, "captcha_auto_solve_failed")
                        raise ValueError(f"Stooq bulk download captcha could not be solved automatically. Screenshot: {shot}")
                page.reload(wait_until="domcontentloaded")
                _return_to_stooq_bulk_history_if_redirected(page, "after captcha reload")
                _clear_stooq_bulk_consent_manager(page, reason="after captcha reload")

            zip_path = _click_bulk_link_for_optional_download(page, download_dir, timeout=180000, purpose="start zip download after captcha")
            if zip_path is None:
                fallback = _fallback_existing_stooq_bulk_zip(
                    download_dir,
                    "Stooq did not provide a valid zip after captcha (possibly bandwidth-limited error.txt)",
                )
                if fallback is not None:
                    return fallback
                shot = _capture_stooq_bulk_failure(page, "download_not_started_after_captcha")
                raise ValueError(f"Stooq bulk zip download did not start after captcha flow. Screenshot: {shot}")
            return zip_path
        except Exception as exc:
            if "Screenshot:" not in str(exc) and "screenshot=" not in str(exc):
                shot = _capture_stooq_bulk_failure(page, "bulk_download_exception")
                raise ValueError(f"Stooq bulk download failed: {exc}. Screenshot: {shot}") from exc
            raise
        finally:
            try:
                context.close()
            finally:
                browser.close()

def _find_wse_txt_members(zip_path: Path, folder_token: str) -> list[str]:
    with zipfile.ZipFile(zip_path) as zf:
        members = []
        exact_folder = f"wse {folder_token}"
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".txt"):
                continue
            normalized_parts = [part.strip().lower() for part in Path(info.filename).parts]
            if any(part == exact_folder for part in normalized_parts):
                members.append(info.filename)
        if members:
            return members
        # Fallback for archives that encode the folder name slightly differently.
        for info in zf.infolist():
            lowered = info.filename.lower().replace("\\", "/")
            if not info.is_dir() and lowered.endswith(".txt") and "wse" in lowered and folder_token in lowered:
                members.append(info.filename)
        return members


def _find_wse_stocks_txt_members(zip_path: Path) -> list[str]:
    return _find_wse_txt_members(zip_path, "stocks")


def _find_wse_indices_txt_members(zip_path: Path) -> list[str]:
    """Return only WIG20 bulk txt from WSE indices; skip mWIG/sWIG/TR/DVP variants."""
    return [member for member in _find_wse_txt_members(zip_path, "indices") if Path(member).stem.strip().lower() == "wig20"]


def _stooq_bulk_txt_to_ohlcv_df(raw: bytes) -> tuple[str, pd.DataFrame]:
    from io import BytesIO
    df = pd.read_csv(BytesIO(raw), sep=",", on_bad_lines="skip")
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in STOOQ_BULK_TXT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"bulk txt missing columns: {missing}")
    df = df[df["<PER>"].astype(str).str.upper().eq("D")].copy()
    if df.empty:
        return "", pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    ticker = str(df["<TICKER>"].iloc[0]).strip().upper()
    out = pd.DataFrame({
        "Date": pd.to_datetime(df["<DATE>"].astype(str), format="%Y%m%d", errors="coerce"),
        "Open": pd.to_numeric(df["<OPEN>"], errors="coerce"),
        "High": pd.to_numeric(df["<HIGH>"], errors="coerce"),
        "Low": pd.to_numeric(df["<LOW>"], errors="coerce"),
        "Close": pd.to_numeric(df["<CLOSE>"], errors="coerce"),
        "Volume": pd.to_numeric(df["<VOL>"], errors="coerce").fillna(0),
    })
    out = out.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    out = out.sort_values("Date").drop_duplicates(subset=["Date"], keep="last").reset_index(drop=True)
    return ticker, out


def _write_daily_csv_without_trailing_blank_line(df: pd.DataFrame, path: Path) -> None:
    text = df.to_csv(index=False).rstrip("\r\n")
    path.write_text(text, encoding="utf-8")


def import_stooq_wig_bulk_zip(
    zip_path: Path,
    stocks_dir: Path | None = None,
    commodities_dir: Path | None = None,
) -> dict[str, int | str]:
    """Replace local Warsaw stock CSV files and only WIG20 from Stooq's WSE indices bulk folder."""
    zip_path = Path(zip_path)
    project_root = Path(__file__).resolve().parents[1]
    stocks_dir = stocks_dir or project_root / "data" / "stocks"
    commodities_dir = commodities_dir or project_root / "data" / "commodities"
    stocks_dir.mkdir(parents=True, exist_ok=True)
    commodities_dir.mkdir(parents=True, exist_ok=True)
    stock_members = _find_wse_stocks_txt_members(zip_path)
    index_members = _find_wse_indices_txt_members(zip_path)
    if not stock_members:
        raise ValueError(f"No 'wse stocks' txt files found in {zip_path}")
    written = 0
    skipped = 0
    indices_written = 0
    indices_skipped = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in stock_members:
            try:
                ticker, df = _stooq_bulk_txt_to_ohlcv_df(zf.read(member))
                if not ticker or df.empty:
                    skipped += 1
                    continue
                safe_ticker = ticker.replace("/", "").replace(".", "_")
                csv_path = stocks_dir / f"{safe_ticker}_WA.csv"
                _write_daily_csv_without_trailing_blank_line(df, csv_path)
                written += 1
            except Exception as exc:
                skipped += 1
                if _stooq_verbose_enabled():
                    print(f"[stooq-bulk] skipped {member}: {exc}", flush=True)
        for member in index_members:
            try:
                ticker, df = _stooq_bulk_txt_to_ohlcv_df(zf.read(member))
                if not ticker or df.empty:
                    indices_skipped += 1
                    continue
                safe_ticker = ticker.replace("/", "").replace(".", "_")
                csv_path = commodities_dir / f"{safe_ticker}.csv"
                _write_daily_csv_without_trailing_blank_line(df, csv_path)
                indices_written += 1
            except Exception as exc:
                indices_skipped += 1
                if _stooq_verbose_enabled():
                    print(f"[stooq-bulk] skipped index {member}: {exc}", flush=True)
    return {
        "zip_path": str(zip_path),
        "members": len(stock_members),
        "written": written,
        "skipped": skipped,
        "stocks_dir": str(stocks_dir),
        "indices_members": len(index_members),
        "indices_written": indices_written,
        "indices_skipped": indices_skipped,
        "commodities_dir": str(commodities_dir),
    }


def download_and_import_stooq_wig_bulk_data(
    download_dir: Path | None = None,
    stocks_dir: Path | None = None,
    commodities_dir: Path | None = None,
    interactive: bool = False,
) -> dict[str, int | str]:
    """Download Stooq d_pl_txt bulk data and replace local data/stocks WSE CSVs."""
    interactive = interactive or os.getenv("STOCKHELPER_STOOQ_BULK_INSPECTOR") == "1"
    project_root = Path(__file__).resolve().parents[1]
    download_dir = download_dir or project_root / "data" / "downloads" / "stooq"
    zip_path = _download_stooq_wig_bulk_zip(download_dir=Path(download_dir), interactive=interactive)
    result = import_stooq_wig_bulk_zip(zip_path=zip_path, stocks_dir=stocks_dir, commodities_dir=commodities_dir)
    print(
        f"[stooq-bulk] imported WSE stocks: written={result['written']} skipped={result['skipped']} "
        f"from_members={result['members']}; indices_written={result['indices_written']} "
        f"indices_skipped={result['indices_skipped']} from_indices={result['indices_members']} "
        f"zip={result['zip_path']}",
        flush=True,
    )
    return result


def _page_has_rate_limit_or_captcha(page) -> bool:
    try:
        body = page.locator("body").inner_text(timeout=1500)
    except Exception:
        try:
            body = page.content()
        except Exception:
            body = ""
    return _is_rate_limited_html(body)


def _page_has_captcha_image(page) -> bool:
    try:
        if page.locator("#t11 img").first.count() > 0:
            return True
    except Exception:
        pass
    try:
        return page.locator("tr#t11 img").first.count() > 0
    except Exception:
        return False


def _is_rate_limited_html(html: str) -> bool:
    lowered = (html or '').lower()
    markers = ['przekroczony dzienny limit wywołań strony', 'przepisz powyższy kod']
    return any(m in lowered for m in markers)


def _clean_numeric(raw: str, for_volume: bool = False) -> str:
    text = (raw or "").strip().replace(" ", " ").replace(" ", "")
    if for_volume:
        return text.replace(",", "")
    return text.replace(",", ".")


def _parse_stooq_date(raw: str) -> pd.Timestamp:
    text = (raw or "").strip().lower().replace(".", " ")
    parts = [p for p in text.split() if p]
    if len(parts) >= 3 and parts[1] in _POLISH_MONTHS:
        day = parts[0].zfill(2)
        month = _POLISH_MONTHS[parts[1]]
        year = parts[2]
        return pd.to_datetime(f"{year}-{month}-{day}", errors="raise")
    return pd.to_datetime(raw, dayfirst=True, errors="raise")


def _csv_path(base_dir: Path, symbol: str) -> Path:
    safe = symbol.replace('/', '').replace('.', '_').upper()
    return base_dir / f"{safe}.csv"






def _stooq_history_urls(symbol: str) -> list[str]:
    raw = (symbol or "").strip()
    candidates = [raw, raw.lower()]
    dedup = []
    seen = set()
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            dedup.append(f"https://stooq.pl/q/d/?s={c}&i=d")
    return dedup



def _open_page(playwright, interactive: bool = False):
    browser = playwright.chromium.launch(headless=not interactive, slow_mo=150 if interactive else 0)
    page = browser.new_page()
    return browser, page




def _page_has_history_rows(page) -> bool:
    try:
        if _extract_rows_from_frame(page):
            return True
        for fr in page.frames:
            if _extract_rows_from_frame(fr):
                return True
    except Exception:
        pass
    try:
        return page.locator("#fth1, table tr td").count() > 0 and not _page_has_rate_limit_or_captcha(page)
    except Exception:
        return False


def _page_is_blank_or_without_captcha_and_rows(page) -> bool:
    if _page_has_captcha_image(page) or _page_has_history_rows(page):
        return False
    try:
        body_text = page.locator("body").inner_text(timeout=1500).strip()
    except Exception:
        body_text = ""
    # Includes truly blank pages and Stooq limit shells where neither captcha nor
    # historical rows are rendered yet. Those are usually solved by VPN change +
    # reload, not by opening the inspector immediately.
    return len(body_text) < 300 or _page_has_rate_limit_or_captcha(page)


def _vpn_pause_and_reload_stooq_page(page, url: str, symbol: str, reason: str) -> None:
    print(
        f"[stooq-web] {reason} for {symbol}. Change VPN if needed, then press Enter to retry before opening inspector.",
        flush=True,
    )
    try:
        input("[stooq-web] VPN changed / ready to retry? Press Enter to continue...")
    except EOFError:
        print("[stooq-web] non-interactive input; retrying page once before inspector.", flush=True)
    try:
        page.goto(url, wait_until="domcontentloaded")
    except Exception:
        try:
            page.reload(wait_until="domcontentloaded")
        except Exception:
            return
    try:
        _accept_consent_if_present(page, first_page=True)
    except Exception:
        pass
    try:
        _wait_for_table_or_limit_with_retry(page, retries=3)
    except Exception:
        pass


def _refresh_blank_page_before_vpn(page, url: str, symbol: str, reason: str, max_refreshes: int = 2) -> bool:
    """Reload blank/no-table Stooq pages before asking for VPN change.

    Returns True when a reload reached data rows or solved a captcha.
    Returns False when the caller should continue captcha/VPN/inspector handling.
    """
    for attempt in range(1, max(0, max_refreshes) + 1):
        if not _page_is_blank_or_without_captcha_and_rows(page) or _page_has_captcha_image(page):
            break
        print(
            f"[stooq-web] {reason} for {symbol}; refreshing page before VPN prompt ({attempt}/{max_refreshes}).",
            flush=True,
        )
        try:
            page.reload(wait_until="domcontentloaded")
        except Exception:
            try:
                page.goto(url, wait_until="domcontentloaded")
            except Exception:
                break
        try:
            _wait_for_table_or_limit_with_retry(page, retries=2)
        except Exception:
            pass
        if _page_has_history_rows(page):
            return True
        if _try_solve_stooq_captcha(page, symbol):
            return True
    return False


def _retry_blank_page_with_vpn_before_inspector(page, url: str, symbol: str, reason: str, pre_vpn_refreshes: int = 0) -> bool:
    """Retry blank/no-table Stooq pages after optional refreshes and VPN change.

    Returns True when the retry already reached data rows or solved a captcha.
    Returns False when the caller should continue normal captcha/inspector handling.
    """
    if not _page_is_blank_or_without_captcha_and_rows(page) or _page_has_captcha_image(page):
        return False
    with _CAPTCHA_INSPECTOR_LOCK:
        if pre_vpn_refreshes > 0 and _refresh_blank_page_before_vpn(page, url, symbol, reason, pre_vpn_refreshes):
            return True
        if not _page_is_blank_or_without_captcha_and_rows(page) or _page_has_captcha_image(page):
            if _try_solve_stooq_captcha(page, symbol):
                return True
            return _page_has_history_rows(page)
        _vpn_pause_and_reload_stooq_page(page, url, symbol, reason)
        if _try_solve_stooq_captcha(page, symbol):
            return True
        return _page_has_history_rows(page)

def _switch_to_inspector_for_captcha(
    playwright,
    browser,
    page,
    url: str,
    symbol: str,
    interactive_captcha: bool,
    *,
    suspected: bool = False,
):
    """Return (browser, page, still_blocked) after optional headed captcha pause.

    Normal commodity scraping stays headless.  Only when Stooq actually shows a
    captcha/rate-limit page (or the first page is blank while interactive captcha
    handling is enabled) do we relaunch a headed browser and pause in the
    inspector so the user can solve it.  The inspector path is serialized so a
    commodity batch does not open many headed browser pauses at once.
    """
    blocked = _page_has_rate_limit_or_captcha(page)
    captcha_image_visible = _page_has_captcha_image(page)
    if not blocked and not suspected:
        return browser, page, False
    blank_or_no_rows = _page_is_blank_or_without_captcha_and_rows(page)
    if suspected and not blocked and not captcha_image_visible and not blank_or_no_rows:
        return browser, page, False
    if not interactive_captcha:
        return browser, page, True

    if blank_or_no_rows and not captcha_image_visible:
        if _retry_blank_page_with_vpn_before_inspector(page, url, symbol, "Blank/no-table Stooq page before captcha"):
            return browser, page, False
        blocked = _page_has_rate_limit_or_captcha(page)
        captcha_image_visible = _page_has_captcha_image(page)
        blank_or_no_rows = _page_is_blank_or_without_captcha_and_rows(page)
        if blank_or_no_rows and not captcha_image_visible:
            print(f"[stooq-web] blank/no-table page persisted for {symbol}; opening inspector on second failure.", flush=True)

    if _try_solve_stooq_captcha(page, symbol):
        return browser, page, False

    with _CAPTCHA_INSPECTOR_LOCK:
        reason = "CAPTCHA/limit" if blocked else "blank first page (possible CAPTCHA/limit)"
        print(f"[stooq-web] {reason} detected for {symbol}. Opening headed inspector pause.")
        try:
            page.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

        browser, page = _open_page(playwright, interactive=True)
        page.set_default_timeout(15000)
        page.set_default_navigation_timeout(20000)
        try:
            page.goto(url, wait_until="domcontentloaded")
        except Exception:
            return browser, page, True
        _accept_consent_if_present(page, first_page=True)
        if _try_solve_stooq_captcha(page, symbol):
            return browser, page, False
        print("[stooq-web] If captcha/limit is visible, solve it; then click Resume in Playwright inspector.")
        try:
            page.pause()
        except Exception as exc:
            print(f"[stooq-web] Unable to open inspector automatically: {exc}")
            return browser, page, True
        return browser, page, _page_has_rate_limit_or_captcha(page)



def _accept_consent_if_present(page, first_page: bool = False) -> None:
    if not first_page:
        return

    selectors = [
        'button:has-text("Zgadzam się")',
        'button:has-text("Zgadzam sie")',
        'button.fc-button.fc-cta-consent.fc-primary-button',
        'button[aria-label="Zgadzam się"]',
        '.fc-dialog-container button:has-text("Zgadzam się")',
        'text=Zgadzam się',
    ]

    for _ in range(4):
        try:
            contexts = [page] + list(page.frames)
        except Exception:
            contexts = [page]
        clicked = False
        for ctx in contexts:
            for sel in selectors:
                try:
                    loc = ctx.locator(sel).first
                    if loc.count() == 0:
                        continue
                    loc.wait_for(state='visible', timeout=1500)
                    loc.click(timeout=3000, force=True)
                    clicked = True
                    break
                except Exception:
                    continue
            if clicked:
                break
        if clicked:
            # Wait for consent layer to disappear and content table to become available.
            try:
                page.wait_for_timeout(1200)
            except Exception:
                pass
            if not _consent_overlay_visible(page):
                return
        else:
            try:
                page.wait_for_timeout(500)
            except Exception:
                pass

def _consent_overlay_visible(page) -> bool:
    probes = [
        'text=Stooq prosi o zgodę',
        'text=Stooq prosi o zgode',
        'text=Zgadzam się',
        'text=Zgadzam sie',
    ]
    for probe in probes:
        try:
            if page.locator(probe).first.count() > 0:
                return True
        except Exception:
            continue
    return False

def _extract_rows_from_frame(frame) -> list[list[str]]:
    try:
        # Prefer strict Stooq history rows: ids like t03, t11 etc. (data only, no header).
        rows = frame.evaluate("""() => {
            const out = [];
            const dataRows = Array.from(document.querySelectorAll('tr[id^="t"]'));
            for (const tr of dataRows) {
                const tds = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                if (tds.length >= 9) out.push(tds);
            }
            if (out.length) return out;

            // Fallback inside #fth1 excluding header id=f13
            const tblRows = Array.from(document.querySelectorAll('#fth1 tr')).filter(tr => (tr.id || '').toLowerCase() !== 'f13');
            for (const tr of tblRows) {
                const tds = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                if (tds.length >= 9) out.push(tds);
            }
            return out;
        }""")
        return rows or []
    except Exception:
        return []



def _wait_for_table_or_limit_with_retry(page, retries: int = 2) -> bool:
    # Playwright-native wait with retries for occasional blank page loads.
    for _ in range(retries):
        try:
            page.locator("table tr td").first.wait_for(state="visible", timeout=3000)
            return True
        except Exception:
            pass
        body = (page.locator("body").inner_text() or "").lower()
        if "przekroczony dzienny limit" in body or "przepisz powyższy kod" in body:
            return False
        try:
            page.reload(wait_until="domcontentloaded")
        except Exception:
            pass
    try:
        if page.locator("table#fth1 tr[id^='t']").count() > 0:
            return True
    except Exception:
        pass
    return page.locator("table tr td").count() > 0



def _handle_captcha_interactive(page, symbol: str, state: dict | None = None, interactive_captcha: bool = False) -> bool:
    """Optional interactive captcha handling (opens Playwright inspector).

    Enable by setting env: STOCKHELPER_STOOQ_INTERACTIVE_CAPTCHA=1
    """
    if not interactive_captcha:
        return False
    if state is not None and state.get("done"):
        return False

    if page.locator("text=Przekroczony dzienny limit").count() > 0 or page.locator("text=Przepisz powyższy kod").count() > 0:
        if _stooq_verbose_enabled():
            print(f"[stooq-web] CAPTCHA/limit detected for {symbol}. Interactive mode enabled; trying OCR first.")
        try:
            if _try_solve_stooq_captcha(page, symbol):
                if state is not None:
                    state["done"] = True
                if _stooq_verbose_enabled():
                    print(f"[stooq-web] captcha OCR flow finished for {symbol}; continuing debug capture.")
                return True
        except Exception as exc:
            if _stooq_verbose_enabled():
                print(f"[stooq-web] captcha OCR flow failed before inspector for {symbol}: {exc}")
        print("[stooq-web] Browser inspector opened (headed mode required). Solve captcha manually, then resume execution.")
        try:
            page.pause()
            if state is not None:
                state["done"] = True
        except Exception as exc:
            print(f"[stooq-web] Unable to open inspector automatically: {exc}")
            print("[stooq-web] Tip: run with STOCKHELPER_STOOQ_INTERACTIVE_CAPTCHA=1 and desktop session/X server.")
        return True
    return False

def _force_interactive_pause(page, symbol: str, state: dict | None = None, interactive_captcha: bool = False) -> None:
    if not interactive_captcha:
        return
    if state is not None and state.get("forced_pause_done"):
        return
    print(f"[stooq-web] interactive inspector forced for {symbol}. Check page/Network, solve captcha if shown, then Resume.")
    try:
        page.pause()
        if state is not None:
            state["forced_pause_done"] = True
            state["done"] = True
    except Exception as exc:
        print(f"[stooq-web] Unable to open inspector: {exc}")


def _debug_fail_screenshot(symbol: str, page, suffix: str = "") -> str:
    out_dir = Path("debug") / "stooq"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{symbol.lower().replace('.', '_')}{suffix}.png"
    path = out_dir / name
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        return ""
    return str(path)



def _captcha_artifact_path(symbol: str, suffix: str) -> Path:
    if (symbol or "").lower().startswith("wig_bulk"):
        out_dir = _stooq_bulk_debug_dir()
    else:
        out_dir = Path("debug") / "stooq"
        out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{symbol.lower().replace('.', '_')}{suffix}.png"


def _preprocess_stooq_captcha_image(src_path: Path, out_path: Path) -> bool:
    try:
        import cv2
        import numpy as np
    except Exception:
        return False
    img = cv2.imread(str(src_path))
    if img is None:
        return False
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 80, 80])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 80, 80])
    upper_red2 = np.array([180, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = mask1 | mask2
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    # OCR engines generally work better with dark glyphs on a light background.
    cleaned = 255 - cleaned
    cleaned = cv2.resize(cleaned, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    cleaned = cv2.copyMakeBorder(cleaned, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    return bool(cv2.imwrite(str(out_path), cleaned))


def _captcha_code_from_text(text: str) -> str:
    code = "".join(ch for ch in (text or "").upper() if ch.isalnum())
    return code[:4] if len(code) >= 4 else ""


def _captcha_debug_enabled() -> bool:
    return os.getenv("STOCKHELPER_STOOQ_CAPTCHA_DEBUG", "0") == "1"


def _stooq_verbose_enabled() -> bool:
    return os.getenv("STOCKHELPER_STOOQ_DEBUG", "0") == "1" or _captcha_debug_enabled()


def _debug_captcha_ocr(engine: str, raw, code: str, cleaned_path: Path) -> None:
    if not _captcha_debug_enabled():
        return
    print(
        f"[stooq-web] captcha OCR debug engine={engine} raw={raw!r} "
        f"normalized={code!r} len={len(code)} image={cleaned_path}",
        flush=True,
    )


def _captcha_page_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=1500)
    except Exception:
        try:
            return page.content()
        except Exception:
            return ""


def _captcha_wrong_code_visible(page) -> bool:
    text = _captcha_page_text(page).lower()
    markers = ("błędny kod", "bledny kod", "spróbuj ponownie", "sprobuj ponownie", "wrong code", "invalid code", "incorrect code", "try again")
    return any(marker in text for marker in markers)


def _captcha_state_screenshot(page, symbol: str, reason: str, attempt: int) -> str:
    shot = _debug_fail_screenshot(symbol, page, suffix=f"_captcha_{reason}_a{attempt}")
    if shot and _stooq_verbose_enabled():
        print(f"[stooq-web] captcha debug screenshot for {symbol} ({reason}, attempt {attempt}): {shot}", flush=True)
    return shot


def _request_new_captcha_code(page, symbol: str, attempt: int) -> bool:
    selectors = (
        'a:has-text("Zmień kod")',
        'a:has-text("Zmien kod")',
        'a[onclick*="cpt_o"]',
    )
    for selector in selectors:
        try:
            link = page.locator(selector).first
            if link.count() == 0:
                continue
            if _stooq_verbose_enabled():
                print(f"[stooq-web] captcha rejected for {symbol}; requesting new code (attempt {attempt}).", flush=True)
            try:
                link.click(timeout=3000, force=True)
            except Exception:
                link.evaluate("el => el.click()")
            try:
                page.wait_for_timeout(1000)
            except Exception:
                pass
            return True
        except Exception:
            continue
    try:
        page.evaluate("() => { if (typeof cpt_o === 'function') cpt_o(); }")
        try:
            page.wait_for_timeout(1000)
        except Exception:
            pass
        if _stooq_verbose_enabled():
            print(f"[stooq-web] captcha rejected for {symbol}; requested new code via cpt_o() (attempt {attempt}).", flush=True)
        return True
    except Exception:
        pass
    if _stooq_verbose_enabled():
        print(f"[stooq-web] captcha rejected for {symbol}; no 'Zmień kod' link found.", flush=True)
    return False


def _submit_captcha_form(page, symbol: str, attempt: int) -> bool:
    """Click Stooq's visible "Potwierdzam" captcha confirmation button."""
    try:
        # The captcha is validated only by this button click. Use the same
        # Playwright selector as the debug/manual recipe so the action is a real
        # button click, not only a form/DOM submit shortcut.
        button = page.get_by_role("button", name="Potwierdzam")
        button.click(timeout=5000)
        if _stooq_verbose_enabled():
            print(f"[stooq-web] captcha Potwierdzam clicked for {symbol} attempt {attempt}.", flush=True)
        try:
            page.wait_for_timeout(1000)
        except Exception:
            pass
        return True
    except Exception as role_exc:
        if _stooq_verbose_enabled():
            print(
                f"[stooq-web] captcha Potwierdzam role click failed for {symbol} "
                f"attempt {attempt}: {role_exc}",
                flush=True,
            )

    # Fallbacks are only for diagnostics/older browser accessibility quirks; the
    # primary supported selector remains get_by_role("button", name="Potwierdzam").
    fallback_targets = (
        'input#f13[type="submit"]',
        'input[type="submit"][value="Potwierdzam"]',
    )
    for selector in fallback_targets:
        try:
            btn = page.locator(selector).first
            if btn.count() == 0:
                continue
            btn.click(timeout=5000, force=True)
            if _stooq_verbose_enabled():
                print(f"[stooq-web] captcha Potwierdzam clicked for {symbol} attempt {attempt} ({selector} fallback).", flush=True)
            try:
                page.wait_for_timeout(1000)
            except Exception:
                pass
            return True
        except Exception:
            continue

    _captcha_state_screenshot(page, symbol, "submit_failed", attempt)
    return False

def _refresh_after_captcha_submit(page, symbol: str, attempt: int) -> bool:
    try:
        try:
            page.wait_for_timeout(1000)
        except Exception:
            pass
        refresh_link = page.get_by_role("link", name="Odśwież stronę").first
        if refresh_link.count() == 0:
            refresh_link = page.locator("a#cpt_gh").first
        if refresh_link.count() > 0:
            try:
                refresh_link.click(timeout=5000)
            except Exception:
                # The link may exist but be hidden; direct DOM click still runs
                # Stooq's onclick handler without waiting for visibility.
                refresh_link.evaluate("el => el.click()")
            if _stooq_verbose_enabled():
                print(f"[stooq-web] captcha refresh link clicked for {symbol} attempt {attempt}.", flush=True)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            return True
        _captcha_state_screenshot(page, symbol, "refresh_link_missing", attempt)
        return False
    except Exception as exc:
        _captcha_state_screenshot(page, symbol, "refresh_step_failed", attempt)
        print(f"[stooq-web] captcha refresh step failed for {symbol}: {exc}", flush=True)
        return False


def _captcha_refresh_reached_data_page(page, symbol: str, attempt: int) -> bool:
    try:
        _accept_consent_if_present(page, first_page=True)
    except Exception:
        pass
    try:
        _wait_for_table_or_limit_with_retry(page, retries=3)
    except Exception:
        pass
    try:
        if page.locator("#fth1").count() > 0:
            return True
    except Exception:
        pass
    try:
        if _extract_rows_from_frame(page):
            return True
        for fr in page.frames:
            if _extract_rows_from_frame(fr):
                return True
    except Exception:
        pass
    try:
        if page.locator("table tr td").count() > 0 and not _page_has_rate_limit_or_captcha(page):
            return True
    except Exception:
        pass
    return False

def _ocr_stooq_captcha_easyocr(cleaned_path: Path) -> tuple[str, str]:
    global _EASYOCR_READER, _EASYOCR_UNAVAILABLE
    if _EASYOCR_UNAVAILABLE:
        return "", ""
    # EasyOCR lazily downloads/initializes its models. In a commodity scan many
    # workers can hit the captcha at once; serialize both initialization and
    # recognition so they do not all try to download/use the model directory at
    # the same time (which caused repeated download logs and temp.zip races).
    with _CAPTCHA_OCR_LOCK:
        if _EASYOCR_UNAVAILABLE:
            return "", ""
        try:
            with warnings.catch_warnings():
                # EasyOCR imports/uses torch internally. On CPU-only desktops torch
                # can emit repeated CUDA/pin_memory UserWarnings for every captcha;
                # keep scanner output focused on the captcha actions instead.
                warnings.filterwarnings("ignore", category=UserWarning, module=r"torch\..*")
                warnings.filterwarnings("ignore", message=r".*CUDA initialization.*", category=UserWarning)
                warnings.filterwarnings("ignore", message=r".*pin_memory.*", category=UserWarning)
                if _EASYOCR_READER is None:
                    import easyocr
                    _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
                results = _EASYOCR_READER.readtext(
                    str(cleaned_path),
                    detail=0,
                    paragraph=False,
                    allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                    decoder="greedy",
                )
        except Exception as exc:
            _EASYOCR_UNAVAILABLE = True
            if _stooq_verbose_enabled():
                print(f"[stooq-web] EasyOCR unavailable/failed for captcha: {exc}")
            return "", ""
    raw_text = "".join(str(x) for x in results)
    code = _captcha_code_from_text(raw_text)
    _debug_captcha_ocr("easyocr", results, code, cleaned_path)
    return code, raw_text


def _ocr_stooq_captcha_tesseract(cleaned_path: Path) -> tuple[str, str]:
    try:
        import pytesseract
    except Exception as exc:
        _debug_captcha_ocr("tesseract", f"unavailable: {exc}", "", cleaned_path)
        return "", ""
    try:
        text = pytesseract.image_to_string(
            str(cleaned_path),
            config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        )
    except Exception as exc:
        _debug_captcha_ocr("tesseract", f"failed: {exc}", "", cleaned_path)
        return "", ""
    code = _captcha_code_from_text(text)
    _debug_captcha_ocr("tesseract", text, code, cleaned_path)
    return code, text


def _ocr_stooq_captcha(cleaned_path: Path) -> tuple[str, str]:
    easy_code, _easy_raw = _ocr_stooq_captcha_easyocr(cleaned_path)
    if len(easy_code) == 4:
        return easy_code, "easyocr"
    tess_code, _tess_raw = _ocr_stooq_captcha_tesseract(cleaned_path)
    if len(tess_code) == 4:
        return tess_code, "tesseract"
    return "", ""


def _try_solve_stooq_captcha(page, symbol: str) -> bool:
    """Best-effort Stooq captcha solver for the simple red-letter challenge.

    The captcha is usually rendered as an image in row #t11, with input #f15
    and confirmation submit #f13. If cv2/EasyOCR/pytesseract are unavailable
    or OCR is uncertain, return False and let the headed inspector fallback handle it.
    """
    max_attempts = max(1, int(os.getenv("STOCKHELPER_STOOQ_CAPTCHA_ATTEMPTS", "5")))
    print("resolving rate limit captcha and consent...", flush=True)
    for attempt in range(1, max_attempts + 1):
        try:
            img = page.locator("#t11 img").first
            if img.count() == 0:
                img = page.locator("tr#t11 img").first
            if img.count() == 0:
                if attempt == 1:
                    return False
                if _stooq_verbose_enabled():
                    print(f"[stooq-web] captcha image disappeared for {symbol} after attempt {attempt - 1}.", flush=True)
                return False
            suffix = "" if attempt == 1 else f"_a{attempt}"
            raw_path = _captcha_artifact_path(symbol, f"_captcha_raw{suffix}")
            cleaned_path = _captcha_artifact_path(symbol, f"_captcha_cleaned{suffix}")
            img.screenshot(path=str(raw_path))
            if not _preprocess_stooq_captcha_image(raw_path, cleaned_path):
                print("[stooq-web] captcha image found, but cv2/numpy preprocessing is unavailable or failed.", flush=True)
                return False
            code, engine = _ocr_stooq_captcha(cleaned_path)
            if len(code) != 4:
                if attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                    if _stooq_verbose_enabled():
                        print(f"[stooq-web] captcha OCR uncertain for {symbol} attempt {attempt}/{max_attempts}; trying new code.", flush=True)
                    continue
                shot = _captcha_state_screenshot(page, symbol, "ocr_uncertain", attempt)
                print(
                    f"[stooq-web] captcha OCR uncertain for {symbol} attempt {attempt}/{max_attempts}; "
                    f"failure screenshot={shot}",
                    flush=True,
                )
                return False
            # Stooq reuses id=f15/id=f13 on non-input elements in some quote panels,
            # so use tag-qualified locators to avoid Playwright strict-mode matches
            # against <font id="f15"> market-value elements.
            page.locator('input[name="cpt_t"], input#f15').first.fill(code)
            if _stooq_verbose_enabled():
                print(f"[stooq-web] captcha code filled for {symbol} attempt {attempt}/{max_attempts}: {code}", flush=True)
            # Stooq requires submitting the captcha form after filling the code.
            # The "Odśwież stronę" link (#cpt_gh) is generated only after this.
            if not _submit_captcha_form(page, symbol, attempt):
                return False
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            try:
                page.wait_for_timeout(1000)
            except Exception:
                pass

            if _captcha_wrong_code_visible(page):
                if attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                    continue
                return False

            # After a successful captcha submit Stooq may show the refresh link; it
            # still needs to be invoked (or the page reloaded) before history rows
            # appear.
            refresh_clicked = _refresh_after_captcha_submit(page, symbol, attempt)
            if not refresh_clicked:
                if _captcha_wrong_code_visible(page):
                    if attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                        continue
                    return False
                if attempt < max_attempts:
                    if _stooq_verbose_enabled():
                        print(f"[stooq-web] captcha refresh link missing for {symbol} attempt {attempt}/{max_attempts}; not changing code unless Stooq rejects it.", flush=True)
                return False

            if _captcha_wrong_code_visible(page):
                if attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                    continue
                return False

            if _captcha_refresh_reached_data_page(page, symbol, attempt):
                return True

            still_blocked = _page_has_rate_limit_or_captcha(page)
            if still_blocked and attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                if _stooq_verbose_enabled():
                    print(f"[stooq-web] captcha still visible for {symbol} attempt {attempt}/{max_attempts}; trying new code.", flush=True)
                continue
            shot = _captcha_state_screenshot(page, symbol, "result_failed", attempt)
            print(
                f"[stooq-web] captcha flow failed for {symbol} attempt {attempt}/{max_attempts}: "
                f"still_blocked={still_blocked} screenshot={shot or '-'}",
                flush=True,
            )
            return False
        except Exception as exc:
            if attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                if _stooq_verbose_enabled():
                    print(f"[stooq-web] captcha auto-solve failed for {symbol} attempt {attempt}/{max_attempts}: {exc}; trying new code.", flush=True)
                continue
            shot = _captcha_state_screenshot(page, symbol, "exception", attempt)
            print(f"[stooq-web] captcha auto-solve failed for {symbol} attempt {attempt}/{max_attempts}: {exc} screenshot={shot or '-'}", flush=True)
            return False
    return False

def update_stooq_history_with_playwright(symbol: str, csv_path: Path, lookback_days: int = 364, verbose: bool = False, interactive_captcha: bool = False, end_date: datetime | None = None) -> pd.DataFrame:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    anchor_date = (end_date.date() if isinstance(end_date, datetime) else datetime.now(UTC).date())
    start_date = (anchor_date - timedelta(days=lookback_days))

    local = pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    if csv_path.exists():
        local = pd.read_csv(csv_path)
        if "Date" in local.columns:
            local["Date"] = pd.to_datetime(local["Date"], errors="coerce")
            local = local.dropna(subset=["Date"])

    min_required = pd.Timestamp(start_date)
    local_has_full_year = False
    if not local.empty:
        local_min = local["Date"].min()
        local_max = local["Date"].max()
        local_has_full_year = bool(local_min <= min_required and local_max.date() >= anchor_date - timedelta(days=2))
        if local_has_full_year and os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") != "1":
            return local.sort_values("Date").reset_index(drop=True)

    rows: list[dict] = []
    attempted_urls: list[str] = []
    if verbose:
        print(f"[stooq-web] start symbol={symbol} csv={csv_path} lookback_days={lookback_days}")
    started_at = time.monotonic()
    # In interactive captcha mode user may need manual steps; allow a longer watchdog.
    default_runtime = "900" if interactive_captcha else "120"
    max_runtime_s = max(30, int(os.getenv("STOCKHELPER_STOOQ_MAX_RUNTIME_S", default_runtime)))
    last_progress_at = started_at
    # For older-data mode, jump directly to the likely history page to avoid
    # re-reading the newest pages. Stooq shows ~40 rows/page.
    start_page = 1
    if end_date is not None and local is not None and not local.empty:
        try:
            start_page = max(1, int((len(local) // 40) + 1))
        except Exception:
            start_page = 1
    with sync_playwright() as p:
        browser, page = _open_page(p, interactive=False)
        try:
            page.set_default_timeout(15000)
            page.set_default_navigation_timeout(20000)
            page_num = start_page
            empty_pages = 0
            interactive_state = {"done": False, "forced_pause_done": False}
            max_page = max(30, start_page + 30)
            while page_num <= max_page:
                now_mono = time.monotonic()
                if (now_mono - last_progress_at) > max_runtime_s:
                    raise TimeoutError(
                        f"Timeout while fetching Stooq history for {symbol} "
                        f"(>{max_runtime_s}s without progress, last_page={page_num})."
                    )
                url = f"https://stooq.pl/q/d/?s={symbol.lower()}&i=d&l={page_num}"
                attempted_urls.append(url)
                if verbose:
                    print(f"[stooq-web] page={page_num} goto={url}")
                try:
                    page.goto(url, wait_until="domcontentloaded")
                except Exception:
                    break
                if interactive_captcha and _retry_blank_page_with_vpn_before_inspector(
                    page, url, symbol, "Blank/no-table Stooq page before consent", pre_vpn_refreshes=2
                ):
                    pass
                if _page_has_rate_limit_or_captcha(page):
                    browser, page, still_blocked = _switch_to_inspector_for_captcha(p, browser, page, url, symbol, interactive_captcha)
                    if still_blocked:
                        shot = _debug_fail_screenshot(symbol, page, suffix=f"_limit_p{page_num}")
                        raise ValueError(f"Stooq rate limit/captcha detected on page {page_num}. URL: {url} Screenshot: {shot}")
                if page_num == 1:
                    _accept_consent_if_present(page, first_page=True)
                    if interactive_captcha and _retry_blank_page_with_vpn_before_inspector(
                        page, url, symbol, "Blank/no-table Stooq page after consent"
                    ):
                        pass
                ready = _wait_for_table_or_limit_with_retry(page, retries=3)
                if interactive_captcha and _retry_blank_page_with_vpn_before_inspector(
                    page, url, symbol, "Blank/no-table Stooq page after table wait"
                ):
                    ready = True
                if _page_has_rate_limit_or_captcha(page):
                    browser, page, still_blocked = _switch_to_inspector_for_captcha(p, browser, page, url, symbol, interactive_captcha)
                    if still_blocked:
                        shot = _debug_fail_screenshot(symbol, page, suffix=f"_limit_after_wait_p{page_num}")
                        raise ValueError(f"Stooq rate limit/captcha detected after table wait on page {page_num}. URL: {url} Screenshot: {shot}")
                if verbose:
                    print(f"[stooq-web] page={page_num} ready={ready}")

                extracted = _extract_rows_from_frame(page)
                if not extracted:
                    for fr in page.frames:
                        extracted = _extract_rows_from_frame(fr)
                        if extracted:
                            break

                if verbose:
                    print(f"[stooq-web] page={page_num} extracted_rows={len(extracted)}")

                if page_num == 1 and not extracted:
                    # Consent modal can still block table even when first click missed/lagged.
                    if _consent_overlay_visible(page):
                        _accept_consent_if_present(page, first_page=True)
                        if _consent_overlay_visible(page):
                            try:
                                page.reload(wait_until='domcontentloaded')
                            except Exception:
                                pass
                            _accept_consent_if_present(page, first_page=True)
                        _wait_for_table_or_limit_with_retry(page, retries=5)
                        extracted = _extract_rows_from_frame(page)
                        if not extracted:
                            for fr in page.frames:
                                extracted = _extract_rows_from_frame(fr)
                                if extracted:
                                    break
                    if not extracted and interactive_captcha:
                        browser, page, still_blocked = _switch_to_inspector_for_captcha(
                            p, browser, page, url, symbol, interactive_captcha, suspected=True
                        )
                        if not still_blocked:
                            _wait_for_table_or_limit_with_retry(page, retries=5)
                            extracted = _extract_rows_from_frame(page)
                            if not extracted:
                                for fr in page.frames:
                                    extracted = _extract_rows_from_frame(fr)
                                    if extracted:
                                        break
                    shot = _debug_fail_screenshot(symbol, page, suffix="_no_rows")
                    if _is_rate_limited_html(page.content()):
                        raise ValueError(f"Stooq rate limit detected (captcha/limit popup). URL: {url} Screenshot: {shot}")
                    if not extracted:
                        raise ValueError(f"Stooq first-page check failed (no table rows). URL: {url} Screenshot: {shot}")

                if not extracted:
                    break

                page_added = 0
                parsed_ok = 0
                oldest_dt_on_page = None
                for row in extracted:
                    # Expected columns: Nr, Data, Open, High, Low, Close, Zmiana%, Zmiana, Wolumen, LOP
                    d = row[1] if len(row) >= 2 else ''
                    try:
                        dt = _parse_stooq_date(d)
                    except Exception:
                        continue
                    if oldest_dt_on_page is None or dt < oldest_dt_on_page:
                        oldest_dt_on_page = dt
                    parsed_ok += 1
                    if dt < min_required:
                        continue
                    rows.append({
                        'Date': dt,
                        'Open': _clean_numeric(row[2]),
                        'High': _clean_numeric(row[3]),
                        'Low': _clean_numeric(row[4]),
                        'Close': _clean_numeric(row[5]),
                        'Volume': _clean_numeric((row[8] if len(row) > 8 else row[7]), for_volume=True)
                    })
                    page_added += 1

                if verbose:
                    print(f"[stooq-web] page={page_num} parsed_ok={parsed_ok} added_rows={page_added} oldest={oldest_dt_on_page}")
                else:
                    print(f"[stooq-web] progress page={page_num} collected={len(rows)}")

                if page_added == 0:
                    empty_pages += 1
                else:
                    empty_pages = 0
                    last_progress_at = time.monotonic()

                if empty_pages >= 2:
                    break
                if oldest_dt_on_page is not None and oldest_dt_on_page < min_required:
                    break
                page_num += 1
        finally:
            try:
                page.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass


    remote = pd.DataFrame(rows)
    if remote.empty:
        raise ValueError(f"Brak danych ze strony Stooq dla {symbol}. Attempted URLs: {attempted_urls}")
    if verbose:
        print(f"[stooq-web] collected_rows={len(remote)}")

    for c in ["Open", "High", "Low", "Close", "Volume"]:
        remote[c] = pd.to_numeric(remote[c], errors="coerce")
    remote = remote.dropna(subset=["Date", "Open", "High", "Low", "Close"])

    if local is None or local.empty or not local_has_full_year:
        # If cached file is shorter than requested 1-year window, rebuild from fresh remote pull.
        merged = remote.copy()
    else:
        merged = pd.concat([local, remote], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)
    if end_date is None:
        merged = merged[merged["Date"] >= min_required]
    merged.to_csv(csv_path, index=False)
    return merged


def _rows_to_daily_df(rows: list[list[str]]) -> pd.DataFrame:
    parsed: list[dict] = []
    for row in rows:
        # Expected columns: Nr, Data, Open, High, Low, Close, Zmiana%, Zmiana, Wolumen, LOP
        if len(row) < 6:
            continue
        try:
            dt = _parse_stooq_date(row[1])
            parsed.append(
                {
                    "Date": dt,
                    "Open": float(_clean_numeric(row[2])),
                    "High": float(_clean_numeric(row[3])),
                    "Low": float(_clean_numeric(row[4])),
                    "Close": float(_clean_numeric(row[5])),
                    "Volume": float(_clean_numeric(row[8], for_volume=True)) if len(row) > 8 and _clean_numeric(row[8], for_volume=True) else 0.0,
                }
            )
        except Exception:
            continue
    if not parsed:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    return pd.DataFrame(parsed).dropna(subset=["Date", "Open", "High", "Low", "Close"]).sort_values("Date").reset_index(drop=True)


def _merge_debug_rows_into_csv(rows: list[list[str]], csv_path: Path) -> tuple[int, str]:
    remote = _rows_to_daily_df(rows)
    if remote.empty:
        return 0, ""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    local = pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    if csv_path.exists():
        try:
            local = pd.read_csv(csv_path)
            if "Date" in local.columns:
                local["Date"] = pd.to_datetime(local["Date"], errors="coerce")
                local = local.dropna(subset=["Date"])
        except Exception:
            local = pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    merged = pd.concat([local, remote], ignore_index=True)
    merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce")
    merged = merged.dropna(subset=["Date"])
    merged = merged.drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)
    merged.to_csv(csv_path, index=False)
    latest = ""
    if not merged.empty:
        latest = pd.to_datetime(merged["Date"].max()).strftime("%Y-%m-%d")
    return len(remote), latest


def debug_stooq_page(symbol: str, out_dir: Path | None = None, interactive_captcha: bool = False, csv_path: Path | None = None) -> Path:
    out_dir = out_dir or Path("debug") / "stooq"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{symbol.lower().replace('.', '_')}_debug.json"

    urls = _stooq_history_urls(symbol)
    payload: dict = {"symbol": symbol, "url": urls[0], "attempted_urls": [], "debug_only": csv_path is None}
    with sync_playwright() as p:
        browser, page = _open_page(p, interactive=interactive_captcha)
        response = None
        interactive_state = {"done": False, "forced_pause_done": False}
        for u in urls:
            try:
                response = page.goto(u, wait_until="domcontentloaded")
                _accept_consent_if_present(page, first_page=True)
                _handle_captcha_interactive(page, symbol, interactive_state, interactive_captcha)
                _wait_for_table_or_limit_with_retry(page, retries=3)
                payload["attempted_urls"].append({"url": u, "title": page.title(), "table_count": page.locator("table").count(), "fth1_count": page.locator("#fth1").count(), "goto_error": None})
            except Exception as exc:
                payload["attempted_urls"].append({"url": u, "title": "", "table_count": 0, "fth1_count": 0, "goto_error": str(exc)})
                continue
            if page.locator("#fth1").count() > 0:
                break
        page.wait_for_timeout(1500)
        try:
            page.wait_for_selector("table#fth1", timeout=6000)
        except Exception:
            pass

        html = page.content()
        html_path = out_dir / f"{symbol.lower().replace('.', '_')}.html"
        html_path.write_text(html, encoding="utf-8")
        page.screenshot(path=str(out_dir / f"{symbol.lower().replace('.', '_')}.png"), full_page=True)

        rows = _extract_rows_from_frame(page)
        frame_rows = {}
        if not rows:
            for fr in page.frames:
                fr_rows = _extract_rows_from_frame(fr)
                frame_rows[fr.url] = len(fr_rows)
                if fr_rows and not rows:
                    rows = fr_rows
        payload["rows_count"] = len(rows)
        payload["rows_preview"] = rows[:8]
        if csv_path is not None:
            written_rows, latest_date = _merge_debug_rows_into_csv(rows, csv_path)
            payload["csv_path"] = str(csv_path)
            payload["csv_rows_merged_from_debug"] = written_rows
            payload["csv_latest_date_after_merge"] = latest_date
        payload["title"] = page.title()
        payload["status"] = response.status if response else None
        payload["final_url"] = page.url
        payload["html_path"] = str(html_path)
        payload["html_length"] = len(html)
        payload["html_head"] = html[:1000]
        payload["table_count"] = page.locator("table").count()
        payload["fth1_count"] = page.locator("#fth1").count()
        payload["frames"] = [fr.url for fr in page.frames]
        payload["frame_rows"] = frame_rows
        payload["contains_fth1_text"] = "fth1" in html.lower()
        payload["rate_limited"] = _is_rate_limited_html(html)
        browser.close()

    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file
