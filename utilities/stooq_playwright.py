from __future__ import annotations

from datetime import UTC, datetime, timedelta
import time
import os
import json
import re
import threading
import warnings
import zipfile
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


_CAPTCHA_INSPECTOR_LOCK = threading.Lock()
_CAPTCHA_OCR_LOCK = threading.Lock()
_EASYOCR_READER = None
_EASYOCR_UNAVAILABLE = False


_POLISH_MONTHS = {
    "sty": "01", "lut": "02", "mar": "03", "kwi": "04", "maj": "05", "cze": "06",
    "lip": "07", "sie": "08", "wrz": "09", "paź": "10", "paz": "10", "lis": "11", "gru": "12",
}


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



def _click_consent_text_fallback(ctx) -> bool:
    """Click common CMP consent buttons by visible text inside a page/frame."""
    script = """() => {
        const needles = [
            'zgadzam się', 'zgadzam sie', 'consent', 'i consent',
            'i agree', 'agree', 'accept all', 'accept', 'allow all'
        ];
        const isVisible = (el) => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style && style.visibility !== 'hidden' && style.display !== 'none'
                && rect.width > 0 && rect.height > 0;
        };
        const candidates = Array.from(document.querySelectorAll(
            'button, [role=\"button\"], input[type=\"button\"], input[type=\"submit\"], a'
        ));
        for (const el of candidates) {
            const text = ((el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || '') + '').trim().toLowerCase();
            if (!text || !isVisible(el)) continue;
            if (needles.some(n => text.includes(n))) {
                el.click();
                return true;
            }
        }
        return false;
    }"""
    try:
        return bool(ctx.evaluate(script))
    except Exception:
        return False


