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
    confirmation_tolerance_pct: float = 0.006
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


def _local_extrema(df: pd.DataFrame, col: str, radius: int = 2) -> list[int]:
    # Selective swing points with configurable neighborhood radius.
    idxs: list[int] = []
    for i in range(radius, len(df) - radius):
        window = df[col].iloc[i - radius : i + radius + 1]
        mid = df[col].iat[i]
        if col == "High":
            if mid == window.max() and (window == mid).sum() == 1:
                idxs.append(i)
        else:
            if mid == window.min() and (window == mid).sum() == 1:
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


def _body_intersections_between_anchors(df: pd.DataFrame, p1: int, p2: int, slope: float, intercept: float) -> int:
    left, right = sorted((p1, p2))
    intersections = 0
    for i in range(left, right + 1):
        line = _line_val(slope, intercept, i)
        body_low = min(float(df["Open"].iat[i]), float(df["Close"].iat[i]))
        body_high = max(float(df["Open"].iat[i]), float(df["Close"].iat[i]))
        if body_low <= line <= body_high:
            intersections += 1
    return intersections


def _anchor_segment_respects_line(df: pd.DataFrame, p1: int, p2: int, slope: float, intercept: float, side: str, tol: float) -> bool:
    tol = max(tol, 0.01)
    left, right = sorted((p1, p2))
    for i in range(left, right + 1):
        if i in (p1, p2):
            continue
        line = _line_val(slope, intercept, i)
        high = float(df["High"].iat[i])
        low = float(df["Low"].iat[i])
        if side == "upper" and high > line * (1 + tol):
            return False
        if side == "lower" and low < line * (1 - tol):
            return False
    return True
def _line_window_stats(df: pd.DataFrame, start: int, end: int, slope: float, intercept: float, side: str, tol: float) -> dict:
    invalid = 0
    tests = 0
    for i in range(start, end + 1):
        line = _line_val(slope, intercept, i)
        close = df["Close"].iat[i]
        high = df["High"].iat[i]
        low = df["Low"].iat[i]
        if side == "upper":
            if close > line:
                invalid += 1
            elif high > line * (1 + tol):
                tests += 1
        else:
            if close < line:
                invalid += 1
            elif low < line * (1 - tol):
                tests += 1
    line_values = [_line_val(slope, intercept, i) for i in range(start, end + 1)]
    return {"invalid": invalid, "tests": tests, "line_mean": float(sum(line_values) / len(line_values))}


def _pick_boundary_line(df: pd.DataFrame, pivots: list[int], side: str, cfg: ScannerConfig, start_min: int, end: int) -> dict | None:
    best = None
    if len(pivots) < 2:
        return None

    # Prefer anchors from extreme swing points only (highest highs for upper, lowest lows for lower).
    pivot_values = [(idx, float(df["High"].iat[idx] if side == "upper" else df["Low"].iat[idx])) for idx in pivots]
    pivot_values_sorted = sorted(pivot_values, key=lambda x: x[1], reverse=(side == "upper"))
    extreme_idxs = {idx for idx, _ in pivot_values_sorted[: min(8, len(pivot_values_sorted))]}

    for i, p1 in enumerate(pivots[:-1]):
        for p2 in pivots[i + 1 :]:
            if p1 not in extreme_idxs and p2 not in extreme_idxs:
                continue
            v1 = df["High"].iat[p1] if side == "upper" else df["Low"].iat[p1]
            v2 = df["High"].iat[p2] if side == "upper" else df["Low"].iat[p2]
            slope, intercept = _fit_line(p1, v1, p2, v2)
            if side == "upper" and slope > 0.0001:
                continue
            if side == "lower" and slope < -0.0001:
                continue

            # Anchor points must match the candle extreme in tolerance.
            a1_line = _line_val(slope, intercept, p1)
            a2_line = _line_val(slope, intercept, p2)
            if abs(v1 - a1_line) / a1_line > cfg.touch_tolerance_pct:
                continue
            if abs(v2 - a2_line) / a2_line > cfg.touch_tolerance_pct:
                continue

            start = max(start_min, min(p1, p2))
            if end - start < 20:
                continue

            body_intersections = _body_intersections_between_anchors(df, p1, p2, slope, intercept)
            if body_intersections > 1:
                continue

            stats = _line_window_stats(df, start, end, slope, intercept, side, cfg.touch_tolerance_pct)
            # Do not accept boundaries broken by end-of-day closes before breakout logic.
            if stats["invalid"] > 0:
                continue

            candidate = {
                "p1": p1, "p2": p2, "slope": slope, "intercept": intercept,
                "start": start, "anchor2": max(p1, p2), "touches": 2 + stats["tests"], "body_intersections": body_intersections, **stats,
            }
            if best is None:
                best = candidate
                continue

            # Priority: 1) fewer body intersections, 2) latest second anchor, 3) fewer invalids, 4) line edge, 5) tests
            if candidate["body_intersections"] < best["body_intersections"]:
                best = candidate
                continue
            if candidate["body_intersections"] > best["body_intersections"]:
                continue

            if candidate["anchor2"] > best["anchor2"]:
                best = candidate
                continue
            if candidate["anchor2"] < best["anchor2"]:
                continue

            if candidate["invalid"] < best["invalid"]:
                best = candidate
                continue

            if side == "upper":
                better_edge = candidate["line_mean"] > best["line_mean"]
            else:
                better_edge = candidate["line_mean"] < best["line_mean"]
            if better_edge or (candidate["tests"] > best["tests"]):
                best = candidate
    return best



