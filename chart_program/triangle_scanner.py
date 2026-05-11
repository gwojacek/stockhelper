from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unicodedata

import pandas as pd

from core.risk_manager import calculate_take_profit
from chart_program.chart_loader import _stooq_download as chart_stooq_download

DATA_DIR = Path("chart_program/data/stocks")
RESULTS_DIR = Path("results/triangles")

WIG20_SYMBOLS = [
    "ALR", "ALE", "ACP", "MDV", "CDR", "CPS", "DNP", "KTY", "KGH", "KRU",
    "LPP", "MBK", "OPL", "PEO", "PCO", "PGE", "PKN", "PKO", "PZU", "EBP",
]

WIG20_LABELS = {
    "ALR": "ALIOR", "ALE": "ALLEGRO", "ACP": "ASSECO", "MDV": "MODIVO", "CDR": "CDPROJEKT",
    "CPS": "CYFRPLSAT", "DNP": "DINOPL", "KTY": "KETY", "KGH": "KGHM", "KRU": "KRUK",
    "LPP": "LPP", "MBK": "MBANK", "OPL": "ORANGEPL", "PEO": "PEKAO", "PCO": "PEPCO",
    "PGE": "PGE", "PKN": "PKNORLEN", "PKO": "PKOBP", "PZU": "PZU", "EBP": "ERSTEPL",
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
    "CCC": "MDV",
    "MODIVO": "MDV",
    "KETY": "KTY",
    "KRUK": "KRU",
    "ERSTEPL": "EBP",
    "SANTANDER": "EBP",
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
    df, _candidate = chart_stooq_download(f"{symbol}.WA", "stock", api_key=None)
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




def _touch_indices(df: pd.DataFrame, slope: float, intercept: float, side: str, tol: float) -> list[int]:
    idxs: list[int] = []
    prev = -99
    for i in range(len(df)):
        line = _line_val(slope, intercept, i)
        price = df["High"].iat[i] if side == "upper" else df["Low"].iat[i]
        if line > 0 and abs(price - line) / line <= tol and i - prev > 2:
            idxs.append(i)
            prev = i
    return idxs
def _count_touches(df: pd.DataFrame, slope: float, intercept: float, side: str, tol: float) -> int:
    return len(_touch_indices(df, slope, intercept, side, tol))






def _confirmation_indices(df: pd.DataFrame, start_idx: int, slope: float, intercept: float, side: str, tol: float) -> list[int]:
    idxs: list[int] = []
    prev = -99
    for i in range(start_idx, len(df)):
        line = _line_val(slope, intercept, i)
        close = df["Close"].iat[i]
        price = df["High"].iat[i] if side == "upper" else df["Low"].iat[i]
        close_inside = close <= line if side == "upper" else close >= line
        if line > 0 and close_inside and abs(price - line) / line <= tol and i - prev > 2:
            idxs.append(i)
            prev = i
    return idxs
def _line_window_stats(df: pd.DataFrame, start: int, end: int, slope: float, intercept: float, side: str, tol: float) -> dict:
    invalid = 0
    tests = 0
    for i in range(start, end + 1):
        line = _line_val(slope, intercept, i)
        close = df["Close"].iat[i]
        high = df["High"].iat[i]
        low = df["Low"].iat[i]
        if side == "upper":
            if high > line * (1 + tol):
                if close <= line:
                    tests += 1
                else:
                    invalid += 1
        else:
            if low < line * (1 - tol):
                if close >= line:
                    tests += 1
                else:
                    invalid += 1
    line_values = [_line_val(slope, intercept, i) for i in range(start, end + 1)]
    return {"invalid": invalid, "tests": tests, "line_mean": float(sum(line_values) / len(line_values))}


def _pick_boundary_line(df: pd.DataFrame, pivots: list[int], side: str, cfg: ScannerConfig, start_min: int, end: int) -> dict | None:
    best = None
    for i, p1 in enumerate(pivots[:-1]):
        for p2 in pivots[i + 1 :]:
            v1 = df["High"].iat[p1] if side == "upper" else df["Low"].iat[p1]
            v2 = df["High"].iat[p2] if side == "upper" else df["Low"].iat[p2]
            slope, intercept = _fit_line(p1, v1, p2, v2)
            if side == "upper" and slope > 0.0001:
                continue
            if side == "lower" and slope < -0.0001:
                continue
            start = max(start_min, min(p1, p2))
            if end - start < 20:
                continue
            touches = _count_touches(df.iloc[start : end + 1].reset_index(drop=True), slope, intercept, side, cfg.touch_tolerance_pct)
            if touches < 2:
                continue
            stats = _line_window_stats(df, start, end, slope, intercept, side, cfg.touch_tolerance_pct)
            candidate = {
                "p1": p1, "p2": p2, "slope": slope, "intercept": intercept,
                "start": start, "touches": touches, **stats,
            }
            if best is None:
                best = candidate
                continue
            # Prefer fewer invalid penetrations; then higher upper line / lower lower line; then more touches.
            if candidate["invalid"] < best["invalid"]:
                best = candidate
            elif candidate["invalid"] == best["invalid"]:
                if side == "upper":
                    better_edge = candidate["line_mean"] > best["line_mean"]
                else:
                    better_edge = candidate["line_mean"] < best["line_mean"]
                if better_edge or (candidate["touches"] > best["touches"]):
                    best = candidate
    return best
def detect_triangle(df: pd.DataFrame, cfg: ScannerConfig) -> dict | None:
    if len(df) < 60:
        return None
    highs = _local_extrema(df, "High")
    lows = _local_extrema(df, "Low")
    if len(highs) < 2 or len(lows) < 2:
        return None

    end = len(df) - 1
    upper = _pick_boundary_line(df, highs, "upper", cfg, start_min=0, end=end)
    lower = _pick_boundary_line(df, lows, "lower", cfg, start_min=0, end=end)
    if not upper or not lower:
        return None

    start = max(upper["start"], lower["start"])
    if end - start < 20:
        return None

    width_start = _line_val(upper["slope"], upper["intercept"], start) - _line_val(lower["slope"], lower["intercept"], start)
    width_end = _line_val(upper["slope"], upper["intercept"], end) - _line_val(lower["slope"], lower["intercept"], end)
    if width_start <= 0 or width_end <= 0 or width_end >= width_start:
        return None

    upper_anchor_end = max(upper["p1"], upper["p2"]) + 1
    lower_anchor_end = max(lower["p1"], lower["p2"]) + 1
    up_conf_ix = _confirmation_indices(df, upper_anchor_end, upper["slope"], upper["intercept"], "upper", cfg.touch_tolerance_pct)
    dn_conf_ix = _confirmation_indices(df, lower_anchor_end, lower["slope"], lower["intercept"], "lower", cfg.touch_tolerance_pct)
    up_touches = len(up_conf_ix) + 2
    dn_touches = len(dn_conf_ix) + 2
    if len(up_conf_ix) < 2 or len(dn_conf_ix) < 2:
        return None

    tri_type = "symmetrical"
    if abs(upper["slope"]) < 1e-4 and lower["slope"] > 0:
        tri_type = "ascending"
    elif upper["slope"] < 0 and abs(lower["slope"]) < 1e-4:
        tri_type = "descending"

    last_i = len(df) - 1
    status = "Active"
    breakout_date = None
    breakout_price = None
    line_cross_value = None
    direction = "none"
    for i in range(max(start, last_i - cfg.breakout_lookback_sessions + 1), len(df)):
        close = df["Close"].iat[i]
        upper_line = _line_val(upper["slope"], upper["intercept"], i)
        lower_line = _line_val(lower["slope"], lower["intercept"], i)
        if close > upper_line:
            status = "Broken_Up"
            direction = "up"
            breakout_date = df["Date"].iat[i]
            breakout_price = close
            line_cross_value = upper_line
            break
        if close < lower_line:
            status = "Broken_Down"
            direction = "down"
            breakout_date = df["Date"].iat[i]
            breakout_price = close
            line_cross_value = lower_line
            break

    window = df.iloc[start : end + 1]
    high = float(window["High"].max())
    low = float(window["Low"].min())
    tp = None
    if status.startswith("Broken") and line_cross_value is not None:
        tp = calculate_take_profit(line_cross_value, high, low, "long" if direction == "up" else "short", start_value=line_cross_value)

    up_test_dates = [df["Date"].iat[i].date().isoformat() for i in up_conf_ix[:2]]
    dn_test_dates = [df["Date"].iat[i].date().isoformat() for i in dn_conf_ix[:2]]

    return {
        "Ticker": "",
        "Typ_trójkąta": tri_type,
        "Kierunek": direction,
        "Data_startu": df["Date"].iat[start].date().isoformat(),
        "Data_końca": df["Date"].iat[end].date().isoformat(),
        "Liczba_touch_górą": up_touches,
        "Liczba_touch_dołem": dn_touches,
        "Data_test_1_góra": up_test_dates[0] if len(up_test_dates) > 0 else "",
        "Data_test_2_góra": up_test_dates[1] if len(up_test_dates) > 1 else "",
        "Data_test_1_dół": dn_test_dates[0] if len(dn_test_dates) > 0 else "",
        "Data_test_2_dół": dn_test_dates[1] if len(dn_test_dates) > 1 else "",
        "Status": status,
        "Data_wybicia": breakout_date.date().isoformat() if breakout_date is not None else "",
        "Cena_wybicia": breakout_price,
        "Line_cross_value": line_cross_value,
        "TP": tp,
        "Wysokość_formacji": high - low,
        "Siła_formacji": "very_good" if min(up_touches, dn_touches) >= 3 else "good",
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
    else:
        print("No valid triangles found for selected universe and filters.")
    return out_path
