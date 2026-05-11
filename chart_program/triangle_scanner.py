from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from core.risk_manager import calculate_take_profit

STOOQ_API_KEY = "x1s2H9UeqW6t3oJR7gDpm8fwPnudBjFS"
DATA_DIR = Path("chart_program/data/stocks")
RESULTS_DIR = Path("results/triangles")

WIG20_SYMBOLS = [
    "ALIOR", "ALLEGRO", "ASSECO", "CCC", "CDPROJEKT", "CYFRPLSAT", "DINOPL", "KETY",
    "KGHM", "KRUK", "LPP", "MBANK", "ORANGEPL", "PEKAO", "PEPCO", "PGE", "PKNORLEN",
    "PKOBP", "PZU", "SANTANDER"
]


@dataclass
class ScannerConfig:
    touch_tolerance_pct: float = 0.001
    breakout_lookback_sessions: int = 5
    liquidity_min_avg_turnover_pln: float = 500_000
    force_refresh: bool = False


def _stooq_download(symbol: str, days: int = 380) -> pd.DataFrame:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    params = {
        "s": f"{symbol.lower()}.pl",
        "i": "d",
        "d1": start.strftime("%Y%m%d"),
        "d2": end.strftime("%Y%m%d"),
        "apikey": STOOQ_API_KEY,
    }
    url = f"https://stooq.pl/q/d/l/?{urlencode(params)}"
    with urlopen(url, timeout=20) as resp:
        df = pd.read_csv(resp)
    df = df.rename(columns=str.capitalize)
    df["Date"] = pd.to_datetime(df["Date"])
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
        if abs(price - line) / line <= tol:
            if i - prev > 2:
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
    for h1 in highs[:-1]:
        for h2 in highs[highs.index(h1)+1:]:
            us, ui = _fit_line(h1, df["High"].iat[h1], h2, df["High"].iat[h2])
            if us > 0.0001:
                continue
            for l1 in lows[:-1]:
                for l2 in lows[lows.index(l1)+1:]:
                    ls, li = _fit_line(l1, df["Low"].iat[l1], l2, df["Low"].iat[l2])
                    if ls < -0.0001:
                        continue
                    start, end = max(min(h1, h2), min(l1, l2)), min(len(df)-1, len(df)-1)
                    if end - start < 20:
                        continue
                    width_start = _line_val(us, ui, start) - _line_val(ls, li, start)
                    width_end = _line_val(us, ui, end) - _line_val(ls, li, end)
                    if width_start <= 0 or width_end <= 0 or width_end >= width_start:
                        continue
                    if abs((df["High"].iat[h1] - _line_val(us, ui, h1)) / df["High"].iat[h1]) > cfg.touch_tolerance_pct:
                        continue
                    if abs((df["High"].iat[h2] - _line_val(us, ui, h2)) / df["High"].iat[h2]) > cfg.touch_tolerance_pct:
                        continue
                    if abs((df["Low"].iat[l1] - _line_val(ls, li, l1)) / df["Low"].iat[l1]) > cfg.touch_tolerance_pct:
                        continue
                    if abs((df["Low"].iat[l2] - _line_val(ls, li, l2)) / df["Low"].iat[l2]) > cfg.touch_tolerance_pct:
                        continue

                    up_touches = _count_touches(df.iloc[start:end+1].reset_index(drop=True), us, ui, "upper", cfg.touch_tolerance_pct)
                    dn_touches = _count_touches(df.iloc[start:end+1].reset_index(drop=True), ls, li, "lower", cfg.touch_tolerance_pct)
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
                            "start": start, "end": end, "upper_slope": us, "upper_i": ui,
                            "lower_slope": ls, "lower_i": li, "up_touches": up_touches,
                            "down_touches": dn_touches, "triangle_type": tri_type, "score": score,
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
        tp = calculate_take_profit(line_cross_value, high, low, "long" if direction == "up" else "short", start_value=line_cross_value)

    return {
        "type": best["triangle_type"],
        "direction": direction,
        "start_date": df["Date"].iat[best["start"]].date().isoformat(),
        "end_date": df["Date"].iat[best["end"]].date().isoformat(),
        "touches_upper": best["up_touches"],
        "touches_lower": best["down_touches"],
        "status": status,
        "breakout_date": breakout_date.date().isoformat() if breakout_date is not None else "",
        "breakout_price": breakout_price,
        "line_cross_value": line_cross_value,
        "tp": tp,
        "height": high - low,
        "strength": "very_good" if min(best["up_touches"], best["down_touches"]) >= 3 else "good",
    }


def run_scan(target: str, force: bool = False) -> Path:
    cfg = ScannerConfig(force_refresh=force)
    symbols = WIG20_SYMBOLS if target.lower() == "wig20" else [target.upper()]
    rows: list[dict] = []

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for symbol in symbols:
        cache_path = DATA_DIR / f"{symbol}_WA.csv"
        if cache_path.exists() and not cfg.force_refresh:
            df = pd.read_csv(cache_path)
            df["Date"] = pd.to_datetime(df["Date"])
        else:
            try:
                df = _stooq_download(symbol)
                df.to_csv(cache_path, index=False)
            except Exception as exc:
                if cache_path.exists():
                    df = pd.read_csv(cache_path)
                    df["Date"] = pd.to_datetime(df["Date"] )
                else:
                    print(f"Skip {symbol}: data download failed ({exc})")
                    continue

        df = df[df["Date"] >= (pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=365))]
        if df.empty:
            continue
        avg_turnover = float((((df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4) * df["Volume"]).tail(10).mean())
        if avg_turnover <= cfg.liquidity_min_avg_turnover_pln:
            continue

        triangle = detect_triangle(df.reset_index(drop=True), cfg)
        if triangle is None:
            continue
        rows.append({"Ticker": symbol, **triangle})

    result_df = pd.DataFrame(rows)
    out_path = RESULTS_DIR / f"triangles_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    result_df.to_csv(out_path, index=False)
    print(f"Saved triangle scan to: {out_path}")
    if not result_df.empty:
        print(result_df.to_string(index=False))
    return out_path
