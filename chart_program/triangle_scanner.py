from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unicodedata

import pandas as pd

from core.risk_manager import calculate_take_profit
from utilities.yahoo_finance import _fetch_stooq_history

STOOQ_API_KEY = "x1s2H9UeqW6t3oJR7gDpm8fwPnudBjFS"
DATA_DIR = Path("chart_program/data/stocks")
RESULTS_DIR = Path("results/triangles")

WIG20_SYMBOLS = [
    "ALR", "ALE", "ACP", "CCC", "CDR", "CPS", "DNP", "KTY", "KGH", "KRU",
    "LPP", "MBK", "OPL", "PEO", "PCO", "PGE", "PKN", "PKO", "PZU", "EBS",
]

WIG20_LABELS = {
    "ALR": "ALIOR", "ALE": "ALLEGRO", "ACP": "ASSECO", "CCC": "CCC", "CDR": "CDPROJEKT",
    "CPS": "CYFRPLSAT", "DNP": "DINOPL", "KTY": "KETY", "KGH": "KGHM", "KRU": "KRUK",
    "LPP": "LPP", "MBK": "MBANK", "OPL": "ORANGEPL", "PEO": "PEKAO", "PCO": "PEPCO",
    "PGE": "PGE", "PKN": "PKNORLEN", "PKO": "PKOBP", "PZU": "PZU", "EBS": "ERSTEPL",
}


@dataclass
class ScannerConfig:
    touch_tolerance_pct: float = 0.001
    breakout_lookback_sessions: int = 5
    liquidity_min_avg_turnover_pln: float = 500_000
    history_days: int = 364
    force_refresh: bool = False


TICKER_ALIASES = {
    "KGHM": "KGH",
    "CDPROJEKT": "CDR",
    "CYFRPLSAT": "CPS",
    "DINOPL": "DNP",
    "MBANK": "MBK",
    "ORANGEPL": "OPL",
    "PEKAO": "PEO",
    "PEPCO": "PCO",
    "PKNORLEN": "PKN",
    "PKOBP": "PKO",
    "ALIOR": "ALR",
    "ALLEGRO": "ALE",
    "ASSECO": "ACP",
    "KETY": "KTY",
    "KRUK": "KRU",
    "ERSTEPL": "EBS",
    "SANTANDER": "EBS",
}



def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    def _norm(value: str) -> str:
        ascii_value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
        return ascii_value.strip().lower()

    mapping = {
        "data": "Date",
        "date": "Date",
        "otwarcie": "Open",
        "open": "Open",
        "najwyzszy": "High",
        "high": "High",
        "najnizszy": "Low",
        "low": "Low",
        "zamkniecie": "Close",
        "close": "Close",
        "wolumen": "Volume",
        "volume": "Volume",
    }
    rename: dict[str, str] = {}
    for col in df.columns:
        key = mapping.get(_norm(col))
        if key:
            rename[col] = key
    return df.rename(columns=rename)
def _stooq_download(symbol: str, days: int) -> pd.DataFrame:
    # Reuse existing stockhelper Stooq loader (supports Polish/English headers, ;/, separators).
    # The utility accepts a `period` string and internally handles Stooq symbol variants.
    df = _fetch_stooq_history(f"{symbol}.WA", period=f"{days}d")
    df = _normalize_columns(df)
    expected_cols = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if not expected_cols.issubset(df.columns):
        raise ValueError(f"Invalid Stooq columns: {list(df.columns)}")

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"])
    return df.sort_values("Date").reset_index(drop=True)


def _local_extrema(df: pd.DataFrame, col: str) -> list[int]:
    idxs: list[int] = []
    for i in range(1, len(df) - 1):
        left, mid, right = df[col].iat[i - 1], df[col].iat[i], df[col].iat[i + 1]
        if col == "High" and mid >= left and mid >= right:
            idxs.append(i)
        if col == "Low" and mid <= left and mid <= right:
            idxs.append(i)
    return idxs


def _fit_line(i1: int, v1: float, i2: int, v2: float) -> tuple[float, float]:
    slope = (v2 - v1) / (i2 - i1)
    intercept = v1 - slope * i1
    return slope, intercept


def _line_val(slope: float, intercept: float, idx: int) -> float:
    return slope * idx + intercept


def _count_touches(df: pd.DataFrame, slope: float, intercept: float, side: str, tol: float) -> int:
    touches = 0
    prev = -99
    for i in range(len(df)):
        line = _line_val(slope, intercept, i)
        price = df["High"].iat[i] if side == "upper" else df["Low"].iat[i]
        if line > 0 and abs(price - line) / line <= tol and i - prev > 2:
            touches += 1
            prev = i
    return touches


