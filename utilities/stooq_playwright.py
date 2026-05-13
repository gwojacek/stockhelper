from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


_POLISH_MONTHS = {
    "sty": "01", "lut": "02", "mar": "03", "kwi": "04", "maj": "05", "cze": "06",
    "lip": "07", "sie": "08", "wrz": "09", "paź": "10", "paz": "10", "lis": "11", "gru": "12",
}


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




def _extract_rows_from_frame(frame) -> list[list[str]]:
    try:
        return frame.evaluate("""() => {
            const table = document.querySelector('table#fth1') || document.querySelector('table');
            if (!table) return [];
            return Array.from(table.querySelectorAll('tr')).map(tr =>
              Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
            ).filter(r => r.length >= 6);
        }""")
    except Exception:
        return []

def update_stooq_history_with_playwright(symbol: str, csv_path: Path, lookback_days: int = 364) -> pd.DataFrame:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    start_date = (datetime.now(UTC).date() - timedelta(days=lookback_days))

    local = pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    if csv_path.exists():
        local = pd.read_csv(csv_path)
        if "Date" in local.columns:
            local["Date"] = pd.to_datetime(local["Date"], errors="coerce")
            local = local.dropna(subset=["Date"])

    min_required = pd.Timestamp(start_date)
    if not local.empty and local["Date"].min() <= min_required and local["Date"].max().date() >= datetime.now(UTC).date() - timedelta(days=3):
        return local.sort_values("Date").reset_index(drop=True)

    rows: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"https://stooq.pl/q/d/?s={symbol.lower()}&i=d", wait_until="domcontentloaded")
        try:
            page.wait_for_selector("table#fth1", timeout=6000)
        except Exception:
            pass

        visited = set()
        while True:
            page.wait_for_timeout(500)
            table_rows = page.locator("table#fth1 tbody tr, table tbody tr")
            count = table_rows.count()

            if count == 0:
                extracted = _extract_rows_from_frame(page)
                if not extracted:
                    for fr in page.frames:
                        extracted = _extract_rows_from_frame(fr)
                        if extracted:
                            break
                count = len(extracted)
                for row in extracted:
                    date_idx = 1 if row and row[0].isdigit() and len(row) >= 8 else 0
                    d = row[date_idx]
                    try:
                        dt = _parse_stooq_date(d)
                    except Exception:
                        continue
                    if dt < min_required:
                        continue
                    rows.append({
                        'Date': dt, 'Open': row[1 + date_idx].replace(',', '.'), 'High': row[2 + date_idx].replace(',', '.'),
                        'Low': row[3 + date_idx].replace(',', '.'), 'Close': row[4 + date_idx].replace(',', '.'), 'Volume': row[6 + date_idx].replace(' ', '')
                    })

            for i in range(count):
                cols = table_rows.nth(i).locator("td")
                if cols.count() < 6:
                    continue
                d = cols.nth(0).inner_text().strip()
                try:
                    dt = _parse_stooq_date(d)
                except Exception:
                    continue
                if dt < min_required:
                    continue
                offset = 1 if cols.nth(0).inner_text().strip().isdigit() else 0
                rows.append({
                    "Date": dt,
                    "Open": cols.nth(1 + offset).inner_text().strip().replace(',', '.'),
                    "High": cols.nth(2 + offset).inner_text().strip().replace(',', '.'),
                    "Low": cols.nth(3 + offset).inner_text().strip().replace(',', '.'),
                    "Close": cols.nth(4 + offset).inner_text().strip().replace(',', '.'),
                    "Volume": cols.nth(6 + offset).inner_text().strip().replace(' ', ''),
                })

            key = page.url
            if key in visited:
                break
            visited.add(key)

            next_link = page.locator("a:has-text('następna')")
            if next_link.count() == 0:
                break
            next_link.first.click()

        browser.close()

    remote = pd.DataFrame(rows)
    if remote.empty:
        raise ValueError(f"Brak danych ze strony Stooq dla {symbol}")

    for c in ["Open", "High", "Low", "Close", "Volume"]:
        remote[c] = pd.to_numeric(remote[c], errors="coerce")
    remote = remote.dropna(subset=["Date", "Open", "High", "Low", "Close"])

    merged = pd.concat([local, remote], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)
    merged = merged[merged["Date"] >= min_required]
    merged.to_csv(csv_path, index=False)
    return merged


def debug_stooq_page(symbol: str, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or Path("debug") / "stooq"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{symbol.lower().replace('.', '_')}_debug.json"

    payload: dict = {"symbol": symbol, "url": f"https://stooq.pl/q/d/?s={symbol.lower()}&i=d"}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(payload["url"], wait_until="domcontentloaded")
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
        browser.close()

    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file