def _collect_boundary_candidates(df: pd.DataFrame, pivots: list[int], side: str, cfg: ScannerConfig, end: int, limit: int = 6) -> list[dict]:
    candidates: list[dict] = []
    if len(pivots) < 2:
        return candidates

    pivot_values = [(idx, float(df["High"].iat[idx] if side == "upper" else df["Low"].iat[idx])) for idx in pivots]
    pivot_values_sorted = sorted(pivot_values, key=lambda x: x[1], reverse=(side == "upper"))
    extreme_idxs = {idx for idx, _ in pivot_values_sorted[: min(10, len(pivot_values_sorted))]}

    for i, p1 in enumerate(pivots[:-1]):
        for p2 in pivots[i + 1 :]:
            if p1 not in extreme_idxs and p2 not in extreme_idxs:
                continue
            v1 = df["High"].iat[p1] if side == "upper" else df["Low"].iat[p1]
            v2 = df["High"].iat[p2] if side == "upper" else df["Low"].iat[p2]
            slope, intercept = _fit_line(p1, v1, p2, v2)
            if side == "upper" and slope > 0.0001:
                continue
            if side == "lower" and slope < -0.0001:
                continue
            start = min(p1, p2)
            if end - start < 20:
                continue
            if _body_intersections_between_anchors(df, p1, p2, slope, intercept) > 5:
                continue
            if not _anchor_segment_respects_line(df, p1, p2, slope, intercept, side, cfg.touch_tolerance_pct):
                continue
            stats = _line_window_stats(df, start, end, slope, intercept, side, cfg.touch_tolerance_pct)
            if stats["invalid"] > 0:
                continue
            candidates.append({
                "p1": p1, "p2": p2, "slope": slope, "intercept": intercept,
                "start": start, "anchor2": max(p1, p2), "body_intersections": _body_intersections_between_anchors(df, p1, p2, slope, intercept),
                **stats,
            })

    def key(c: dict):
        edge = c["line_mean"] if side == "upper" else -c["line_mean"]
        return (c["body_intersections"], -c["anchor2"], c["invalid"], -c["tests"], -edge)

    return sorted(candidates, key=key)[:limit]


