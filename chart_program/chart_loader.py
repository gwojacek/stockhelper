from __future__ import annotations

from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


STOOQ_DEFAULT_API_KEY = "x1s2H9UeqW6t3oJR7gDpm8fwPnudBjFS"

DATA_DIR_BY_INSTRUMENT = {
    "stock": Path("data/stocks"),
    "commodity": Path("data/commodities"),
    "forex": Path("data/forex"),
}

COMMODITY_YAHOO_MAP = {
    "GOLD": "GC=F",
    "XAUUSD": "GC=F",
    "XAU/USD": "GC=F",
    "SILVER": "SI=F",
    "XAGUSD": "SI=F",
    "XAG/USD": "SI=F",
    "COFFEE": "KC=F",
    "COCOA": "CC=F",
    "SUGAR": "SB=F",
    "WHEAT": "ZW=F",
    "CORN": "ZC=F",
    "SOYBEAN": "ZS=F",
    "SOYOIL": "ZL=F",
    "COPPER": "HG=F",
    "ALUMINIUM": "ALI=F",
    "PLATINUM": "PL=F",
    "PALLADIUM": "PA=F",
    "WTI": "CL=F",
    "OIL.WTI": "CL=F",
    "OIL": "BZ=F",
    "CRUDE_OIL": "CL=F",
    "NATURAL_GAS": "NG=F",
    "BTC": "BTC-USD",
    "DOGE": "DOGE-USD",
    "BRACOMP": "^BVP",
    "US500": "^SPX",
    "MEXCOMP": "^IPC",
    "VIX": "^VIX",
    "US30": "^DJI",
    "US100": "^NDX",
    "HK.CASH": "^HSI",
    "SG20CASH": "^STI",
    "AU200.CASH": "^AORD",
    "CHN.CASH": "000001.SS",
    "JP225": "^NKX",
    "NKX": "^NKX",
    "W20": "WIG20",
    "WIG20": "WIG20",
    "UK100": "^FTSE",
    "ITA40": "FTSEMIB.MI",
    "DE40": "^GDAXI",
    "DAX": "^GDAXI",
    "FRA40": "^FCHI",
    "CAC": "^FCHI",
    "NED25": "^AEX",
    "AEX": "^AEX",
    "SUI20": "^SSMI",
    "SMI": "^SSMI",
    "SPA35": "^IBEX",
    "IBEX": "^IBEX",
    "EU50": "^STOXX50E",
}

COMMODITY_STOOQ_MAP = {
    "GOLD": "xauusd",
    "XAUUSD": "xauusd",
    "XAU/USD": "xauusd",
    "SILVER": "xagusd",
    "XAGUSD": "xagusd",
    "XAG/USD": "xagusd",
    "PLATINUM": "pl.f",
    "PALLADIUM": "xpdusd",
    "XPDUSD": "xpdusd",
    "XPD/USD": "xpdusd",
    "COFFEE": "kc.f",
    "COCOA": "cc.f",
    "SUGAR": "sb.f",
    "COTTON": "ct.f",
    "WHEAT": "zw.f",
    "CORN": "zc.f",
    "SOYBEAN": "zs.f",
    "SOYBEAN_OIL": "zl.f",
    "SOYOIL": "zl.f",
    "GASOLINE": "rb.f",
    "LSGASOIL": "qs.f",
    "WTI": "cl.f",
    "OIL.WTI": "cl.f",
    "OIL": "cb.f",
    "ALUMINIUM": "ali.f",
    "NICKEL": "ni.f",
    "ZINC": "zn.f",
    "CRUDE_OIL_BRENT": "cb.f",
    "NATURAL_GAS": "ng.f",
    "BRACOMP": "^bvp",
    "US500": "^spx",
    "MEXCOMP": "^ipc",
    "VIX": "vi.c",
    "US30": "^dji",
    "US100": "^ndx",
    "HK.CASH": "^hsi",
    "SG20CASH": "^sti",
    "AU200.CASH": "^aor",
    "CHN.CASH": "0el.c",
    "JP225": "^nkx",
    "NKX": "^nkx",
    "W20": "wig20",
    "WIG20": "wig20",
    "UK100": "^ukx",
    "ITA40": "^fmib",
    "DE40": "^dax",
    "DAX": "^dax",
    "FRA40": "^cac",
    "CAC": "^cac",
    "NED25": "^aex",
    "AEX": "^aex",
    "SUI20": "^smi",
    "SMI": "^smi",
    "SPA35": "^ibex",
    "IBEX": "^ibex",
    "EU50": "fx.f",
}

