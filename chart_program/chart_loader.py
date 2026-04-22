from __future__ import annotations

from pathlib import Path

import pandas as pd


DATA_DIR_BY_INSTRUMENT = {
    "stock": Path("data/stocks"),
    "commodity": Path("data/commodities"),
    "forex": Path("data/forex"),
}


def _sanitize_symbol_for_filename(symbol: str) -> str:
    return symbol.replace("/", "").replace(".", "_").upper()


def _stooq_symbol(symbol: str, instrument_type: str) -> str:
    cleaned = symbol.strip().lower().replace("/", "")
    if instrument_type == "stock" and "." in symbol:
        left, right = symbol.lower().split(".", 1)
        return f"{left}.{right}"
    return cleaned


def _stooq_download(symbol: str, instrument_type: str) -> pd.DataFrame:
    stooq_symbol = _stooq_symbol(symbol, instrument_type)
    url = f"https://stooq.pl/q/d/l/?s={stooq_symbol}&i=d"

    df = pd.read_csv(url)
    if df.empty or "Date" not in df.columns:
        raise ValueError(f"No daily data returned from Stooq for {symbol} ({stooq_symbol}).")

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return df.sort_values("Date").reset_index(drop=True)


def load_or_update_daily_data(symbol: str, instrument_type: str) -> tuple[pd.DataFrame, Path]:
    data_dir = DATA_DIR_BY_INSTRUMENT[instrument_type]
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / f"{_sanitize_symbol_for_filename(symbol)}.csv"

    remote = _stooq_download(symbol=symbol, instrument_type=instrument_type)

    if csv_path.exists():
        local = pd.read_csv(csv_path)
        if not local.empty and "Date" in local.columns:
            local["Date"] = pd.to_datetime(local["Date"])
            merged = pd.concat([local, remote], ignore_index=True)
            merged = merged.drop_duplicates(subset=["Date"], keep="last")
            merged = merged.sort_values("Date").reset_index(drop=True)
        else:
            merged = remote
    else:
        merged = remote

    merged.to_csv(csv_path, index=False)
    return merged, csv_path