def detect_triangle(df: pd.DataFrame, cfg: ScannerConfig) -> dict | None:
    if len(df) < 60:
        return None
    highs = _local_extrema(df, "High")
    lows = _local_extrema(df, "Low")
    if len(highs) < 2 or len(lows) < 2:
        return None

    end = len(df) - 1
    upper_candidates = _collect_boundary_candidates(df, highs, "upper", cfg, end=end, limit=6)
    lower_candidates = _collect_boundary_candidates(df, lows, "lower", cfg, end=end, limit=6)
    if not upper_candidates or not lower_candidates:
        return None

    best_combo = None
    for upper in upper_candidates:
        for lower in lower_candidates:
            start = max(upper["start"], lower["start"])
            if end - start < 20:
                continue
            width_start = _line_val(upper["slope"], upper["intercept"], start) - _line_val(lower["slope"], lower["intercept"], start)
            width_end = _line_val(upper["slope"], upper["intercept"], end) - _line_val(lower["slope"], lower["intercept"], end)
            if width_start <= 0 or width_end <= 0 or width_end >= width_start:
                continue

            upper_anchor_end = max(upper["p1"], upper["p2"]) + 1
            lower_anchor_end = max(lower["p1"], lower["p2"]) + 1
            up_conf_ix = _confirmation_indices(df, upper_anchor_end, upper["slope"], upper["intercept"], "upper", cfg.touch_tolerance_pct)
            dn_conf_ix = _confirmation_indices(df, lower_anchor_end, lower["slope"], lower["intercept"], "lower", cfg.touch_tolerance_pct)
            score = (len(up_conf_ix) + len(dn_conf_ix)) * 20 + min(len(up_conf_ix), len(dn_conf_ix)) * 10 - abs((upper["anchor2"] - lower["anchor2"]))
            combo = {"upper": upper, "lower": lower, "start": start, "up_conf_ix": up_conf_ix, "dn_conf_ix": dn_conf_ix, "score": score}
            if best_combo is None or combo["score"] > best_combo["score"]:
                best_combo = combo

    if best_combo is None:
        # Fallback pass with denser pivots for broad triangles (helps symbols like KGH).
        highs_relaxed = _local_extrema(df, "High", radius=1)
        lows_relaxed = _local_extrema(df, "Low", radius=1)
        upper_candidates = _collect_boundary_candidates(df, highs_relaxed, "upper", cfg, end=end, limit=8)
        lower_candidates = _collect_boundary_candidates(df, lows_relaxed, "lower", cfg, end=end, limit=8)
        for upper in upper_candidates:
            for lower in lower_candidates:
                start = max(upper["start"], lower["start"])
                if end - start < 20:
                    continue
                width_start = _line_val(upper["slope"], upper["intercept"], start) - _line_val(lower["slope"], lower["intercept"], start)
                width_end = _line_val(upper["slope"], upper["intercept"], end) - _line_val(lower["slope"], lower["intercept"], end)
                if width_start <= 0 or width_end <= 0 or width_end >= width_start:
                    continue
                upper_anchor_end = max(upper["p1"], upper["p2"]) + 1
                lower_anchor_end = max(lower["p1"], lower["p2"]) + 1
                up_conf_ix = _confirmation_indices(df, upper_anchor_end, upper["slope"], upper["intercept"], "upper", cfg.confirmation_tolerance_pct)
                dn_conf_ix = _confirmation_indices(df, lower_anchor_end, lower["slope"], lower["intercept"], "lower", cfg.confirmation_tolerance_pct)
                score = len(up_conf_ix) + len(dn_conf_ix)
                combo = {"upper": upper, "lower": lower, "start": start, "up_conf_ix": up_conf_ix, "dn_conf_ix": dn_conf_ix, "score": score}
                if best_combo is None or combo["score"] > best_combo["score"]:
                    best_combo = combo
    if best_combo is None:
        return None

    upper = best_combo["upper"]
    lower = best_combo["lower"]
    start = best_combo["start"]
    up_conf_ix = best_combo["up_conf_ix"]
    dn_conf_ix = best_combo["dn_conf_ix"]
    up_touches = len(up_conf_ix) + 2
    dn_touches = len(dn_conf_ix) + 2

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

    upper_anchor_dates = sorted([df["Date"].iat[upper["p1"]].date().isoformat(), df["Date"].iat[upper["p2"]].date().isoformat()])
    lower_anchor_dates = sorted([df["Date"].iat[lower["p1"]].date().isoformat(), df["Date"].iat[lower["p2"]].date().isoformat()])

    return {
        "Ticker": "",
        "Typ_trójkąta": tri_type,
        "Liczba_touch_górą": up_touches,
        "Liczba_touch_dołem": dn_touches,
        "Data_anchor_1_góra": upper_anchor_dates[0],
        "Data_anchor_2_góra": upper_anchor_dates[1],
        "Data_anchor_1_dół": lower_anchor_dates[0],
        "Data_anchor_2_dół": lower_anchor_dates[1],
        "Status": status,
        "Data_wybicia": breakout_date.date().isoformat() if breakout_date is not None else "",
        "Cena_wybicia": line_cross_value if line_cross_value is not None else breakout_price,
        "Line_cross_value": line_cross_value,
        "TP": tp,
        "Wysokość_formacji": high - low,
        "Siła_formacji": "very_good" if min(len(up_conf_ix), len(dn_conf_ix)) >= 2 else ("good" if min(len(up_conf_ix), len(dn_conf_ix)) >= 1 else "base"),
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
                last_date = df["Date"].max().date() if not df.empty else None
                today = pd.Timestamp.utcnow().tz_localize(None).date()
                if last_date is None or (today - last_date).days >= 1:
                    fresh = _stooq_download(symbol, days=cfg.history_days)
                    if not fresh.empty:
                        df = fresh
                        df.to_csv(cache_path, index=False)
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
