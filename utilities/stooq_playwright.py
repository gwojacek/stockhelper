from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import json
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


_POLISH_MONTHS = {
    "sty": "01", "lut": "02", "mar": "03", "kwi": "04", "maj": "05", "cze": "06",
    "lip": "07", "sie": "08", "wrz": "09", "paź": "10", "paz": "10", "lis": "11", "gru": "12",
}


def _is_rate_limited_html(html: str) -> bool:
    lowered = (html or '').lower()
    markers = ['przekroczony dzienny limit wywołań strony', 'przepisz powyższy kod']
    return any(m in lowered for m in markers)


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



def _open_page(playwright):
    interactive = os.getenv("STOCKHELPER_STOOQ_INTERACTIVE_CAPTCHA", "0") == "1"
    browser = playwright.chromium.launch(headless=not interactive, slow_mo=150 if interactive else 0)
    page = browser.new_page()
    return browser, page



def _accept_consent_if_present(page, first_page: bool = False) -> None:
    if not first_page:
        return

    selectors = [
        'button.fc-button.fc-cta-consent.fc-primary-button',
        'button[aria-label="Zgadzam się"]',
        '.fc-dialog-container button:has-text("Zgadzam się")',
        'text=Zgadzam się',
    ]

    contexts = [page] + list(page.frames)
    for ctx in contexts:
        for sel in selectors:
            try:
                loc = ctx.locator(sel).first
                loc.wait_for(state='visible', timeout=8000)
                loc.click(timeout=3000, force=True)
                page.wait_for_timeout(700)
                return
            except Exception:
                continue
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
    return page.locator("table tr td").count() > 0



def _handle_captcha_interactive(page, symbol: str, state: dict | None = None) -> bool:
    """Optional interactive captcha handling (opens Playwright inspector).

    Enable by setting env: STOCKHELPER_STOOQ_INTERACTIVE_CAPTCHA=1
    """
    if os.getenv("STOCKHELPER_STOOQ_INTERACTIVE_CAPTCHA", "0") != "1":
        return False
    if state is not None and state.get("done"):
        return False

    if page.locator("text=Przekroczony dzienny limit").count() > 0 or page.locator("text=Przepisz powyższy kod").count() > 0:
        print(f"[stooq-web] CAPTCHA/limit detected for {symbol}. Interactive mode enabled.")
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

def update_stooq_history_with_playwright(symbol: str, csv_path: Path, lookback_days: int = 364, verbose: bool = False) -> pd.DataFrame:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    start_date = (datetime.now(UTC).date() - timedelta(days=lookback_days))

    local = pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    if csv_path.exists():
        local = pd.read_csv(csv_path)
        if "Date" in local.columns:
            local["Date"] = pd.to_datetime(local["Date"], errors="coerce")
            local = local.dropna(subset=["Date"])

    min_required = pd.Timestamp(start_date)
    if not local.empty and local["Date"].min() <= min_required and local["Date"].max().date() >= datetime.now(UTC).date() - timedelta(days=2):
        return local.sort_values("Date").reset_index(drop=True)

    rows: list[dict] = []
    attempted_urls: list[str] = []
    if verbose:
        print(f"[stooq-web] start symbol={symbol} csv={csv_path} lookback_days={lookback_days}")
    with sync_playwright() as p:
        browser, page = _open_page(p)
        page_num = 1
        empty_pages = 0
        interactive_state = {"done": False}
        while page_num <= 30:
            url = f"https://stooq.pl/q/d/?s={symbol.lower()}&i=d&l={page_num}"
            attempted_urls.append(url)
            if verbose:
                print(f"[stooq-web] page={page_num} goto={url}")
            try:
                page.goto(url, wait_until="domcontentloaded")
            except Exception:
                break
            if page_num == 1:
                _accept_consent_if_present(page, first_page=True)
            _handle_captcha_interactive(page, symbol, interactive_state)
            ready = _wait_for_table_or_limit_with_retry(page, retries=3)
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
                shot = _debug_fail_screenshot(symbol, page, suffix="_no_rows")
                if _is_rate_limited_html(page.content()):
                    raise ValueError(f"Stooq rate limit detected (captcha/limit popup). URL: {url} Screenshot: {shot}")
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
                    'Open': row[2].replace(',', '.'),
                    'High': row[3].replace(',', '.'),
                    'Low': row[4].replace(',', '.'),
                    'Close': row[5].replace(',', '.'),
                    'Volume': (row[8] if len(row) > 8 else row[7]).replace(' ', '')
                })
                page_added += 1

            if verbose:
                print(f"[stooq-web] page={page_num} parsed_ok={parsed_ok} added_rows={page_added} oldest={oldest_dt_on_page}")

            if page_added == 0:
                empty_pages += 1
            else:
                empty_pages = 0

            if empty_pages >= 2:
                break
            if oldest_dt_on_page is not None and oldest_dt_on_page < min_required:
                break
            page_num += 1

        browser.close()

    remote = pd.DataFrame(rows)
    if remote.empty:
        raise ValueError(f"Brak danych ze strony Stooq dla {symbol}. Attempted URLs: {attempted_urls}")
    if verbose:
        print(f"[stooq-web] collected_rows={len(remote)}")

    for c in ["Open", "High", "Low", "Close", "Volume"]:
        remote[c] = pd.to_numeric(remote[c], errors="coerce")
    remote = remote.dropna(subset=["Date", "Open", "High", "Low", "Close"])

    if local is None or local.empty:
        merged = remote.copy()
    else:
        merged = pd.concat([local, remote], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)
    merged = merged[merged["Date"] >= min_required]
    merged.to_csv(csv_path, index=False)
    return merged


def debug_stooq_page(symbol: str, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or Path("debug") / "stooq"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{symbol.lower().replace('.', '_')}_debug.json"

    urls = _stooq_history_urls(symbol)
    payload: dict = {"symbol": symbol, "url": urls[0], "attempted_urls": []}
    with sync_playwright() as p:
        browser, page = _open_page(p)
        response = None
        interactive_state = {"done": False}
        for u in urls:
            try:
                response = page.goto(u, wait_until="domcontentloaded")
                _accept_consent_if_present(page, first_page=True)
                _handle_captcha_interactive(page, symbol, interactive_state)
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