COMMODITY_DISPLAY_NAME = {
    "GOLD": "Gold",
    "SILVER": "Silver",
    "PLATINUM": "Platinum",
    "PALLADIUM": "Palladium",
    "COFFEE": "Coffee",
    "COCOA": "Cocoa",
    "SUGAR": "Sugar",
    "COTTON": "Cotton",
    "WHEAT": "Wheat",
    "CORN": "Corn",
    "SOYBEAN": "Soybean",
    "SOYOIL": "Soy Oil",
    "SOYBEAN_OIL": "Soybean Oil",
    "GASOLINE": "Gasoline",
    "LSGASOIL": "LS Gasoil",
    "WTI": "WTI Oil",
    "OIL.WTI": "WTI Oil",
    "OIL": "Brent Oil",
    "ALUMINIUM": "Aluminium",
    "NICKEL": "Nickel",
    "ZINC": "Zinc",
    "CRUDE_OIL_BRENT": "Crude Oil Brent",
    "NATURAL_GAS": "Natural Gas",
    "BTC": "Bitcoin",
    "DOGE": "Dogecoin",
}


def _humanize_symbol(symbol: str) -> str:
    raw = (symbol or "").strip().replace("^", "")
    if not raw:
        return ""
    cleaned = raw.replace("_", " ").replace(".", " ").replace("/", " ").replace("-", " ")
    parts = [p for p in cleaned.split() if p]
    if not parts:
        return raw.upper()
    return " ".join(part.upper() if part.isupper() and len(part) <= 4 else part.title() for part in parts)


