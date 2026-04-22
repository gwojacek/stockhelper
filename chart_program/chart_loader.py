from __future__ import annotations

from io import StringIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd


DATA_DIR_BY_INSTRUMENT = {
    "stock": Path("data/stocks"),
    "commodity": Path("data/commodities"),
    "forex": Path("data/forex"),
}


def _sanitize_symbol_for_filename(symbol: str) -> str:
    return symbol.replace("/", "").replace(".", "_").upper()


def _stooq_symbol_candidates(symbol: str, instrument_type: str) -> list[str]:
    cleaned = symbol.strip().lower().replace("/", "")

    candidates: list[str] = []
    if instrument_type == "stock":
        if "." in cleaned:
            left, right = cleaned.split(".", 1)
            candidates.append(f"{left}.{right}")
            if right == "wa":
                candidates.append(f"{left}.pl")
            candidates.append(left)
        else:
            candidates.append(cleaned)
            candidates.append(f"{cleaned}.pl")
    else:
        candidates.append(cleaned)

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _download_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_stooq_csv_text(csv_text: str) -> pd.DataFrame:
    lines = csv_text.splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith("Date,")), None)
    if header_index is None:
        raise ValueError("Stooq response does not contain expected CSV header.")

    normalized = "\n".join(lines[header_index:])
    df = pd.read_csv(StringIO(normalized), on_bad_lines="skip")

    required_columns = {"Date", "Open", "High", "Low", "Close"}
    if not required_columns.issubset(df.columns):
        raise ValueError("CSV is missing required OHLC columns.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    return df.sort_values("Date").reset_index(drop=True)


def _stooq_download(symbol: str, instrument_type: str) -> pd.DataFrame:
    errors: list[str] = []
    for candidate in _stooq_symbol_candidates(symbol, instrument_type):
        url = f"https://stooq.pl/q/d/l/?s={candidate}&i=d"
        try:
            text = _download_text(url)
            df = _parse_stooq_csv_text(text)
            if not df.empty:
                return df
            errors.append(f"{candidate}: empty data")
        except (URLError, ValueError, pd.errors.ParserError) as exc:
            errors.append(f"{candidate}: {exc}")

    raise ValueError(f"No daily data returned from Stooq for {symbol}. Tried: {' | '.join(errors)}")


def load_or_update_daily_data(symbol: str, instrument_type: str) -> tuple[pd.DataFrame, Path]:
    data_dir = DATA_DIR_BY_INSTRUMENT[instrument_type]
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / f"{_sanitize_symbol_for_filename(symbol)}.csv"

    local = None
    if csv_path.exists():
        local = pd.read_csv(csv_path)
        if not local.empty and "Date" in local.columns:
            local["Date"] = pd.to_datetime(local["Date"], errors="coerce")
            local = local.dropna(subset=["Date"])
        else:
            local = None

    try:
        remote = _stooq_download(symbol=symbol, instrument_type=instrument_type)
    except ValueError:
        if local is not None and not local.empty:
            return local.sort_values("Date").reset_index(drop=True), csv_path
        raise

    if local is not None and not local.empty:
        merged = pd.concat([local, remote], ignore_index=True)
        merged = merged.drop_duplicates(subset=["Date"], keep="last")
        merged = merged.sort_values("Date").reset_index(drop=True)
    else:
        merged = remote

    merged.to_csv(csv_path, index=False)
    return merged, csv_path