def detect_triangle(df: pd.DataFrame, cfg: ScannerConfig) -> dict | None:
    if len(df) < 60:
        return None
    highs = _local_extrema(df, "High")
    lows = _local_extrema(df, "Low")
    if len(highs) < 2 or len(lows) < 2:
        return None

    best = None
    for hi, h1 in enumerate(highs[:-1]):
        for h2 in highs[hi + 1 :]:
            us, ui = _fit_line(h1, df["High"].iat[h1], h2, df["High"].iat[h2])
            if us > 0.0001:
                continue
            for li, l1 in enumerate(lows[:-1]):
                for l2 in lows[li + 1 :]:
                    ls, li2 = _fit_line(l1, df["Low"].iat[l1], l2, df["Low"].iat[l2])
                    if ls < -0.0001:
                        continue
                    start = max(min(h1, h2), min(l1, l2))
                    end = len(df) - 1
                    if end - start < 20:
                        continue

                    width_start = _line_val(us, ui, start) - _line_val(ls, li2, start)
                    width_end = _line_val(us, ui, end) - _line_val(ls, li2, end)
                    if width_start <= 0 or width_end <= 0 or width_end >= width_start:
                        continue

                    up_touches = _count_touches(df.iloc[start : end + 1].reset_index(drop=True), us, ui, "upper", cfg.touch_tolerance_pct)
                    dn_touches = _count_touches(df.iloc[start : end + 1].reset_index(drop=True), ls, li2, "lower", cfg.touch_tolerance_pct)
                    if up_touches + dn_touches < 3:
                        continue

                    tri_type = "symmetrical"
                    if abs(us) < 1e-4 and ls > 0:
                        tri_type = "ascending"
                    elif us < 0 and abs(ls) < 1e-4:
                        tri_type = "descending"

                    score = (end - start) + 5 * (up_touches + dn_touches)
                    if best is None or score > best["score"]:
                        best = {
                            "start": start,
                            "end": end,
                            "upper_slope": us,
                            "upper_i": ui,
                            "lower_slope": ls,
                            "lower_i": li2,
                            "up_touches": up_touches,
                            "down_touches": dn_touches,
                            "triangle_type": tri_type,
                            "score": score,
                        }
    if not best:
        return None

    last_i = len(df) - 1
    status = "Active"
    breakout_date = None
    breakout_price = None
    line_cross_value = None
    direction = "none"
    for i in range(max(best["start"], last_i - cfg.breakout_lookback_sessions + 1), len(df)):
        close = df["Close"].iat[i]
        upper = _line_val(best["upper_slope"], best["upper_i"], i)
        lower = _line_val(best["lower_slope"], best["lower_i"], i)
        if close > upper:
            status = "Broken_Up"
            direction = "up"
            breakout_date = df["Date"].iat[i]
            breakout_price = close
            line_cross_value = upper
            break
        if close < lower:
            status = "Broken_Down"
            direction = "down"
            breakout_date = df["Date"].iat[i]
            breakout_price = close
            line_cross_value = lower
            break

    window = df.iloc[best["start"] : best["end"] + 1]
    high = float(window["High"].max())
    low = float(window["Low"].min())
    tp = None
    if status.startswith("Broken") and line_cross_value is not None:
        tp = calculate_take_profit(
            line_cross_value,
            high,
            low,
            "long" if direction == "up" else "short",
            start_value=line_cross_value,
        )

    return {
        "Ticker": "",
        "Typ_trójkąta": best["triangle_type"],
        "Kierunek": direction,
        "Data_startu": df["Date"].iat[best["start"]].date().isoformat(),
        "Data_końca": df["Date"].iat[best["end"]].date().isoformat(),
        "Liczba_touch_górą": best["up_touches"],
        "Liczba_touch_dołem": best["down_touches"],
        "Status": status,
        "Data_wybicia": breakout_date.date().isoformat() if breakout_date is not None else "",
        "Cena_wybicia": breakout_price,
        "Line_cross_value": line_cross_value,
        "TP": tp,
        "Wysokość_formacji": high - low,
        "Siła_formacji": "very_good" if min(best["up_touches"], best["down_touches"]) >= 3 else "good",
    }


def run_scan(target: str, force: bool = False) -> Path:
    cfg = ScannerConfig(force_refresh=force)
    raw_symbols = WIG20_SYMBOLS if target.lower() == "wig20" else [target.upper()]
    symbols = [TICKER_ALIASES.get(sym, sym) for sym in raw_symbols]
    rows: list[dict] = []

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for symbol in symbols:
        cache_path = DATA_DIR / f"{symbol}_WA.csv"
        try:
            if cache_path.exists() and not cfg.force_refresh:
                df = _normalize_columns(pd.read_csv(cache_path))
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                df = df.dropna(subset=["Date"])
            else:
                df = _stooq_download(symbol, days=cfg.history_days)
                df.to_csv(cache_path, index=False)
        except Exception as exc:
            print(f"Skip {symbol}: data download failed ({exc})")
            continue

        df = df[df["Date"] >= (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=cfg.history_days))]
        if df.empty:
            continue

        avg_turnover = float((((df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4) * df["Volume"]).tail(10).mean())
        if avg_turnover <= cfg.liquidity_min_avg_turnover_pln:
            continue

        triangle = detect_triangle(df.reset_index(drop=True), cfg)
        if triangle is None:
            continue
        triangle["Ticker"] = WIG20_LABELS.get(symbol, symbol)
        rows.append(triangle)

    result_df = pd.DataFrame(rows)
    out_path = RESULTS_DIR / f"triangles_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    result_df.to_csv(out_path, index=False)
    print(f"Saved triangle scan to: {out_path}")
    if not result_df.empty:
        print(result_df.to_string(index=False))
    return out_path