def _accept_consent_if_present(page, first_page: bool = False) -> None:
    if not first_page:
        return

    selectors = [
        'button:has-text("Zgadzam się")',
        'button:has-text("Zgadzam sie")',
        'button:has-text("Consent")',
        'button:has-text("I Consent")',
        'button:has-text("I agree")',
        'button:has-text("Agree")',
        'button:has-text("Accept")',
        'button:has-text("Accept all")',
        'button:has-text("Allow all")',
        'button.fc-button.fc-cta-consent.fc-primary-button',
        'button[aria-label="Zgadzam się"]',
        'button[aria-label="Consent"]',
        'button[aria-label="I agree"]',
        'button[aria-label="Accept"]',
        '.fc-dialog-container button:has-text("Zgadzam się")',
        '.fc-dialog-container button:has-text("Consent")',
        '.fc-dialog-container button:has-text("Accept")',
        '#didomi-notice-agree-button',
        '#onetrust-accept-btn-handler',
        'text=Zgadzam się',
        'text=Consent',
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
                    if _stooq_verbose_enabled():
                        print(f"[stooq-web] consent manager clicked with selector: {sel}", flush=True)
                    clicked = True
                    break
                except Exception:
                    continue
            if clicked:
                break
        if not clicked:
            consent_re = re.compile(r"zgadzam|consent|agree|accept|allow", re.I)
            for ctx in contexts:
                try:
                    ctx.get_by_role("button", name=consent_re).first.click(timeout=2000, force=True)
                    if _stooq_verbose_enabled():
                        print("[stooq-web] consent manager clicked with role fallback", flush=True)
                    clicked = True
                    break
                except Exception:
                    pass
                try:
                    ctx.get_by_text(consent_re).first.click(timeout=2000, force=True)
                    if _stooq_verbose_enabled():
                        print("[stooq-web] consent manager clicked with text locator fallback", flush=True)
                    clicked = True
                    break
                except Exception:
                    pass
                if _click_consent_text_fallback(ctx):
                    if _stooq_verbose_enabled():
                        print("[stooq-web] consent manager clicked with JS text fallback", flush=True)
                    clicked = True
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


def _accept_stooq_consent_for_bulk(page, phase: str) -> None:
    print(f"[stooq-bulk] checking consent manager ({phase})...", flush=True)
    try:
        _accept_consent_if_present(page, first_page=True)
    except Exception as exc:
        print(f"[stooq-bulk] consent manager handling failed ({phase}): {exc}", flush=True)
        return
    try:
        if _consent_overlay_visible(page):
            print(f"[stooq-bulk] consent manager still visible after click attempts ({phase}).", flush=True)
            _debug_fail_screenshot("stooq_pl_bulk", page, suffix=f"_consent_still_visible_{phase}")
        else:
            print(f"[stooq-bulk] consent manager not blocking page ({phase}).", flush=True)
    except Exception:
        pass


def _consent_overlay_visible(page) -> bool:
    probes = [
        'Stooq prosi o zgodę',
        'Stooq prosi o zgode',
        'wykorzystanie Twoich danych osobowych',
        'wykorzystanie Twoich danych',
        'Zgadzam się',
        'Zgadzam sie',
        'Consent Manager',
        'Consent',
        'I agree',
        'Accept all',
    ]
    try:
        contexts = [page] + list(page.frames)
    except Exception:
        contexts = [page]
    for ctx in contexts:
        try:
            body = ctx.locator("body").inner_text(timeout=700)
        except Exception:
            body = ""
        lowered = body.lower()
        if any(probe.lower() in lowered for probe in probes):
            return True
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
    markers = ("błędny kod", "bledny kod", "spróbuj ponownie", "sprobuj ponownie")
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


def _stooq_page_contexts(page):
    try:
        return [("page", page)] + [(f"frame:{i}", frame) for i, frame in enumerate(page.frames)]
    except Exception:
        return [("page", page)]


def _stooq_captcha_image_locator(page):
    selectors = (
        'img[src*="/q/l/s/i/"]',
        'img[src^="//stooq.com/q/l/s/i/"]',
        '#t11 img',
        'tr#t11 img',
    )
    fallback = None
    for label, ctx in _stooq_page_contexts(page):
        for selector in selectors:
            try:
                locator = ctx.locator(selector).first
                if locator.count() == 0:
                    continue
                if fallback is None:
                    fallback = locator
                try:
                    if locator.is_visible(timeout=500):
                        print(f"[stooq-bulk] captcha image found with {selector} ({label})", flush=True)
                        return locator
                except Exception:
                    pass
            except Exception:
                continue
    return fallback


def _stooq_captcha_input_locator(page):
    selectors = ('input[name="cpt_t"]', 'input#f15')
    fallback = None
    for label, ctx in _stooq_page_contexts(page):
        for selector in selectors:
            try:
                locator = ctx.locator(selector).first
                if locator.count() == 0:
                    continue
                if fallback is None:
                    fallback = locator
                try:
                    if locator.is_visible(timeout=500):
                        print(f"[stooq-bulk] captcha input found with {selector} ({label})", flush=True)
                        return locator
                except Exception:
                    pass
            except Exception:
                continue
    return fallback


def _stooq_download_link_locator(page, require_visible: bool = False):
    selectors = ('a#cpt_gh', 'a:has-text("Download file")', 'a:has-text("Download file...")')
    fallback = None
    for label, ctx in _stooq_page_contexts(page):
        for selector in selectors:
            try:
                locator = ctx.locator(selector).first
                if locator.count() == 0:
                    continue
                if fallback is None:
                    fallback = locator
                try:
                    visible = locator.is_visible(timeout=500)
                except Exception:
                    visible = False
                if not require_visible or visible:
                    print(
                        f"[stooq-bulk] download link found with {selector} ({label}) "
                        f"visible={visible}",
                        flush=True,
                    )
                    return locator
            except Exception:
                continue
    return None if require_visible else fallback


def _stooq_download_link_ready(page) -> bool:
    return _stooq_download_link_locator(page, require_visible=True) is not None


def _wait_for_stooq_download_gate_after_click(page, symbol: str, timeout_ms: int = 10000) -> None:
    try:
        result = page.wait_for_function(
            """() => {
                const visible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden' && style.display !== 'none'
                        && rect.width > 0 && rect.height > 0;
                };
                if ([...document.querySelectorAll('img')].some(img => (img.getAttribute('src') || '').includes('/q/l/s/i/'))) return 'captcha_image';
                if (document.querySelector('input[name="cpt_t"], input#f15')) return 'captcha_input';
                if ([...document.querySelectorAll('a#cpt_gh, a')].some(a => visible(a) && /Download file/i.test(a.textContent || ''))) return 'download_link';
                return false;
            }""",
            timeout=timeout_ms,
        ).json_value()
        print(f"[stooq-bulk] Stooq gate appeared after listing click: {result}", flush=True)
    except Exception:
        _debug_stooq_download_page(page, symbol, "gate_after_listing_click_timeout")


def _wait_for_stooq_captcha_image(page, timeout_ms: int = 5000):
    try:
        page.wait_for_function(
            """() => [...document.querySelectorAll('img')]
                .some(img => (img.getAttribute('src') || '').includes('/q/l/s/i/'))""",
            timeout=timeout_ms,
        )
    except Exception:
        return None
    return _stooq_captcha_image_locator(page)


def _click_stooq_captcha_approve(page, symbol: str, attempt: int) -> bool:
    selectors = (
        'input#f13[type="submit"]',
        'input[type="submit"][value="Approve"]',
        'input[type="submit"][value="Potwierdzam"]',
    )
    for label, ctx in _stooq_page_contexts(page):
        for selector in selectors:
            try:
                button = ctx.locator(selector).first
                if button.count() == 0:
                    continue
                button.click(timeout=5000, force=True)
                print(
                    f"[stooq-bulk] captcha approve clicked for {symbol} "
                    f"attempt {attempt} ({selector}, {label}).",
                    flush=True,
                )
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
                try:
                    page.wait_for_timeout(1000)
                except Exception:
                    pass
                return True
            except Exception:
                continue
    try:
        button = page.get_by_role("button", name="Approve")
        button.click(timeout=5000)
        return True
    except Exception:
        pass
    _captcha_state_screenshot(page, symbol, "approve_failed", attempt)
    return False


def _solve_stooq_download_captcha(page, symbol: str) -> bool:
    max_attempts = max(1, int(os.getenv("STOCKHELPER_STOOQ_CAPTCHA_ATTEMPTS", "5")))
    print(f"[stooq-bulk] resolving Stooq download captcha (max_attempts={max_attempts})...", flush=True)
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[stooq-bulk] captcha attempt {attempt}/{max_attempts}: locating captcha image...", flush=True)
            img = _stooq_captcha_image_locator(page)
            if img is None:
                input_present = _stooq_captcha_input_locator(page) is not None
                if input_present:
                    print("[stooq-bulk] captcha input is present; waiting for captcha image to load...", flush=True)
                    img = _wait_for_stooq_captcha_image(page, timeout_ms=7000)
                if img is None:
                    link_ready = _stooq_download_link_ready(page)
                    print(
                        f"[stooq-bulk] captcha image not found; "
                        f"input_present={input_present} visible_download_link_ready={link_ready}",
                        flush=True,
                    )
                    if not link_ready:
                        _debug_stooq_download_page(page, symbol, "captcha_image_missing")
                    return link_ready
            suffix = "" if attempt == 1 else f"_a{attempt}"
            raw_path = _captcha_artifact_path(symbol, f"_download_captcha_raw{suffix}")
            cleaned_path = _captcha_artifact_path(symbol, f"_download_captcha_cleaned{suffix}")
            img.screenshot(path=str(raw_path))
            print(f"[stooq-bulk] captcha screenshot saved: {raw_path}", flush=True)
            if not _preprocess_stooq_captcha_image(raw_path, cleaned_path):
                print("[stooq-web] captcha image found, but cv2/numpy preprocessing is unavailable or failed.", flush=True)
                return False
            code, engine = _ocr_stooq_captcha(cleaned_path)
            print(
                f"[stooq-bulk] captcha OCR attempt {attempt}/{max_attempts}: "
                f"engine={engine or '-'} code_len={len(code)}",
                flush=True,
            )
            if len(code) != 4:
                if attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                    continue
                shot = _captcha_state_screenshot(page, symbol, "download_ocr_uncertain", attempt)
                print(f"[stooq-web] download captcha OCR uncertain for {symbol}; screenshot={shot or '-'}", flush=True)
                return False
            input_box = _stooq_captcha_input_locator(page)
            if input_box is None:
                _debug_stooq_download_page(page, symbol, "captcha_input_missing")
                return False
            input_box.fill(code)
            print("[stooq-bulk] captcha code filled; clicking approve...", flush=True)
            if _stooq_verbose_enabled():
                print(
                    f"[stooq-web] download captcha code filled for {symbol} "
                    f"attempt {attempt}/{max_attempts}: {code} ({engine}).",
                    flush=True,
                )
            if not _click_stooq_captcha_approve(page, symbol, attempt):
                return False
            if _captcha_wrong_code_visible(page):
                if attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                    continue
                return False
            if page.locator("a#cpt_gh").first.count() > 0:
                print("[stooq-bulk] captcha approved; download link is visible.", flush=True)
                return True
            try:
                page.wait_for_selector("a#cpt_gh", timeout=5000)
                print("[stooq-bulk] captcha approved; download link appeared after wait.", flush=True)
                return True
            except Exception:
                if (
                    _captcha_wrong_code_visible(page)
                    and attempt < max_attempts
                    and _request_new_captcha_code(page, symbol, attempt + 1)
                ):
                    continue
                shot = _captcha_state_screenshot(page, symbol, "download_link_missing", attempt)
                print(f"[stooq-web] download link missing after captcha for {symbol}; screenshot={shot or '-'}", flush=True)
                return False
        except Exception as exc:
            if attempt < max_attempts and _request_new_captcha_code(page, symbol, attempt + 1):
                continue
            shot = _captcha_state_screenshot(page, symbol, "download_exception", attempt)
            print(f"[stooq-web] download captcha flow failed for {symbol}: {exc}; screenshot={shot or '-'}", flush=True)
            return False
    return False


def _playwright_saved_download_is_valid(path: Path, expect_zip: bool) -> bool:
    return not expect_zip or zipfile.is_zipfile(path)


def _save_playwright_download(download, download_path: Path, expect_zip: bool, label: str) -> bool:
    download.save_as(str(download_path))
    size_mb = download_path.stat().st_size / (1024 * 1024)
    valid = _playwright_saved_download_is_valid(download_path, expect_zip)
    status = "valid" if valid else "invalid"
    print(
        f"[stooq-bulk] Playwright: {label} saved to {download_path} "
        f"({size_mb:.3f} MB, {status})",
        flush=True,
    )
    return valid


def _debug_stooq_download_page(page, symbol: str, reason: str) -> str:
    safe_reason = reason.lower().replace(" ", "_").replace("/", "_")
    shot = _debug_fail_screenshot(symbol, page, suffix=f"_download_{safe_reason}")
    html_path = ""
    try:
        out_dir = Path("debug") / "stooq"
        out_dir.mkdir(parents=True, exist_ok=True)
        html = page.content()
        html_file = out_dir / f"{symbol.lower().replace('.', '_')}_download_{safe_reason}.html"
        html_file.write_text(html, encoding="utf-8", errors="replace")
        html_path = str(html_file)
    except Exception:
        html_path = ""
    try:
        body = page.locator("body").inner_text(timeout=1500).strip().replace("\n", " ")
        body_preview = body[:500]
    except Exception:
        body_preview = ""
    print(
        f"[stooq-bulk] debug page state ({reason}): url={getattr(page, 'url', '')} "
        f"screenshot={shot or '-'} html={html_path or '-'} body={body_preview!r}",
        flush=True,
    )
    return shot


def _debug_stooq_download_links(page) -> None:
    try:
        contexts = [("page", page)] + [(f"frame:{i}", frame) for i, frame in enumerate(page.frames)]
    except Exception:
        contexts = [("page", page)]
    for label, ctx in contexts:
        try:
            rows = ctx.locator("a").evaluate_all(
                """els => els.slice(0, 25).map((a, i) => ({
                    i,
                    text: (a.innerText || a.textContent || '').trim().slice(0, 60),
                    href: a.getAttribute('href') || '',
                    onclick: a.getAttribute('onclick') || ''
                }))"""
            )
            print(f"[stooq-bulk] Playwright: visible link sample ({label}): {rows}", flush=True)
        except Exception as exc:
            print(f"[stooq-bulk] Playwright: could not inspect listing links ({label}): {exc}", flush=True)


def _find_stooq_bulk_listing_link(page, preferred_selector: str | None):
    selectors = [
        preferred_selector,
        'a[href*="d_pl_txt"]',
        'a[href*="b=d_pl_txt"]',
        'a[href*="db/d/?b=d_pl_txt"]',
    ]
    try:
        contexts = [("page", page)] + [(f"frame:{i}", frame) for i, frame in enumerate(page.frames)]
    except Exception:
        contexts = [("page", page)]
    for label, ctx in contexts:
        for selector in [s for s in selectors if s]:
            try:
                link = ctx.locator(selector).first
                if link.count() > 0:
                    print(
                        f"[stooq-bulk] Playwright: found listing link with selector: "
                        f"{selector} ({label})",
                        flush=True,
                    )
                    return link
            except Exception:
                continue
        try:
            links = ctx.locator("a")
            for index in range(min(links.count(), 200)):
                link = links.nth(index)
                href = link.get_attribute("href") or ""
                onclick = link.get_attribute("onclick") or ""
                text = (link.inner_text(timeout=500) or "").strip()
                haystack = f"{href} {onclick} {text}".lower()
                if "d_pl_txt" in haystack or "b=d_pl_txt" in haystack:
                    print(
                        f"[stooq-bulk] Playwright: found listing link by scanning anchors: "
                        f"context={label} index={index} text={text!r} href={href!r}",
                        flush=True,
                    )
                    return link
        except Exception as exc:
            print(f"[stooq-bulk] Playwright: anchor scan failed ({label}): {exc}", flush=True)
    return None


def _open_direct_stooq_download_or_gate(page, url: str):
    print("[stooq-bulk] Playwright: opening direct URL with download watcher...", flush=True)
    try:
        with page.expect_download(timeout=15000) as download_info:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as goto_exc:
                if "Download is starting" not in str(goto_exc):
                    raise
                print("[stooq-bulk] Playwright: direct URL triggered browser download.", flush=True)
        return download_info.value
    except Exception as direct_exc:
        print(
            f"[stooq-bulk] Playwright: direct URL did not produce a usable download "
            f"({direct_exc}); loading as captcha gate...",
            flush=True,
        )
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            _accept_stooq_consent_for_bulk(page, "direct-gate")
        except Exception as goto_exc:
            if "Download is starting" in str(goto_exc):
                raise ValueError(
                    "Direct Stooq URL started a download but Playwright did not capture it"
                ) from goto_exc
            raise
        return None


def _open_stooq_download_gate(page, url: str, listing_url: str | None, link_selector: str | None):
    """Open Stooq's download gate page and return a download if clicking starts one."""
    if listing_url:
        print(f"[stooq-bulk] Playwright: opening Stooq listing page: {listing_url}", flush=True)
        page.goto(listing_url, wait_until="domcontentloaded", timeout=30000)
        _accept_stooq_consent_for_bulk(page, "listing")
        try:
            page.wait_for_timeout(1500)
        except Exception:
            pass
        link = _find_stooq_bulk_listing_link(page, link_selector)
        if link is None:
            print(
                "[stooq-bulk] Playwright: listing link not found; "
                "dumping link sample and trying direct URL...",
                flush=True,
            )
            _debug_stooq_download_links(page)
            _debug_stooq_download_page(page, "stooq_pl_bulk", "listing_link_missing")
            return _open_direct_stooq_download_or_gate(page, url)
        print("[stooq-bulk] Playwright: clicking listing download link...", flush=True)
        try:
            with page.expect_download(timeout=10000) as download_info:
                try:
                    link.click(timeout=5000, force=True)
                except Exception:
                    link.evaluate("el => el.click()")
            print("[stooq-bulk] Playwright: listing click started a download.", flush=True)
            return download_info.value
        except Exception as click_exc:
            print(
                f"[stooq-bulk] Playwright: listing click did not start a direct download "
                f"({click_exc}); checking captcha gate...",
                flush=True,
            )
            _wait_for_stooq_download_gate_after_click(page, "stooq_pl_bulk")
            return None
    return _open_direct_stooq_download_or_gate(page, url)


def _goto_stooq_download_url_for_expected_download(page, url: str) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as exc:
        if "Download is starting" not in str(exc):
            raise
        print("[stooq-bulk] Playwright: direct URL raised 'Download is starting' inside watcher.", flush=True)


def _expect_stooq_download_action(page, label: str, action, timeout: int = 30000):
    print(f"[stooq-bulk] Playwright: attempting final download via {label}...", flush=True)
    try:
        with page.expect_download(timeout=timeout) as download_info:
            action()
        print(f"[stooq-bulk] Playwright: final download started via {label}.", flush=True)
        return download_info.value
    except Exception as exc:
        print(f"[stooq-bulk] Playwright: final download via {label} failed ({exc}).", flush=True)
        return None


def _download_from_stooq_ready_gate(page, url: str, link, download_path: Path, expect_zip: bool, symbol: str) -> Path:
    """Try all known Stooq post-captcha download actions and require a valid file."""
    attempts = [
        (
            "#cpt_gh click",
            lambda: link.click(timeout=5000, force=True),
        ),
        (
            "#cpt_gh DOM click",
            lambda: link.evaluate("el => el.click()"),
        ),
        (
            "cpt_g(0,0,1)",
            lambda: page.evaluate("() => { if (typeof cpt_g === 'function') return cpt_g(0,0,1); }")
        ),
        (
            "direct URL after captcha gate",
            lambda: _goto_stooq_download_url_for_expected_download(page, url),
        ),
    ]
    for label, action in attempts:
        download = _expect_stooq_download_action(page, label, action)
        if download is None:
            continue
        if _save_playwright_download(download, download_path, expect_zip, label):
            return download_path
        try:
            download_path.unlink()
        except OSError:
            pass
        print(f"[stooq-bulk] Playwright: {label} produced invalid file; trying next method.", flush=True)
    _debug_stooq_download_page(page, symbol, "final_download_timeout_or_invalid")
    raise ValueError(f"Stooq final download did not produce a valid file: {download_path}")


def _pause_stooq_bulk_inspector(page, symbol: str, phase: str) -> None:
    print(
        f"[stooq-bulk] inspector pause ({phase}). Browser is headed; "
        "inspect/solve consent or captcha if needed, then click Resume in Playwright Inspector.",
        flush=True,
    )
    _debug_stooq_download_page(page, symbol, f"inspector_pause_{phase}")
    try:
        page.pause()
    except Exception as exc:
        print(f"[stooq-bulk] inspector pause failed ({phase}): {exc}", flush=True)


def _click_stooq_listing_link(link) -> None:
    try:
        link.click(timeout=5000, force=True)
    except Exception:
        link.evaluate("el => el.click()")


def _download_stooq_via_listing_captcha_flow(
    page,
    url: str,
    listing_url: str,
    link_selector: str | None,
    download_path: Path,
    expect_zip: bool,
    symbol: str,
    interactive_captcha: bool,
) -> Path:
    print("[stooq-bulk] Playwright: using listing -> captcha -> listing download flow.", flush=True)
    page.goto(listing_url, wait_until="domcontentloaded", timeout=30000)
    _accept_stooq_consent_for_bulk(page, "listing-before-first-click")
    link = _find_stooq_bulk_listing_link(page, link_selector)
    if link is None:
        _debug_stooq_download_links(page)
        _debug_stooq_download_page(page, symbol, "listing_link_missing_first_click")
        raise ValueError("Stooq PL listing link d_pl_txt not found")

    print("[stooq-bulk] Playwright: first click on d_pl_txt listing link (expect captcha or immediate download).", flush=True)
    try:
        with page.expect_download(timeout=7000) as download_info:
            _click_stooq_listing_link(link)
        download = download_info.value
        if _save_playwright_download(download, download_path, expect_zip, "first listing click"):
            return download_path
        try:
            download_path.unlink()
        except OSError:
            pass
        print("[stooq-bulk] first listing click downloaded invalid file; continuing to captcha gate.", flush=True)
    except Exception as exc:
        print(f"[stooq-bulk] first listing click did not download directly ({exc}); waiting for captcha gate.", flush=True)
        _wait_for_stooq_download_gate_after_click(page, symbol)

    if interactive_captcha:
        _pause_stooq_bulk_inspector(page, symbol, "before_captcha_solver")
    captcha_solved = _solve_stooq_download_captcha(page, symbol)
    if not captcha_solved and interactive_captcha:
        _pause_stooq_bulk_inspector(page, symbol, "captcha_solver_failed")
        _accept_stooq_consent_for_bulk(page, "after-manual-inspector")
        captcha_solved = _stooq_download_link_ready(page)
        if not captcha_solved and (
            _stooq_captcha_image_locator(page) is not None
            or _stooq_captcha_input_locator(page) is not None
        ):
            print("[stooq-bulk] retrying captcha solver after inspector pause...", flush=True)
            captcha_solved = _solve_stooq_download_captcha(page, symbol)
    if not captcha_solved:
        _debug_stooq_download_page(page, symbol, "captcha_not_solved")
        raise ValueError("Stooq download captcha could not be solved")

    print("[stooq-bulk] captcha accepted; refreshing listing page before final d_pl_txt click.", flush=True)
    page.goto(listing_url, wait_until="domcontentloaded", timeout=30000)
    _accept_stooq_consent_for_bulk(page, "listing-before-final-click")
    link = _find_stooq_bulk_listing_link(page, link_selector)
    if link is None:
        _debug_stooq_download_links(page)
        _debug_stooq_download_page(page, symbol, "listing_link_missing_final_click")
        raise ValueError("Stooq PL listing link d_pl_txt not found after captcha")

    if interactive_captcha:
        _pause_stooq_bulk_inspector(page, symbol, "before_final_listing_click")
    print("[stooq-bulk] Playwright: final click on d_pl_txt listing link; expecting ZIP download...", flush=True)
    with page.expect_download(timeout=180000) as download_info:
        _click_stooq_listing_link(link)
    download = download_info.value
    if not _save_playwright_download(download, download_path, expect_zip, "final listing click"):
        _debug_stooq_download_page(page, symbol, "invalid_final_listing_download")
        raise ValueError(f"Downloaded file did not match expected type: {download_path}")
    return download_path


def download_stooq_file_with_playwright(
    url: str,
    download_path: Path,
    symbol: str = "stooq_bulk",
    *,
    expect_zip: bool = False,
    listing_url: str | None = None,
    link_selector: str | None = None,
    interactive_captcha: bool = False,
) -> Path:
    """Download a Stooq file, solving Stooq's simple captcha challenge if shown."""
    download_path = Path(download_path)
    download_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[stooq-bulk] launching Playwright downloader: url={url}", flush=True)
    if interactive_captcha:
        print("[stooq-bulk] inspector mode enabled: launching headed browser.", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not interactive_captcha, slow_mo=150 if interactive_captcha else 0)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            if listing_url:
                return _download_stooq_via_listing_captcha_flow(
                    page,
                    url,
                    listing_url,
                    link_selector,
                    download_path,
                    expect_zip,
                    symbol,
                    interactive_captcha,
                )

            try:
                print("[stooq-bulk] Playwright: trying immediate download without captcha...", flush=True)
                with page.expect_download(timeout=15000) as download_info:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                download = download_info.value
                print("[stooq-bulk] Playwright: immediate download started.", flush=True)
                if _save_playwright_download(download, download_path, expect_zip, "immediate download"):
                    return download_path
                print(
                    "[stooq-bulk] Playwright: immediate download was not the expected file; "
                    "opening Stooq page/captcha flow...",
                    flush=True,
                )
                try:
                    download_path.unlink()
                except OSError:
                    pass
            except Exception as direct_exc:
                print(
                    f"[stooq-bulk] Playwright: immediate download not available "
                    f"({direct_exc}); opening Stooq page/captcha flow...",
                    flush=True,
                )

            gated_download = _open_stooq_download_gate(page, url, listing_url, link_selector)
            if gated_download is not None:
                if _save_playwright_download(gated_download, download_path, expect_zip, "listing download"):
                    return download_path
                print(
                    "[stooq-bulk] Playwright: listing download was not the expected file; "
                    "continuing with captcha gate...",
                    flush=True,
                )
                try:
                    download_path.unlink()
                except OSError:
                    pass

            if interactive_captcha:
                _pause_stooq_bulk_inspector(page, symbol, "before_captcha_solver")
            captcha_solved = _solve_stooq_download_captcha(page, symbol)
            if not captcha_solved and interactive_captcha:
                _pause_stooq_bulk_inspector(page, symbol, "captcha_solver_failed")
                _accept_stooq_consent_for_bulk(page, "after-manual-inspector")
                captcha_solved = _stooq_download_link_ready(page)
                if not captcha_solved and (_stooq_captcha_image_locator(page) is not None or _stooq_captcha_input_locator(page) is not None):
                    print("[stooq-bulk] retrying captcha solver after inspector pause...", flush=True)
                    captcha_solved = _solve_stooq_download_captcha(page, symbol)
            if not captcha_solved:
                _debug_stooq_download_page(page, symbol, "captcha_not_solved")
                raise ValueError("Stooq download captcha could not be solved")
            link = _stooq_download_link_locator(page, require_visible=True)
            if link is None:
                _debug_stooq_download_page(page, symbol, "download_link_missing_after_captcha")
                raise ValueError("Stooq download link #cpt_gh not found after captcha approval")
            if interactive_captcha:
                _pause_stooq_bulk_inspector(page, symbol, "before_final_download")
            print("[stooq-bulk] Playwright: Stooq Download file link is ready; starting final download attempts...", flush=True)
            return _download_from_stooq_ready_gate(page, url, link, download_path, expect_zip, symbol)
        finally:
            context.close()
            browser.close()
            print("[stooq-bulk] Playwright downloader closed.", flush=True)


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
            print(f"[stooq-web] captcha screenshot saved: {raw_path}", flush=True)
            if not _preprocess_stooq_captcha_image(raw_path, cleaned_path):
                print("[stooq-web] captcha image found, but cv2/numpy preprocessing is unavailable or failed.", flush=True)
                return False
            code, engine = _ocr_stooq_captcha(cleaned_path)
            print(
                f"[stooq-web] captcha OCR attempt {attempt}/{max_attempts}: "
                f"engine={engine or '-'} code_len={len(code)}",
                flush=True,
            )
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
            print("[stooq-web] captcha code filled; clicking approve...", flush=True)
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
