from __future__ import annotations

from io import StringIO
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import os

import pandas as pd

from utilities.stooq_playwright import update_stooq_history_with_playwright

STOOQ_DEFAULT_API_KEY = "FY7eN0urJV3My6FH5LU9COh2qxnP8Kci"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNIFIED_DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR_BY_INSTRUMENT = {
    "stock": UNIFIED_DATA_DIR / "stocks",
    "commodity": UNIFIED_DATA_DIR / "commodities",
    "forex": UNIFIED_DATA_DIR / "forex",
}

# Per-process memo of symbols already refreshed from remote.
# Prevents duplicate remote fetches in one run (e.g. allsearch ichi -> fibo).
_SESSION_REFRESHED_KEYS: set[tuple[str, str, bool]] = set()

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
    "COPPER": "hg.f",
    "ALUMINIUM": "al.f",
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
                if candidate.startswith("^"):
                    lowered = name.lower()
                    trusted_tokens = (
                        "index",
                        "nikkei",
                        "s&p",
                        "dow",
                        "dax",
                        "cac",
                        "ibex",
                        "ftse",
                        "stoxx",
                        "hang seng",
                        "nasdaq",
                        "vix",
                        "wig",
                        "mib",
                        "aex",
                        "smi",
                    )
                    if not any(token in lowered for token in trusted_tokens):
                        continue
                if candidate.startswith("^") and name.endswith(" P"):
                    name = name[:-2].strip()
                return name
        except Exception:
            continue
    return None

def _sanitize_symbol_for_filename(symbol: str) -> str:
    return symbol.replace("/", "").replace(".", "_").upper()


def _storage_symbol_for_csv(symbol: str, instrument_type: str) -> str:
    if instrument_type != "commodity":
        return symbol
    mapped = COMMODITY_STOOQ_MAP.get((symbol or "").strip().upper())
    return str(mapped or symbol)



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


def _stooq_url(
    symbol: str,
    api_key: str | None = None,
    param_name: str | None = None,
    domain: str = "stooq.pl",
    lookback_days: int = 364,
    end_date: datetime | None = None,
) -> str:
    end = (end_date.date() if isinstance(end_date, datetime) else datetime.now(timezone.utc).date())
    start = end - timedelta(days=lookback_days)
    query = {"s": symbol, "i": "d", "d1": start.strftime("%Y%m%d"), "d2": end.strftime("%Y%m%d")}
    if api_key and param_name:
        query[param_name] = api_key
    return f"https://{domain}/q/d/l/?{urlencode(query)}"


def _stooq_download(
    symbol: str,
    instrument_type: str,
    api_key: str | None = None,
    lookback_days: int = 364,
    end_date: datetime | None = None,
) -> tuple[pd.DataFrame, str]:
    errors: list[str] = []
    for candidate in _stooq_symbol_candidates(symbol, instrument_type):
        effective_api_key = api_key or STOOQ_DEFAULT_API_KEY
        url = _stooq_url(candidate, api_key=effective_api_key, param_name="apikey", domain="stooq.pl", lookback_days=lookback_days, end_date=end_date)

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





def _sanitize_ohlc_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename_map = {
        "date": "Date", "Data": "Date", "Datetime": "Date",
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    }
    out = out.rename(columns={c: rename_map.get(c, c) for c in out.columns})
    required = ["Date", "Open", "High", "Low", "Close"]
    if not set(required).issubset(out.columns):
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["Date", "Open", "High", "Low", "Close"])
    out = out.sort_values("Date").drop_duplicates(subset=["Date"], keep="last").reset_index(drop=True)
    return out
