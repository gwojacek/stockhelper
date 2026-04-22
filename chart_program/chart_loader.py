from __future__ import annotations

from io import StringIO
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


DATA_DIR_BY_INSTRUMENT = {
    "stock": Path("data/stocks"),
    "commodity": Path("data/commodities"),
    "forex": Path("data/forex"),
}

COMMODITY_YAHOO_MAP = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "COFFEE": "KC=F",
    "COCOA": "CC=F",
    "SUGAR": "SB=F",
    "WHEAT": "ZW=F",
    "COPPER": "HG=F",
    "CRUDE_OIL": "CL=F",
    "NATURAL_GAS": "NG=F",
}


def _sanitize_symbol_for_filename(symbol: str) -> str:
    return symbol.replace("/", "").replace(".", "_").upper()


def _yahoo_symbol_candidates(symbol: str, instrument_type: str) -> list[str]:
    cleaned = symbol.strip().upper()
    candidates: list[str] = []

    if instrument_type == "forex":
        compact = cleaned.replace("/", "")
        if len(compact) >= 6:
            candidates.append(f"{compact[:6]}=X")
        candidates.append(f"{compact}=X")
    elif instrument_type == "commodity":
        mapped = COMMODITY_YAHOO_MAP.get(cleaned)
        if mapped:
            candidates.append(mapped)
        candidates.append(cleaned)
    else:
        candidates.append(cleaned)

    deduped = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _yahoo_download(symbol: str, instrument_type: str) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ValueError("yfinance is not installed") from exc

    errors = []
    for candidate in _yahoo_symbol_candidates(symbol, instrument_type):
        try:
            hist = yf.Ticker(candidate).history(period="max", interval="1d", auto_adjust=False)
            if hist is None or hist.empty:
                errors.append(f"{candidate}: empty data")
                continue

            df = hist.reset_index()
            rename_map = {
                "Datetime": "Date",
                "date": "Date",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Volume": "Volume",
            }
            df = df.rename(columns=rename_map)
            if "Date" not in df.columns:
                if df.columns.size > 0:
                    df = df.rename(columns={df.columns[0]: "Date"})

            required_columns = {"Date", "Open", "High", "Low", "Close"}
            if not required_columns.issubset(df.columns):
                errors.append(f"{candidate}: missing OHLC columns")
                continue

            df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
            df = df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
            if df.empty:
                errors.append(f"{candidate}: no valid OHLC rows")
                continue

            return _last_year_only(df)
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")

    raise ValueError(f"No daily data returned from Yahoo for {symbol}. Tried: {' | '.join(errors)}")


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
    header_index = None
    separator = ","
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        line_lower = line.lower()
        if line_lower.startswith("date,open,high,low,close"):
            header_index = i
            separator = ","
            break
        if line_lower.startswith("date;open;high;low;close"):
            header_index = i
            separator = ";"
            break

    if header_index is None:
        raise ValueError("Stooq response does not contain expected CSV header.")

    normalized = "\n".join(lines[header_index:])
    df = pd.read_csv(StringIO(normalized), sep=separator, on_bad_lines="skip")

    required_columns = {"Date", "Open", "High", "Low", "Close"}
    if not required_columns.issubset(df.columns):
        raise ValueError("CSV is missing required OHLC columns.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    return _last_year_only(df)


def _stooq_url(symbol: str, api_key: str | None = None, param_name: str | None = None, domain: str = "stooq.pl") -> str:
    query = {"s": symbol, "i": "d"}
    if api_key and param_name:
        query[param_name] = api_key
    return f"https://{domain}/q/d/l/?{urlencode(query)}"


def _stooq_download(symbol: str, instrument_type: str, api_key: str | None = None) -> pd.DataFrame:
    errors: list[str] = []
    for candidate in _stooq_symbol_candidates(symbol, instrument_type):
        urls = [
            _stooq_url(candidate, domain="stooq.pl"),
            _stooq_url(candidate, domain="stooq.com"),
        ]
        if api_key:
            urls.extend(
                [
                    _stooq_url(candidate, api_key=api_key, param_name="apikey", domain="stooq.pl"),
                    _stooq_url(candidate, api_key=api_key, param_name="api_key", domain="stooq.pl"),
                    _stooq_url(candidate, api_key=api_key, param_name="apikey", domain="stooq.com"),
                    _stooq_url(candidate, api_key=api_key, param_name="api_key", domain="stooq.com"),
                ]
            )

        for url in urls:
            try:
                text = _download_text(url)
                df = _parse_stooq_csv_text(text)
                if not df.empty:
                    return df
                errors.append(f"{candidate}: empty data from {url}")
            except (URLError, ValueError, pd.errors.ParserError) as exc:
                errors.append(f"{candidate}: {exc}")

    raise ValueError(f"No daily data returned from Stooq for {symbol}. Tried: {' | '.join(errors)}")



def _last_year_only(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    latest = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(latest):
        return df
    cutoff = latest - pd.Timedelta(days=370)
    trimmed = df[df["Date"] >= cutoff]
    return trimmed.sort_values("Date").reset_index(drop=True)

def _download_remote(symbol: str, instrument_type: str, api_key: str | None, data_source: str) -> pd.DataFrame:
    if data_source == "yahoo":
        return _yahoo_download(symbol, instrument_type)
    if data_source == "stooq":
        return _stooq_download(symbol, instrument_type, api_key=api_key)

    yahoo_error = None
    try:
        return _yahoo_download(symbol, instrument_type)
    except ValueError as exc:
        yahoo_error = exc

    try:
        return _stooq_download(symbol, instrument_type, api_key=api_key)
    except ValueError as stooq_exc:
        raise ValueError(f"Yahoo failed: {yahoo_error} ; Stooq failed: {stooq_exc}") from stooq_exc


def load_or_update_daily_data(
    symbol: str,
    instrument_type: str,
    persist: bool = True,
    api_key: str | None = None,
    data_source: str = "auto",
) -> tuple[pd.DataFrame, Path]:
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
        remote = _download_remote(symbol=symbol, instrument_type=instrument_type, api_key=api_key, data_source=data_source)
    except ValueError:
        if local is not None and not local.empty:
            return _last_year_only(local), csv_path
        raise

    if local is not None and not local.empty:
        merged = pd.concat([local, remote], ignore_index=True)
        merged = merged.drop_duplicates(subset=["Date"], keep="last")
        merged = merged.sort_values("Date").reset_index(drop=True)
    else:
        merged = remote

    merged = _last_year_only(merged)

    if persist:
        merged.to_csv(csv_path, index=False)
    return merged, csv_path
