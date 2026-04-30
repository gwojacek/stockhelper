import io
from io import StringIO
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import pandas as pd
import yfinance as yf
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
RETRY_EXCEPTIONS = (HTTPError, URLError, ValueError, ConnectionError, TimeoutError, Exception)
STOOQ_API_KEY = "x1s2H9UeqW6t3oJR7gDpm8fwPnudBjFS"
LAST_TURNOVER_SOURCE = "unknown"
def _before_sleep_log(retry_state):
    print(
        f"Retry {retry_state.attempt_number} for {retry_state.fn.__name__} "
        f"after error: {retry_state.outcome.exception()}"
    )
def _period_to_date_range(period: str) -> tuple[str, str]:
    days = int(period.rstrip("d"))
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days * 2)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
def _stooq_symbol_candidates(symbol: str) -> list[str]:
    cleaned = (symbol or "").strip().lower()
    if not cleaned:
        return []
    candidates: list[str] = []
    if "." in cleaned:
        left, right = cleaned.split(".", 1)
        candidates.append(f"{left}.{right}")
        if right == "wa":
            candidates.append(f"{left}.pl")
        candidates.append(left)
    else:
        candidates.append(f"{cleaned}.pl")
        candidates.append(cleaned)
    return list(dict.fromkeys(candidates))
def _parse_stooq_csv_text(csv_text: str) -> pd.DataFrame:
    lines = csv_text.splitlines()
    header_index = None
    separator = ","
    for i, raw_line in enumerate(lines):
        line = raw_line.strip().lstrip("﻿")
        lowered = line.lower()
        if lowered.startswith("date,open,high,low,close"):
            header_index = i
            separator = ","
            break
        if lowered.startswith("date;open;high;low;close"):
            header_index = i
            separator = ";"
            break
        if lowered.startswith("data,otwarcie,najwyzszy,najnizszy,zamkniecie"):
            header_index = i
            separator = ","
            break
        if lowered.startswith("data;otwarcie;najwyzszy;najnizszy;zamkniecie"):
            header_index = i
            separator = ";"
            break
    if header_index is None:
        preview = " | ".join(line.strip() for line in lines[:5])
        raise ValueError(f"Stooq response does not contain expected CSV header. Preview: {preview[:200]}")

    df = pd.read_csv(StringIO("\n".join(lines[header_index:])), sep=separator, on_bad_lines="skip")
    df = df.rename(columns={
        "Data": "Date",
        "Otwarcie": "Open",
        "Najwyzszy": "High",
        "Najnizszy": "Low",
        "Zamkniecie": "Close",
        "Wolumen": "Volume",
    })
    return df
def _fetch_stooq_history(symbol: str, period: str) -> pd.DataFrame:
    d1, d2 = _period_to_date_range(period)
    for candidate in _stooq_symbol_candidates(symbol):
        params = {"s": candidate, "i": "d", "d1": d1, "d2": d2, "apikey": STOOQ_API_KEY}
        url = f"https://stooq.pl/q/d/l/?{urlencode(params)}"
        with urlopen(url, timeout=15) as response:
            csv_text = response.read().decode("utf-8", errors="replace")
        df = _parse_stooq_csv_text(csv_text)
        expected_cols = {"Open", "High", "Low", "Close", "Volume"}
        if expected_cols.issubset(df.columns) and not df.empty:
            return df
    raise ValueError(f"Brak danych Stooq dla symbolu {symbol}")
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(RETRY_EXCEPTIONS),
    reraise=True,
    before_sleep=_before_sleep_log,
)
def get_daily_turnovers_yahoo(symbol: str, period: str = "20d") -> list[float]:
    """Pobiera listę dziennych obrotów, preferując Stooq, z fallbackiem do Yahoo."""
    global LAST_TURNOVER_SOURCE
    hist = None
    try:
        hist = _fetch_stooq_history(symbol, period=period)
        LAST_TURNOVER_SOURCE = "stooq"
    except Exception as stooq_error:
        LAST_TURNOVER_SOURCE = "yahoo"
        stock = yf.Ticker(symbol)
        hist = stock.history(period=period)
    if hist is None or hist.empty:
        raise ValueError(f"Brak danych dla symbolu {symbol}")
    hist["AveragePrice"] = (hist["Open"] + hist["Close"] + hist["High"] + hist["Low"]) / 4
    hist["DailyTurnover"] = hist["Volume"] * hist["AveragePrice"]
    return hist["DailyTurnover"].tolist()
def get_avg_daily_turnover_yahoo(symbol: str, period: str = "10d") -> float:
    daily_turnovers = get_daily_turnovers_yahoo(symbol, period=period)
    return float(sum(daily_turnovers) / len(daily_turnovers))
def get_symbol_currency_yahoo(symbol: str) -> str:
    stock = yf.Ticker(symbol)
    currency = ""
    try:
        currency = (stock.fast_info.get("currency") or "").upper()
    except Exception:
        currency = ""
    if not currency:
        info = stock.info or {}
        currency = (info.get("currency") or "").upper()
    return currency or "USD"
def get_fx_to_pln_rate_yahoo(currency: str) -> tuple[str, float]:
    currency = currency.upper()
    if currency == "PLN":
        return "PLNPLN=X", 1.0
    for pair in [f"{currency}PLN=X", f"PLN{currency}=X"]:
        hist = yf.Ticker(pair).history(period="5d")
        if not hist.empty:
            rate = float(hist["Close"].iloc[-1])
            if pair.startswith("PLN") and rate > 0:
                rate = 1 / rate
            return pair, rate
    raise ValueError(f"Brak kursu FX dla waluty {currency} do PLN")
def get_last_turnover_source() -> str:
    """Zwraca źródło ostatnio pobranych danych obrotu: stooq/yahoo/unknown."""
    return LAST_TURNOVER_SOURCE