def _last_two_years_only(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    latest = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(latest):
        return df
    cutoff = latest - pd.Timedelta(days=740)
    trimmed = df[df["Date"] >= cutoff]
    return trimmed.sort_values("Date").reset_index(drop=True)

def _last_year_only(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    latest = pd.to_datetime(df["Date"], errors="coerce").max()
    if pd.isna(latest):
        return df
    cutoff = latest - pd.Timedelta(days=370)
    trimmed = df[df["Date"] >= cutoff]
    return trimmed.sort_values("Date").reset_index(drop=True)

def _local_csv_has_min_year(csv_path: Path) -> bool:
    """Return True when local CSV exists and contains at least ~1 year span."""
    try:
        if not csv_path.exists():
            return False
        local_df = pd.read_csv(csv_path)
        if local_df.empty or "Date" not in local_df.columns:
            return False
        dts = pd.to_datetime(local_df["Date"], errors="coerce").dropna()
        if dts.empty:
            return False
        latest = dts.max().date()
        oldest = dts.min().date()
        return (latest - oldest).days >= 360
    except Exception:
        return False


def _older_fetch_plan(csv_path: Path, instrument_type: str) -> tuple[int, datetime | None]:
    """When older-data mode is requested, fetch only bounded extra history.

    Non-commodity: if local already covers >=364 days, fetch only 180 older days
    (max target span ~544 days). Otherwise fetch up to 364 older days.
    Commodity keeps legacy 364-day older fetch behavior.
    """
    try:
        if not csv_path.exists():
            return 364, None
        local_df = pd.read_csv(csv_path)
        if local_df.empty or "Date" not in local_df.columns:
            return 364, None
        dts = pd.to_datetime(local_df["Date"], errors="coerce").dropna().sort_values()
        if dts.empty:
            return 364, None
        oldest = dts.min().to_pydatetime()
        newest = dts.max()
        span = int((newest - dts.min()).days)
        if instrument_type != "commodity" and span >= 364:
            target_max = 364 + 180
            remaining = max(0, target_max - span)
            if remaining <= 0:
                return 0, oldest
            return min(180, remaining), oldest
        return 364, oldest
    except Exception:
        return 364, None

def _download_remote(symbol: str, instrument_type: str, api_key: str | None, data_source: str, fetch_older_data: bool = False) -> tuple[pd.DataFrame, str, str, str | None, str | None]:
    def _incremental_lookback_days(csv_path: Path, default_days: int = 364) -> int:
        try:
            if not csv_path.exists():
                return default_days
            local_df = pd.read_csv(csv_path)
            if "Date" not in local_df.columns or local_df.empty:
                return default_days
            latest = pd.to_datetime(local_df["Date"], errors="coerce").max()
            if pd.isna(latest):
                return default_days
            days = (pd.Timestamp.utcnow().tz_localize(None) - latest).days + 14
            return max(30, min(default_days, int(days)))
        except Exception:
            return default_days
    def _older_fetch_anchor(csv_path: Path) -> datetime | None:
        try:
            if not csv_path.exists():
                return None
            local_df = pd.read_csv(csv_path)
            if "Date" not in local_df.columns or local_df.empty:
                return None
            oldest = pd.to_datetime(local_df["Date"], errors="coerce").min()
            if pd.isna(oldest):
                return None
            return oldest.to_pydatetime()
        except Exception:
            return None
    if data_source == "yahoo":
        df, candidate, display_name = _yahoo_download(symbol, instrument_type)
        return df, "yahoo", candidate, display_name, "Yahoo forced by --data-source yahoo."
    csv_path_ref = DATA_DIR_BY_INSTRUMENT[instrument_type] / f"{_sanitize_symbol_for_filename(_storage_symbol_for_csv(symbol, instrument_type))}.csv"
    older_days, older_anchor = _older_fetch_plan(csv_path_ref, instrument_type) if fetch_older_data else (364, None)
    if data_source == "stooq":
        df, candidate = _stooq_download(
            symbol,
            instrument_type,
            api_key=None if instrument_type == "commodity" else api_key,
            lookback_days=older_days if fetch_older_data else 364,
            end_date=older_anchor,
        )
        return df, "stooq", candidate, None, "Stooq forced by --data-source stooq."

    # For literal commodities prefer web scraping first (Stooq history pages are often richer/more reliable than CSV endpoint).
    # Do NOT force web scraping for index-like symbols routed as "commodity" (e.g. US500, DAX, WIG20).
    normalized_symbol = symbol.strip().upper()
    mapped_stooq = COMMODITY_STOOQ_MAP.get(normalized_symbol, "")
    if not mapped_stooq:
        # Scanner may already pass mapped stooq symbols (e.g. "fx.f" instead of "EU50").
        direct = symbol.strip().lower()
        if direct in {str(v).lower() for v in COMMODITY_STOOQ_MAP.values()}:
            mapped_stooq = direct
    is_index_like_commodity_symbol = (
        str(mapped_stooq).startswith("^")
        or str(mapped_stooq).lower() in {"wig20", "vi.c", "0el.c", "fx.f"}
    )
    # Some symbols are unavailable via Stooq CSV API and must use web pages.
    requires_web_even_if_index_like = str(mapped_stooq).lower() in {"fx.f"}
    # Force selected metals to stay on API path (no Playwright fallback).
    force_api_only_symbols = {"xauusd", "xagusd", "xpdusd"}
    is_literal_commodity = (
        instrument_type == "commodity"
        and (normalized_symbol in COMMODITY_STOOQ_MAP or bool(mapped_stooq))
        and (not is_index_like_commodity_symbol or requires_web_even_if_index_like)
        and str(mapped_stooq).lower() not in force_api_only_symbols
    )
    if is_literal_commodity:
        try:
            csv_path = DATA_DIR_BY_INSTRUMENT[instrument_type] / f"{_sanitize_symbol_for_filename(_storage_symbol_for_csv(symbol, instrument_type))}.csv"
            stooq_fetch_symbol = str(mapped_stooq or symbol).lower()
            df = update_stooq_history_with_playwright(
                symbol=stooq_fetch_symbol,
                csv_path=csv_path,
                lookback_days=older_days if fetch_older_data else _incremental_lookback_days(csv_path),
                end_date=_older_fetch_anchor(csv_path) if fetch_older_data else None,
                verbose=os.getenv("STOCKHELPER_STOOQ_DEBUG", "0") == "1",
                interactive_captcha=True,
            )
            return df, "stooq_web", symbol, None, "Stooq web used as primary source for commodity."
        except Exception as web_exc:
            raise ValueError(f"Stooq web failed: {web_exc}") from web_exc

    primary_error = None
    try:
        df, candidate = _stooq_download(
            symbol,
            instrument_type,
            api_key=api_key,
            lookback_days=older_days if fetch_older_data else 364,
            end_date=older_anchor,
        )
        return df, "stooq", candidate, None, f"Stooq succeeded as primary source for {instrument_type}."
    except ValueError as exc:
        primary_error = exc

    if is_literal_commodity:
        try:
            csv_path = DATA_DIR_BY_INSTRUMENT[instrument_type] / f"{_sanitize_symbol_for_filename(_storage_symbol_for_csv(symbol, instrument_type))}.csv"
            stooq_fetch_symbol = str(mapped_stooq or symbol).lower()
            df = update_stooq_history_with_playwright(
                symbol=stooq_fetch_symbol,
                csv_path=csv_path,
                lookback_days=older_days if fetch_older_data else _incremental_lookback_days(csv_path),
                end_date=_older_fetch_anchor(csv_path) if fetch_older_data else None,
                verbose=os.getenv("STOCKHELPER_STOOQ_DEBUG", "0") == "1",
                interactive_captcha=True,
            )
            return df, "stooq_web", symbol, None, f"Stooq API failed, fallback to Stooq web scraping: {primary_error}"
        except Exception as web_exc:
            raise ValueError(f"Stooq API failed: {primary_error} ; Stooq web failed: {web_exc}") from web_exc

    raise ValueError(f"Stooq API failed for non-commodity-web symbol {symbol}: {primary_error}")


def load_or_update_daily_data(
    symbol: str,
    instrument_type: str,
    persist: bool = True,
    api_key: str | None = None,
    data_source: str = "auto",
    fetch_older_data: bool = False,
) -> tuple[pd.DataFrame, Path, dict]:
    data_dir = DATA_DIR_BY_INSTRUMENT[instrument_type]
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = data_dir / f"{_sanitize_symbol_for_filename(_storage_symbol_for_csv(symbol, instrument_type))}.csv"

    local = None
    if csv_path.exists():
        local = _sanitize_ohlc_dataframe(pd.read_csv(csv_path))
        if local.empty:
            local = None

    cache_only = os.environ.get("STOCKHELPER_CACHE_ONLY") == "1"
    refresh_key = (instrument_type, _storage_symbol_for_csv(symbol, instrument_type).upper(), bool(fetch_older_data))

    # If this symbol was already refreshed in this process and file exists, reuse local CSV
    # to avoid repeated API/web fetches (especially Stooq web + captcha flows).
    if refresh_key in _SESSION_REFRESHED_KEYS and local is not None and not local.empty:
        cached_df = local if fetch_older_data else _last_year_only(local)
        return cached_df, csv_path, {
            "source": "cache",
            "symbol": symbol,
            "name": symbol.title(),
            "fallback_reason": "Session cache: remote refresh already performed in this run.",
        }

    if cache_only and local is not None and not local.empty:
        cached_df = local if fetch_older_data else _last_year_only(local)
        return cached_df, csv_path, {
            "source": "cache",
            "symbol": symbol,
            "name": symbol.title(),
            "fallback_reason": "Cache-only mode enabled.",
        }

    if instrument_type == "commodity" and not fetch_older_data and _local_csv_has_min_year(csv_path):
        cached_df = _last_year_only(local) if local is not None else pd.DataFrame()
        return cached_df, csv_path, {
            "source": "cache",
            "symbol": symbol,
            "name": symbol.title(),
            "fallback_reason": "Commodity local CSV already has >=1y data.",
        }

    try:
        remote, source, source_symbol, source_name, fallback_reason = _download_remote(symbol=symbol, instrument_type=instrument_type, api_key=api_key, data_source=data_source, fetch_older_data=fetch_older_data)
        _SESSION_REFRESHED_KEYS.add(refresh_key)
    except ValueError:
        if local is not None and not local.empty:
            cached_df = local if fetch_older_data else _last_year_only(local)
            return cached_df, csv_path, {"source": "cache", "symbol": symbol, "name": symbol.title(), "fallback_reason": "Remote download failed, using local cache."}
        raise

    if local is not None and not local.empty:
        merged_full = _sanitize_ohlc_dataframe(pd.concat([local, remote], ignore_index=True))
    else:
        merged_full = _sanitize_ohlc_dataframe(remote)

    # Runtime callers typically need only the recent window for indicators,
    # but cache on disk must keep full history (never shrink on regular refresh).
    merged = merged_full if fetch_older_data else _last_year_only(merged_full)

    if persist:
        # Safety for older-data backfills: never shrink/regress cached history when writing.
        if fetch_older_data and csv_path.exists():
            try:
                current = pd.read_csv(csv_path)
                if not current.empty and "Date" in current.columns:
                    current = _sanitize_ohlc_dataframe(current)
                    merged_full = _sanitize_ohlc_dataframe(pd.concat([current, merged_full], ignore_index=True))
            except Exception:
                pass

        if instrument_type == "commodity":
            merged_full = _last_two_years_only(merged_full)

        # Atomic write prevents partial/truncated CSV if process is interrupted.
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(csv_path.parent), suffix=".tmp") as tf:
            tmp_path = Path(tf.name)
        try:
            merged_full.to_csv(tmp_path, index=False)
            tmp_path.replace(csv_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
    display_name = _humanize_symbol(symbol)
    display_symbol = str(source_symbol).upper()
    if instrument_type == "commodity":
        display_name = COMMODITY_DISPLAY_NAME.get(symbol.strip().upper(), _humanize_symbol(symbol))
        # Yahoo enrichment disabled in Stooq-only mode to avoid noisy 404 lookups.
        enriched_name = source_name
        if enriched_name:
            display_name = enriched_name
        elif str(source_symbol).startswith("^"):
            display_name = str(source_symbol).replace("^", "").upper()
        preferred_stooq_symbol = COMMODITY_STOOQ_MAP.get(symbol.strip().upper())
        if preferred_stooq_symbol:
            display_symbol = preferred_stooq_symbol.upper()
    elif instrument_type == "stock":
        display_name = source_name or symbol.upper()
    return merged, csv_path, {"source": source, "symbol": display_symbol, "name": display_name, "fallback_reason": fallback_reason}
