from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


def _csv_path(base_dir: Path, symbol: str) -> Path:
    safe = symbol.replace('/', '').replace('.', '_').upper()
    return base_dir / f"{safe}.csv"


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

        visited = set()
        while True:
            page.wait_for_timeout(500)
            table_rows = page.locator("table#fth1 tbody tr, table tbody tr")
            count = table_rows.count()

            if count == 0:
                extracted = page.evaluate("""() => {
                    const table = document.querySelector('table#fth1') || document.querySelector('table');
                    if (!table) return [];
                    return Array.from(table.querySelectorAll('tr')).map(tr =>
                      Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim())
                    ).filter(r => r.length >= 6);
                }""")
                count = len(extracted)
                for row in extracted:
                    d = row[0]
                    try:
                        dt = pd.to_datetime(d, dayfirst=True, errors='raise')
                    except Exception:
                        continue
                    if dt < min_required:
                        continue
                    rows.append({
                        'Date': dt, 'Open': row[1].replace(',', '.'), 'High': row[2].replace(',', '.'),
                        'Low': row[3].replace(',', '.'), 'Close': row[4].replace(',', '.'), 'Volume': row[5].replace(' ', '')
                    })

            for i in range(count):
                cols = table_rows.nth(i).locator("td")
                if cols.count() < 6:
                    continue
                d = cols.nth(0).inner_text().strip()
                try:
                    dt = pd.to_datetime(d, dayfirst=True, errors="raise")
                except Exception:
                    continue
                if dt < min_required:
                    continue
                rows.append({
                    "Date": dt,
                    "Open": cols.nth(1).inner_text().strip().replace(',', '.'),
                    "High": cols.nth(2).inner_text().strip().replace(',', '.'),
                    "Low": cols.nth(3).inner_text().strip().replace(',', '.'),
                    "Close": cols.nth(4).inner_text().strip().replace(',', '.'),
                    "Volume": cols.nth(5).inner_text().strip().replace(' ', ''),
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