def _best_effort_display_name(symbol: str, instrument_type: str, source_symbol: str | None) -> str | None:
    if instrument_type == "stock":
        return None
    try:
        import yfinance as yf
    except Exception:
        return None

    lookup_candidates: list[str] = []
    normalized_symbol = (symbol or "").strip().upper()
    normalized_source = (source_symbol or "").strip().upper()
    if normalized_source:
        lookup_candidates.append(normalized_source)
    mapped = COMMODITY_YAHOO_MAP.get(normalized_symbol)
    if mapped:
        lookup_candidates.append(mapped)
    if normalized_symbol:
        lookup_candidates.append(normalized_symbol)

    seen = set()
    for candidate in lookup_candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            ticker = yf.Ticker(candidate)
            info = ticker.info if hasattr(ticker, "info") else {}
            name = (info.get("longName") or info.get("shortName") or "").strip()
            if name:
                return name
        except Exception:
            continue
    return None

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
        if cleaned.endswith(".US"):
            candidates.append(cleaned[:-3])
        if cleaned.endswith(".F") and "=" not in cleaned:
            candidates.append(cleaned.replace(".F", "=F"))
        candidates.append(cleaned)
    else:
        if cleaned.endswith(".US"):
            candidates.append(cleaned[:-3])
        candidates.append(cleaned)

    deduped = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _yahoo_download(symbol: str, instrument_type: str) -> tuple[pd.DataFrame, str, str | None]:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ValueError("yfinance is not installed") from exc

    errors = []
    for candidate in _yahoo_symbol_candidates(symbol, instrument_type):
        try:
            ticker = yf.Ticker(candidate)
            with StringIO() as sink, redirect_stderr(sink), redirect_stdout(sink):
                hist = ticker.history(period="max", interval="1d", auto_adjust=False)
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

            display_name = None
            if instrument_type == "stock":
                try:
                    info = ticker.info if hasattr(ticker, "info") else {}
                    display_name = info.get("longName") or info.get("shortName")
                except Exception:
                    display_name = None
            return _last_year_only(df), candidate, display_name
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
            # Prefer Warsaw listing symbol first for local stock slugs (e.g. "cog" -> "cog.pl").
            candidates.append(f"{cleaned}.pl")
            candidates.append(cleaned)
    elif instrument_type == "commodity":
        mapped = COMMODITY_STOOQ_MAP.get(symbol.strip().upper())
        if mapped:
            candidates.append(mapped)
        if cleaned.endswith(".us"):
            candidates.append(cleaned[:-3])
        candidates.append(cleaned)
        if cleaned.isalpha():
            candidates.append(f"{cleaned}.f")
    else:
        candidates.append(cleaned)

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _download_text(url: str) -> str:
    with urlopen(url, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_stooq_csv_text(csv_text: str) -> pd.DataFrame:
    lines = csv_text.splitlines()
    header_index = None
    separator = ","
    for i, raw_line in enumerate(lines):
        line = raw_line.strip().lstrip("﻿")
        line_lower = line.lower()
        if line_lower.startswith("date,open,high,low,close"):
            header_index = i
            separator = ","
            break
        if line_lower.startswith("date;open;high;low;close"):
            header_index = i
            separator = ";"
            break
        if line_lower.startswith("data,otwarcie,najwyzszy,najnizszy,zamkniecie"):
            header_index = i
            separator = ","
            break
        if line_lower.startswith("data;otwarcie;najwyzszy;najnizszy;zamkniecie"):
            header_index = i
            separator = ";"
            break

    if header_index is None:
        preview = " | ".join(line.strip() for line in lines[:5])
        raise ValueError(f"Stooq response does not contain expected CSV header. Preview: {preview[:400]}")

    normalized = "\n".join(lines[header_index:])
    df = pd.read_csv(StringIO(normalized), sep=separator, on_bad_lines="skip")

    df = df.rename(columns={
        "Data": "Date",
        "Otwarcie": "Open",
        "Najwyzszy": "High",
        "Najnizszy": "Low",
        "Zamkniecie": "Close",
        "Wolumen": "Volume",
    })
    df.columns = [str(c).strip().title() for c in df.columns]
    required_columns = {"Date", "Open", "High", "Low", "Close"}
    if not required_columns.issubset(df.columns):
        raise ValueError("CSV is missing required OHLC columns.")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    return _last_year_only(df)

def _stooq_live_quote_url(symbol: str, domain: str = "stooq.pl") -> str:
    query = {"s": symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"}
    return f"https://{domain}/q/l/?{urlencode(query)}"


def _merge_stooq_current_quote(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    url = _stooq_live_quote_url(symbol)
    text = _download_text(url)
    quote_df = pd.read_csv(StringIO(text), sep=",", on_bad_lines="skip")
    quote_df.columns = [str(c).strip().title() for c in quote_df.columns]
    required = {"Date", "Open", "High", "Low", "Close"}
    if not required.issubset(set(quote_df.columns)) or quote_df.empty:
        return df

    quote_row = quote_df.iloc[0].copy()
    quote_date = pd.to_datetime(quote_row.get("Date"), errors="coerce")
    if pd.isna(quote_date):
        return df

    live_row = {
        "Date": quote_date,
        "Open": pd.to_numeric(quote_row.get("Open"), errors="coerce"),
        "High": pd.to_numeric(quote_row.get("High"), errors="coerce"),
        "Low": pd.to_numeric(quote_row.get("Low"), errors="coerce"),
        "Close": pd.to_numeric(quote_row.get("Close"), errors="coerce"),
    }
    if any(pd.isna(live_row[c]) for c in ["Open", "High", "Low", "Close"]):
        return df

    if "Volume" in df.columns:
        live_row["Volume"] = pd.to_numeric(quote_row.get("Volume"), errors="coerce")

    result = df.copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    result = result[result["Date"].dt.date != quote_date.date()]
    result = pd.concat([result, pd.DataFrame([live_row])], ignore_index=True)
    result = result.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    return _last_year_only(result)


def _stooq_url(symbol: str, api_key: str | None = None, param_name: str | None = None, domain: str = "stooq.pl") -> str:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=364)
    query = {"s": symbol, "i": "d", "d1": start.strftime("%Y%m%d"), "d2": end.strftime("%Y%m%d")}
    if api_key and param_name:
        query[param_name] = api_key
    return f"https://{domain}/q/d/l/?{urlencode(query)}"


def _stooq_download(symbol: str, instrument_type: str, api_key: str | None = None) -> tuple[pd.DataFrame, str]:
    errors: list[str] = []
    for candidate in _stooq_symbol_candidates(symbol, instrument_type):
        effective_api_key = api_key or STOOQ_DEFAULT_API_KEY
        url = _stooq_url(candidate, api_key=effective_api_key, param_name="apikey", domain="stooq.pl")

        try:
            text = _download_text(url)
            df = _parse_stooq_csv_text(text)
            if not df.empty:
                try:
                    df = _merge_stooq_current_quote(df, candidate)
                except Exception:
                    pass
                return df, candidate
            errors.append(f"{candidate}: empty data from {url}")
        except (URLError, ValueError, pd.errors.ParserError) as exc:
            errors.append(f"{candidate}: {exc} | url={url}")

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

def _download_remote(symbol: str, instrument_type: str, api_key: str | None, data_source: str) -> tuple[pd.DataFrame, str, str, str | None, str | None]:
    if data_source == "yahoo":
        df, candidate, display_name = _yahoo_download(symbol, instrument_type)
        return df, "yahoo", candidate, display_name, "Yahoo forced by --data-source yahoo."
    if data_source == "stooq":
        df, candidate = _stooq_download(symbol, instrument_type, api_key=None if instrument_type == "commodity" else api_key)
        return df, "stooq", candidate, None, "Stooq forced by --data-source stooq."

    primary_error = None
    try:
        df, candidate = _stooq_download(symbol, instrument_type, api_key=None if instrument_type == "commodity" else api_key)
        return df, "stooq", candidate, None, f"Stooq succeeded as primary source for {instrument_type}."
    except ValueError as exc:
        primary_error = exc

    try:
        df, candidate, display_name = _yahoo_download(symbol, instrument_type)
        return df, "yahoo", candidate, display_name, f"Stooq failed, fallback to Yahoo: {primary_error}"
    except ValueError as secondary_exc:
        raise ValueError(f"Stooq failed: {primary_error} ; Yahoo failed: {secondary_exc}") from secondary_exc


def load_or_update_daily_data(
    symbol: str,
    instrument_type: str,
    persist: bool = True,
    api_key: str | None = None,
    data_source: str = "auto",
) -> tuple[pd.DataFrame, Path, dict]:
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
        remote, source, source_symbol, source_name, fallback_reason = _download_remote(symbol=symbol, instrument_type=instrument_type, api_key=api_key, data_source=data_source)
    except ValueError:
        if local is not None and not local.empty:
            return _last_year_only(local), csv_path, {"source": "cache", "symbol": symbol, "name": symbol.title(), "fallback_reason": "Remote download failed, using local cache."}
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
    display_name = _humanize_symbol(symbol)
    display_symbol = str(source_symbol).upper()
    if instrument_type == "commodity":
        display_name = COMMODITY_DISPLAY_NAME.get(symbol.strip().upper(), _humanize_symbol(symbol))
        enriched_name = source_name or _best_effort_display_name(symbol, instrument_type, source_symbol)
        if enriched_name:
            display_name = enriched_name
        preferred_stooq_symbol = COMMODITY_STOOQ_MAP.get(symbol.strip().upper())
        if preferred_stooq_symbol:
            display_symbol = preferred_stooq_symbol.upper()
    elif instrument_type == "stock":
        display_name = source_name or symbol.upper()
    return merged, csv_path, {"source": source, "symbol": display_symbol, "name": display_name, "fallback_reason": fallback_reason}
