from __future__ import annotations

import argparse
import csv
import json
import os
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
import math
from importlib import util
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from chart_program.instrument_detector import detect_instrument_type
from chart_program.chart_loader import (
    UNIFIED_DATA_DIR,
    COMMODITY_STOOQ_MAP,
    COMMODITY_YAHOO_MAP,
    load_or_update_daily_data,
)
from utilities.yahoo_finance import get_fx_to_pln_rate_yahoo

PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_MEMBERS_FILE = PROJECT_ROOT / "data" / "indices" / "memberships.json"
SEARCH_OUTPUT_DIR = PROJECT_ROOT / "chart_program" / "data" / "search"

COMMODITIES_SEARCH_TICKERS = [
    "COFFEE", "COCOA", "SUGAR", "WHEAT", "CORN", "SOYBEAN", "SOYOIL",
    "COPPER", "ALUMINIUM", "PLATINUM", "PALLADIUM", "WTI",
    "OIL", "NATURAL_GAS", "XAUUSD", "XAGUSD",
]

INDEXES_SEARCH_TICKERS = [
    "BRACOMP", "US500", "MEXCOMP", "VIX", "US30", "US100", "HK.CASH",
    "SG20CASH", "AU200.CASH", "CHN.CASH", "JP225", "WIG20", "UK100",
    "ITA40", "DE40", "FRA40", "NED25", "SUI20", "SPA35", "EU50",
]

WIG_SEARCH_TICKERS = [
    "EBP","PKO","MBK","OPL","PEO","CEZ","GTN","GTC","AGO","KGH","PXM","PKN","CPS","BIO","ACP","MIL","ENA","ECH","EUR","PGE",
    "PZU","UCG","MBW","MOL","06N","ABE","ABS","ACG","ACT","AGT","ALR","AMB","AMC","APN","APT","ASB","ASE","ATD","AST","ATC",
    "ATG","ATP","ATR","ATS","ATT","BBD","MDI","BDX","BFT","BHW","BMC","BRS","BOS","BOW","LRQ","CAR","MDV","CDR","CIG","CLE",
    "CMP","COG","CPD","CRM","DCR","DOM","EAT","EKP","ELT","ENE","ENI","ERB","ETL","FON","FRO","FSG","FTE","LES","GPW","HDR",
    "HEL","HRP","HRS","IMC","IMP","INC","ING","INK","INL","INP","IPE","ITB","IZS","JSW","FAB","KGN","RWL","KOM","KPD","KPL",
    "KRK","KRU","KSG","KTY","LBT","LBW","DVL","LEN","LPP","LTX","LWB","MBR","MCI","MCR","MEX","MIR","GKI","MLK","MNC","MON",
    "MRB","MSP","MSW","MSZ","NEU","3RG","NTT","NVA","ODL","OTM","PAT","PCE","PEP","PHN","PJP","PLZ","FHB","PRM","PPS",
    "PRT","QRS","NVG","RBW","RLP","RMK","RNK","SEL","SFS","SGN","SKA","ONO","SNK","SON","STF","STP","STX","SWG","TOA",
    "TPE","TRN","TSG","AAT","ULM","UNI","VIN","VOT","VOX","VRG","WAS","WIK","WLT","WWL","WXF","ZEP","MGT","ZMT","PGV","ZUE",
    "ZUK","DIG","GVT","OPM","OPN","PGM","SEK","DEL","FEE","CPI","NTC","MAB","MAK","OTS","TLX","TAR","PEN","APE","MFO","BMX",
    "BLO","SVE","CLD","CPR","EAH","IMS","MDG","PHR","DAT","RVU","SNT","VVD","ALL","11B","CSR","TXT","NWG",
    "MRC","ALI","TOR","PWX","BCM","CLC","DGA","MLG","MOJ","MZA","PCR","IFR","EQU","SNX","UNT","UNF","YAN","ZRE","SKH","VGO",
    "CDL","AWM","DEK","WPR","OML","XPL","ECB","ERG","BIP","1AT","PBX","WTN","LKD","ENT","XTB","ARH","APR","KMP","ASM",
    "BNP","IZO","KCI","GRX","SKL","SNW","YRL","PLW","ART","CLN","DNP","CAP","SCP","XTP","NNG","CBF","MVP","MOC","TEN","SVRS",
    "MLS","ULG","CRJ","PAS","PUR","MOV","4MS","ICE","BBT","SLV","DBE","GOP","SIM","SPR","GIF","ALE","DAD","PCF","ANR","HUG",
    "GMT","CTX","VRC","SHO","OND","DRG","CAV","WPR","CRI","URT","BCX","PTG","BCS","GPP","RND","NCL","SCW","MUR","QNA","ZAB",
    "DGN","ARL",
]


WIG_PART_SIZE = 165


def _split_into_parts(items: list[str], part_size: int) -> tuple[list[str], list[str], list[str]]:
    p1 = items[:part_size]
    p2 = items[part_size:part_size * 2]
    p3 = items[part_size * 2:]
    return p1, p2, p3


DAX40_SEARCH_TICKERS = [
    "ADS.DE","AIR.DE","ALV.DE","BAS.DE","BAYN.DE","BEI.DE","BMW.DE","BNR.DE","CON.DE","DB1.DE",
    "DBK.DE","DTE.DE","DTG.DE","EOAN.DE","FME.DE","FRE.DE","HEI.DE","HEN3.DE","HFG.DE","HNR1.DE",
    "IFX.DE","LIN.DE","MBG.DE","MRK.DE","MTX.DE","MUV2.DE","PAH3.DE","PUM.DE","QIA.DE","RWE.DE",
    "SAP.DE","SHL.DE","SIE.DE","SRT3.DE","SY1.DE","VNA.DE","VOW3.DE","ZAL.DE","ENR.DE","RHM.DE",
]

NDX100_SEARCH_TICKERS = [
    "AAPL.US","ABNB.US","ADBE.US","ADI.US","ADP.US","ADSK.US","AEP.US","ALNY.US","AMAT.US","AMD.US",
    "AMGN.US","AMZN.US","APP.US","ARM.US","ASML.US","AVGO.US","AXON.US","BKR.US","BKNG.US","CCEP.US",
    "CDNS.US","CEG.US","CHTR.US","CMCSA.US","COST.US","CPRT.US","CRWD.US","CSCO.US","CSGP.US","CSX.US",
    "CTAS.US","CTSH.US","DASH.US","DDOG.US","DXCM.US","EA.US","EXC.US","FANG.US","FAST.US","FER.US",
    "FTNT.US","GEHC.US","GILD.US","GOOG.US","GOOGL.US","HON.US","IDXX.US","INSM.US","INTC.US","INTU.US",
    "ISRG.US","KDP.US","KLAC.US","KHC.US","LIN.US","LRCX.US","MAR.US","MCHP.US","MDLZ.US","MELI.US",
    "META.US","MNST.US","MPWR.US","MRVL.US","MSFT.US","MSTR.US","MU.US","NFLX.US","NVDA.US","NXPI.US",
    "ODFL.US","ORLY.US","PANW.US","PAYX.US","PCAR.US","PDD.US","PEP.US","PLTR.US","PYPL.US","QCOM.US",
    "REGN.US","ROP.US","ROST.US","SBUX.US","SHOP.US","SNPS.US","STX.US","TMUS.US","TRI.US","TSLA.US",
    "TTWO.US","TXN.US","VRSK.US","VRTX.US","WBD.US","WDC.US","WMT.US","XEL.US","ZS.US",
]


GDP_PPP_VALUE = {
    "PL": 2120569,
    "US": 31821293,
    "DE": 6323531,
    "FR": 4657190,
    "CN": 43491520,
}

SUFFIX_TO_COUNTRY = {
    "WA": "PL",
    "US": "US",
    "DE": "DE",
    "PA": "FR",
    "SS": "CN",
}


@dataclass
class ScanResult:
    ticker: str
    side: str
    respect_days: int
    close: float
    start_date: str
    respect_months: float
    avg_turnover_10d_pln: float | None = None
    low_turnover_days_20d: int | None = None
    liquidity_threshold_10d_pln: float | None = None
    liquidity_threshold_20d_pln: float | None = None


@dataclass
class FlipResult:
    ticker: str
    previous_side: str
    current_side: str
    flip_date: str
    months_since_flip: float
    close: float
    retest_status: str = "no_breakout"
    retest_depth: str = "-"
    valid_retests_count: int = 0


@dataclass
class FiboScanResult:
    ticker: str
    direction: str
    status: str
    incline_start_date: str
    incline_end_date: str
    incline_duration_days: int
    decline_end_date: str
    decline_duration_days: int
    incline_decline_duration_ratio: float
    fib_23_6: float
    fib_38_2: float
    fib_61_8: float
    first_61_8_touch_date: str
    reversal_pattern_name: str
    stop_loss: float
    current_close: float


def _is_bullish_hammer(c: pd.Series) -> bool:
    body = abs(float(c["Close"] - c["Open"]))
    if body == 0:
        return False
    lower = min(float(c["Open"]), float(c["Close"])) - float(c["Low"])
    upper = float(c["High"]) - max(float(c["Open"]), float(c["Close"]))
    return lower >= 2 * body and upper <= body


def _is_bearish_shooting_star(c: pd.Series) -> bool:
    body = abs(float(c["Close"] - c["Open"]))
    if body == 0:
        return False
    upper = float(c["High"]) - max(float(c["Open"]), float(c["Close"]))
    lower = min(float(c["Open"]), float(c["Close"])) - float(c["Low"])
    return upper >= 2 * body and lower <= body


def _touches_level(c: pd.Series, level: float) -> bool:
    return float(c["Low"]) <= level <= float(c["High"])


def _is_bullish_piercing_line(c1: pd.Series, c2: pd.Series, level: float) -> bool:
    c1_open = float(c1["Open"])
    c1_close = float(c1["Close"])
    c2_open = float(c2["Open"])
    c2_close = float(c2["Close"])
    if not (c1_close < c1_open and c2_close > c2_open):
        return False
    midpoint_c1 = (c1_open + c1_close) / 2.0
    return (
        c2_open < c1_close
        and c2_close > midpoint_c1
        and (_touches_level(c1, level) or _touches_level(c2, level))
        and c2_close > level
    )

def _candle_parts(c: pd.Series) -> tuple[float, float, float, float, float]:
    o = float(c["Open"]); cl = float(c["Close"]); h = float(c["High"]); l = float(c["Low"])
    body = abs(cl - o)
    return o, cl, h, l, body

def _is_doji(c: pd.Series, tol: float = 0.15) -> bool:
    o, cl, h, l, body = _candle_parts(c)
    rng = max(h - l, 1e-9)
    return body / rng <= tol

def _is_bullish_harami(c1: pd.Series, c2: pd.Series, level: float) -> bool:
    o1, cl1, _, _, b1 = _candle_parts(c1); o2, cl2, _, _, b2 = _candle_parts(c2)
    if not (cl1 < o1 and cl2 > o2 and b2 < b1):
        return False
    lo1, hi1 = sorted((o1, cl1)); lo2, hi2 = sorted((o2, cl2))
    return lo1 <= lo2 and hi2 <= hi1 and (_touches_level(c1, level) or _touches_level(c2, level)) and cl2 > level

def _is_morning_star(c1: pd.Series, c2: pd.Series, c3: pd.Series, level: float, doji_middle: bool = False) -> bool:
    o1, cl1, _, _, b1 = _candle_parts(c1); _, _, _, _, b2 = _candle_parts(c2); o3, cl3, _, _, _ = _candle_parts(c3)
    c2_close = float(c2["Close"])
    if not (cl1 < o1 and cl3 > o3):
        return False
    if b2 >= b1 * 0.6:
        return False
    if doji_middle and not _is_doji(c2):
        return False
    if not (c2_close <= min(cl1, cl3)):
        return False
    mid1 = (o1 + cl1) / 2.0
    return cl3 > mid1 and (_touches_level(c1, level) or _touches_level(c2, level) or _touches_level(c3, level)) and cl3 > level

def _is_bearish_harami(c1: pd.Series, c2: pd.Series, level: float) -> bool:
    o1, cl1, _, _, b1 = _candle_parts(c1); o2, cl2, _, _, b2 = _candle_parts(c2)
    if not (cl1 > o1 and cl2 < o2 and b2 < b1):
        return False
    lo1, hi1 = sorted((o1, cl1)); lo2, hi2 = sorted((o2, cl2))
    return lo1 <= lo2 and hi2 <= hi1 and (_touches_level(c1, level) or _touches_level(c2, level)) and cl2 < level

def _is_dark_cloud_cover(c1: pd.Series, c2: pd.Series, level: float) -> bool:
    o1, cl1, _, _, _ = _candle_parts(c1); o2, cl2, _, _, _ = _candle_parts(c2)
    if not (cl1 > o1 and cl2 < o2 and o2 > cl1):
        return False
    mid1 = (o1 + cl1) / 2.0
    return cl2 < mid1 and (_touches_level(c1, level) or _touches_level(c2, level)) and cl2 < level

def _is_evening_star(c1: pd.Series, c2: pd.Series, c3: pd.Series, level: float, doji_middle: bool = False) -> bool:
    o1, cl1, _, _, b1 = _candle_parts(c1); _, _, _, _, b2 = _candle_parts(c2); o3, cl3, _, _, _ = _candle_parts(c3)
    c2_close = float(c2["Close"])
    if not (cl1 > o1 and cl3 < o3):
        return False
    if b2 >= b1 * 0.6:
        return False
    if doji_middle and not _is_doji(c2):
        return False
    if not (c2_close >= max(cl1, cl3)):
        return False
    mid1 = (o1 + cl1) / 2.0
    return cl3 < mid1 and (_touches_level(c1, level) or _touches_level(c2, level) or _touches_level(c3, level)) and cl3 < level
def _latest_sideways_end_offset(df_slice: pd.DataFrame, max_days: int = 22, band_pct: float = 0.12) -> int | None:
    if len(df_slice) < max_days:
        return None
    highs = pd.to_numeric(df_slice["High"], errors="coerce").reset_index(drop=True)
    lows = pd.to_numeric(df_slice["Low"], errors="coerce").reset_index(drop=True)
    best_end: int | None = None
    for i in range(0, len(df_slice) - max_days + 1):
        hwin = highs.iloc[i:i + max_days]
        lwin = lows.iloc[i:i + max_days]
        hi = float(hwin.max())
        lo = float(lwin.min())
        mid = (hi + lo) / 2.0
        if mid <= 0:
            continue
        rng_pct = (hi - lo) / mid
        if rng_pct <= band_pct:
            best_end = i + max_days - 1
    return best_end


def _latest_sideways_window(df_slice: pd.DataFrame, max_days: int = 22, band_pct: float = 0.12) -> tuple[int, int, float, float, float] | None:
    if len(df_slice) < max_days:
        return None
    highs = pd.to_numeric(df_slice["High"], errors="coerce").reset_index(drop=True)
    lows = pd.to_numeric(df_slice["Low"], errors="coerce").reset_index(drop=True)
    best: tuple[int, int, float, float, float] | None = None
    for i in range(0, len(df_slice) - max_days + 1):
        hwin = highs.iloc[i:i + max_days]
        lwin = lows.iloc[i:i + max_days]
        hi = float(hwin.max())
        lo = float(lwin.min())
        mid = (hi + lo) / 2.0
        if mid <= 0:
            continue
        rng_pct = (hi - lo) / mid
        if rng_pct <= band_pct:
            end = i + max_days - 1
            # keep the tightest qualifying window as most diagnostic
            if best is None or rng_pct < best[4]:
                best = (i, end, hi, lo, rng_pct)
    return best


def _has_long_sideways(df_slice: pd.DataFrame, max_days: int = 22, band_pct: float = 0.12) -> bool:
    if len(df_slice) < max_days:
        return False
    return _latest_sideways_end_offset(df_slice, max_days=max_days, band_pct=band_pct) is not None


def _select_impulse_start_long(w: pd.DataFrame, peak_idx: int, min_days: int) -> int | None:
    low = pd.to_numeric(w["Low"], errors="coerce")
    left = max(0, peak_idx - 140)
    right = peak_idx - min_days
    if right <= left:
        return None
    # If a long sideways block exists before the selected peak, treat the breakout
    # after that block as a newer impulse and avoid anchoring to very old lows.
    seg = w.iloc[left:peak_idx + 1]
    sideways_end = _latest_sideways_end_offset(seg, max_days=22, band_pct=0.12)
    if sideways_end is not None:
        candidate_left = left + sideways_end + 1
        if candidate_left < right:
            left = candidate_left
    # Use the lowest low in the allowed pre-peak window as impulse base.
    return int(low.iloc[left:right + 1].idxmin())


def _select_peak_long(w: pd.DataFrame, min_incline_days: int, min_tail_bars: int = 8) -> int | None:
    high = pd.to_numeric(w["High"], errors="coerce")
    if len(high) < min_incline_days + 10:
        return None
    left = min_incline_days
    right = len(high) - min_tail_bars
    best_idx = None
    best_score = -1e9
    global_max = float(high.iloc[left:right].max())
    if global_max <= 0:
        return None
    near_top_idxs: list[int] = []
    near_top_threshold = global_max * 0.92
    recent_near_top_idxs: list[int] = []
    recent_left = max(left, right - 35)
    for i in range(left, right):
        win_l = max(0, i - 5)
        win_r = min(len(high), i + 6)
        if float(high.iloc[i]) < float(high.iloc[win_l:win_r].max()):
            continue
        if float(high.iloc[i]) >= near_top_threshold:
            near_top_idxs.append(i)
            if i >= recent_left and float(high.iloc[i]) >= (global_max * 0.97):
                recent_near_top_idxs.append(i)
        recency = i / max(len(high) - 1, 1)
        prominence = float(high.iloc[i]) / max(float(high.iloc[max(0, i - 20):i + 1].mean()), 1e-9)
        height_rank = float(high.iloc[i]) / global_max
        # Prefer recent dominant highs; keep strong weight on recency to avoid stale peaks.
        score = prominence * 0.9 + height_rank * 1.0 + recency * 0.7
        if score > best_score:
            best_score = score
            best_idx = i
    if recent_near_top_idxs:
        return max(recent_near_top_idxs)
    if near_top_idxs:
        return max(near_top_idxs)
    return best_idx



def _reverse_stooq_symbol(symbol: str) -> str | None:
    target = (symbol or "").strip().upper()
    for key, value in COMMODITY_STOOQ_MAP.items():
        if str(value).upper() == target:
            return key.upper()
    return None


def _normalize_commodity_symbol(raw: str) -> str:
    cleaned = (raw or "").strip().upper().replace(" ", "_")
    aliases = {
        "S&P500": "US500",
        "SP500": "US500",
        "CRUDE_OIL": "CRUDE_OIL",
        "CRUDEOIL": "CRUDE_OIL",
        "NATURAL_GAS": "NATURAL_GAS",
        "NATGAS": "NATURAL_GAS",
        "GOLD": "XAUUSD",
        "SILVER": "XAGUSD",
    }
    cleaned = aliases.get(cleaned, cleaned)
    available = set(COMMODITY_YAHOO_MAP.keys()) | set(COMMODITY_STOOQ_MAP.keys())
    if cleaned in available:
        return cleaned
    compact = cleaned.replace("_", "")
    for key in available:
        if key.replace("_", "") == compact:
            return key
    return cleaned

def _load_py_module(path: Path):
    spec = util.spec_from_file_location(f"cfg_{path.stem}", path)
    if not spec or not spec.loader:
        raise ValueError(f"Unable to load config module: {path}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _members_from_configs(scope: str) -> list[str]:
    directory = PROJECT_ROOT / "configs" / scope
    members: list[str] = []
    for path in sorted(directory.glob("*.py")):
        module = _load_py_module(path)
        config = module.TradingConfig()
        if scope == "forex":
            members.append((getattr(config, "pair", "").replace("/", "") or path.stem).upper())
        elif scope == "commodities":
            value = getattr(config, "symbol", "") or getattr(config, "name", "") or path.stem
            members.append(_normalize_commodity_symbol(str(value)))
        else:
            members.append((getattr(config, "symbol", "") or getattr(config, "name", "") or path.stem).upper())
    dedup=[]
    seen=set()
    for m in members:
        if m and m not in seen:
            seen.add(m)
            dedup.append(m)
    return dedup


def _get_members(target: str) -> tuple[str, list[str], str, str | None]:
    normalized = (target or "").strip().lower()
    if normalized == "wig":
        print("[search] WIG has a large universe. For VPN/rate-limit safety use: wig_part1, wig_part2, wig_part3.")
        return "WIG", WIG_SEARCH_TICKERS, "manual WIG list", ".WA"
    if normalized in {"wig_part1", "wig1", "wig_p1"}:
        p1, _, _ = _split_into_parts(WIG_SEARCH_TICKERS, WIG_PART_SIZE)
        return "WIG_PART1", p1, "manual WIG list part1", ".WA"
    if normalized in {"wig_part2", "wig2", "wig_p2"}:
        _, p2, _ = _split_into_parts(WIG_SEARCH_TICKERS, WIG_PART_SIZE)
        return "WIG_PART2", p2, "manual WIG list part2", ".WA"
    if normalized in {"wig_part3", "wig3", "wig_p3"}:
        _, _, p3 = _split_into_parts(WIG_SEARCH_TICKERS, WIG_PART_SIZE)
        return "WIG_PART3", p3, "manual WIG list part3", ".WA"
    if normalized in {"dax", "dax40"}:
        return "DAX40", DAX40_SEARCH_TICKERS, "manual DAX40 list", None
    if normalized in {"ndx", "us100", "nasdaq100", "nasdaq-100"}:
        return "NDX100", NDX100_SEARCH_TICKERS, "manual NDX100 list", None
    if normalized in {"commodities", "commidities", "commodity"}:
        return "commodities", COMMODITIES_SEARCH_TICKERS, "commodity maps", None
    if normalized in {"forex", "fx"}:
        return "forex", _members_from_configs("forex"), "configs", None
    if normalized in {"indexes", "indices", "index"}:
        return "indexes", INDEXES_SEARCH_TICKERS, "commodity maps", None

    if INDEX_MEMBERS_FILE.exists():
        payload = json.loads(INDEX_MEMBERS_FILE.read_text(encoding="utf-8"))
        indices = payload.get("indices", {})
        for key, data in indices.items():
            if key.lower() == normalized:
                return key, [x.upper() for x in data.get("tickers", [])], payload.get("source", "local file"), data.get("exchange_suffix")
    # Fallback: traktuj input jako pojedynczy ticker/symbol do skanowania.
    raw = (target or "").strip()
    if raw:
        return "single", [raw.upper()], "direct symbol", None
    raise ValueError(f"Brak skonfigurowanej listy instrumentów dla: {target}")


def _ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    high9 = out["High"].rolling(9).max()
    low9 = out["Low"].rolling(9).min()
    high26 = out["High"].rolling(26).max()
    low26 = out["Low"].rolling(26).min()
    out["tenkan"] = (high9 + low9) / 2
    out["kijun"] = (high26 + low26) / 2
    span_a = ((out["tenkan"] + out["kijun"]) / 2).shift(26)
    span_b = ((out["High"].rolling(52).max() + out["Low"].rolling(52).min()) / 2).shift(26)
    out["cloud_top"] = pd.concat([span_a, span_b], axis=1).max(axis=1)
    out["cloud_bottom"] = pd.concat([span_a, span_b], axis=1).min(axis=1)
    return out.dropna(subset=["cloud_top", "cloud_bottom"])


def _qualifies(df: pd.DataFrame, min_days: int = 80) -> ScanResult | None:
    if len(df) < min_days + 2:
        return None

    body_high = df[["Open", "Close"]].max(axis=1)
    body_low = df[["Open", "Close"]].min(axis=1)
    top = df["cloud_top"]
    bottom = df["cloud_bottom"]

    # Dla trendu poniżej chmury: korpus może wejść w chmurę, ale nie może przebić górnej granicy.
    # Dla trendu powyżej chmury: korpus może wejść w chmurę, ale nie może przebić dolnej granicy.
    below_respected = body_high <= top
    above_respected = body_low >= bottom

    close = df["Close"]
    current_side = "below" if close.iloc[-1] < bottom.iloc[-1] else "above" if close.iloc[-1] > top.iloc[-1] else "inside"
    if current_side not in {"below", "above"}:
        return None

    respect_mask = below_respected if current_side == "below" else above_respected

    run = 0
    for ok in reversed(respect_mask.tolist()):
        if ok:
            run += 1
        else:
            break
    if run < min_days:
        return None

    window_start = len(df) - run

    # Start liczenia: świeca, na której korpus przebił odpowiednią granicę chmury
    # (dla below: przebicie dolnej linii chmury w dół; dla above: przebicie górnej linii chmury w górę).
    start_idx = window_start
    for i in range(window_start, len(df)):
        prev_i = i - 1
        if current_side == "below":
            crossed_now = body_high.iloc[i] < bottom.iloc[i]
            prev_not_below = True if i == 0 else body_high.iloc[prev_i] >= bottom.iloc[prev_i]
            if crossed_now and prev_not_below:
                start_idx = i
                break
        else:
            crossed_now = body_low.iloc[i] > top.iloc[i]
            prev_not_above = True if i == 0 else body_low.iloc[prev_i] <= top.iloc[prev_i]
            if crossed_now and prev_not_above:
                start_idx = i
                break

    start_ts = pd.to_datetime(df.iloc[start_idx]["Date"])
    end_ts = pd.to_datetime(df.iloc[-1]["Date"])
    months = ((end_ts - start_ts).days + 1) / 30.44

    return ScanResult(
        ticker="",
        side=current_side,
        respect_days=run,
        close=float(close.iloc[-1]),
        start_date=start_ts.strftime("%Y-%m-%d"),
        respect_months=round(months, 1),
    )




def _country_code_from_ticker(symbol: str) -> str:
    suffix = symbol.split(".")[-1].upper() if "." in symbol else "US"
    return SUFFIX_TO_COUNTRY.get(suffix, "US")


def _gdp_multiplier_for_ticker(symbol: str) -> float:
    pl = GDP_PPP_VALUE["PL"]
    cc = _country_code_from_ticker(symbol)
    return GDP_PPP_VALUE.get(cc, pl) / pl


def _compute_stock_liquidity_metrics(df: pd.DataFrame, fetch_symbol: str) -> tuple[float, int, float, float] | None:
    if "Close" not in df.columns or "Volume" not in df.columns or len(df) < 20:
        return None
    turnover_native = pd.to_numeric(df["Close"], errors="coerce") * pd.to_numeric(df["Volume"], errors="coerce")
    turnover_native = turnover_native.dropna()
    if len(turnover_native) < 20:
        return None
    try:
        cc = _country_code_from_ticker(fetch_symbol)
        country_to_currency = {
            "PL": "PLN",
            "US": "USD",
            "DE": "EUR",
            "FR": "EUR",
            "CN": "CNY",
        }
        currency = country_to_currency.get(cc, "USD")
        _, fx_to_pln = get_fx_to_pln_rate_yahoo(currency)
        fx_to_pln = float(fx_to_pln) if fx_to_pln and fx_to_pln > 0 else 1.0
    except Exception:
        fx_to_pln = 1.0
    turnover_pln = turnover_native * fx_to_pln
    avg_10d = float(turnover_pln.tail(10).mean())
    gdp_mult = _gdp_multiplier_for_ticker(fetch_symbol)
    threshold_10d = 700000.0 * gdp_mult
    threshold_20d = 300000.0 * gdp_mult
    below_20d = int((turnover_pln.tail(20) < threshold_20d).sum())
    return avg_10d, below_20d, threshold_10d, threshold_20d


def _scan_one(ticker: str, group_name: str, exchange_suffix: str | None) -> tuple[str, ScanResult | None, FlipResult | None, str | None, str]:
    if group_name == "forex":
        instrument = "forex"
    elif group_name == "commodities":
        instrument = "commodity"
    elif group_name == "indexes":
        instrument = "commodity"
    elif group_name == "single":
        detected = detect_instrument_type(ticker, None)
        instrument = "commodity" if detected == "commodity" else ("forex" if detected == "forex" else "stock")
    else:
        instrument = "stock"

    fetch_symbol = ticker
    display_symbol = fetch_symbol
    if instrument == "stock" and exchange_suffix and not ticker.endswith(exchange_suffix.upper()):
        fetch_symbol = f"{ticker}{exchange_suffix}"
        display_symbol = fetch_symbol
    if instrument == "commodity":
        t_upper = ticker.upper()
        mapped = COMMODITY_STOOQ_MAP.get(t_upper)
        # Requested explicit stooq symbols for scanner output/fetching.
        if t_upper == "ALUMINIUM":
            mapped = "al.f"
        elif t_upper == "COPPER":
            mapped = "hg.f"
        if mapped:
            fetch_symbol = mapped.upper()
            display_symbol = fetch_symbol
        elif group_name == "single":
            canonical = _reverse_stooq_symbol(ticker)
            if canonical:
                display_symbol = canonical

    try:
        df, _, meta = load_or_update_daily_data(symbol=fetch_symbol, instrument_type=instrument, persist=True)
        source_label = str((meta or {}).get("source", "unknown")).lower()
        enriched = _ichimoku(df)
        result = _qualifies(enriched)
        flip = _flip_after_long_respect(enriched)
        if result:
            result.ticker = ticker
            if instrument == "stock":
                metrics = _compute_stock_liquidity_metrics(df, fetch_symbol)
                if metrics is None:
                    return display_symbol, None, flip, "insufficient turnover data", source_label
                avg_10d, below_20d, threshold_10d, threshold_20d = metrics
                result.avg_turnover_10d_pln = avg_10d
                result.low_turnover_days_20d = below_20d
                result.liquidity_threshold_10d_pln = threshold_10d
                result.liquidity_threshold_20d_pln = threshold_20d
                if avg_10d < threshold_10d or below_20d > 2:
                    return display_symbol, None, flip, (
                        f"liquidity filter failed (avg10={avg_10d:.0f} < {threshold_10d:.0f} or below20d={below_20d} > 2)"
                    ), source_label
        if flip:
            flip.ticker = ticker
        return display_symbol, result, flip, None, source_label
    except Exception as exc:
        return display_symbol, None, None, str(exc), "unknown"


def _rate_limit_detected(err: str | None) -> bool:
    text = (err or "").lower()
    return "rate limit" in text or "captcha" in text or "przekroczony dzienny limit" in text


def _stooq_symbol_for_link(ticker: str) -> str:
    raw = (ticker or "").strip().upper()
    # Commodity/index aliases -> exact stooq symbols for chart links.
    mapped = COMMODITY_STOOQ_MAP.get(raw)
    if mapped:
        # Requested overrides
        if raw == "ALUMINIUM":
            return "al.f"
        if raw == "COPPER":
            return "hg.f"
        return str(mapped).lower()
    return raw.lower()


def _stooq_chart_url(ticker: str) -> str:
    symbol = _stooq_symbol_for_link(ticker)
    symbol_q = quote(symbol, safe="")
    return f"https://stooq.pl/q/a2/?s={symbol_q}&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1"


def _compact_error(err: str | None) -> str:
    text = (err or "").strip()
    if "url=" in text:
        return text.split(" | url=", 1)[0]
    if " Tried: " in text:
        return text.split(" Tried: ", 1)[0]
    return text


def _scan_source_label(src: str) -> str:
    s = (src or "").lower()
    if s in {"stooq_web"}:
        return "UI"
    if s in {"stooq", "yahoo", "cache"}:
        return "API"
    return s.upper() or "UNKNOWN"


def _print_results_with_links(results: list[ScanResult]) -> list[str]:
    print(f"\n{ANSI_BOLD}{ANSI_GREEN}WYNIKI (instrumenty spełniające warunki):{ANSI_RESET}")
    if not results:
        print("Brak wyników.")
        return []
    print(f"{'Ticker':<10} {'Pozycja':<8} {'Świece':<8} {'Mies.':<6} {'Start':<12} {'Close':>10} {'Avg10d PLN':>14} {'Low<Th20':>10} {'Link':<0}")
    print("-" * 140)
    sorted_rows = sorted(results, key=lambda r: r.respect_days, reverse=True)
    links: list[str] = []
    for row in sorted_rows:
        avg_10d = f"{row.avg_turnover_10d_pln:,.0f}" if row.avg_turnover_10d_pln is not None else "-"
        low_20 = str(row.low_turnover_days_20d) if row.low_turnover_days_20d is not None else "-"
        link = _stooq_chart_url(row.ticker)
        links.append(link)
        print(f"{row.ticker:<10} {row.side:<8} {row.respect_days:<8} {row.respect_months:<6.1f} {row.start_date:<12} {row.close:>10.4f} {avg_10d:>14} {low_20:>10} {ANSI_CYAN}{link}{ANSI_RESET}")
    return links


def _print_flip_results_with_links(flip_results: list[FlipResult]) -> list[str]:
    print(f"\n{ANSI_BOLD}{ANSI_YELLOW}WYNIKI 2 (po >=4 mies. po jednej stronie, potem wybicie i utrzymanie po drugiej):{ANSI_RESET}")
    if not flip_results:
        print("Brak wyników.")
        return []
    print(f"{'Ticker':<10} {'Było':<8} {'Jest':<8} {'Data wybicia':<12} {'Mies. od wybicia':<16} {'Retest status':<44} {'Count':<6} {'Close':>10} {'Link':<0}")
    print("-" * 150)
    links: list[str] = []
    for row in sorted(flip_results, key=lambda r: r.months_since_flip, reverse=True):
        link = _stooq_chart_url(row.ticker)
        links.append(link)
        print(
            f"{row.ticker:<10} {row.previous_side:<8} {row.current_side:<8} {row.flip_date:<12} {row.months_since_flip:<16.1f} "
            f"{row.retest_status:<44} {row.valid_retests_count:<6} {row.close:>10.4f} {ANSI_CYAN}{link}{ANSI_RESET}"
        )
    return links


def _flip_after_long_respect(df: pd.DataFrame, min_days: int = 80) -> FlipResult | None:
    if len(df) < min_days + 5:
        return None
    close = df["Close"]
    top = df["cloud_top"]
    bottom = df["cloud_bottom"]

    body_high = df[["Open", "Close"]].max(axis=1)
    body_low = df[["Open", "Close"]].min(axis=1)

    # Respect definitions match _qualifies:
    # - trend below: body may enter cloud, but cannot break above cloud top
    # - trend above: body may enter cloud, but cannot break below cloud bottom
    below_respected = body_high <= top
    above_respected = body_low >= bottom

    flip_idx: int | None = None
    previous_side: str | None = None
    current_side: str | None = None

    # Prefer latest valid flip below->above.
    for i in range(len(df) - 1, 0, -1):
        crossed_up = body_low.iloc[i] > top.iloc[i] and body_low.iloc[i - 1] <= top.iloc[i - 1]
        if not crossed_up:
            continue
        if not bool(above_respected.iloc[i:].all()):
            continue
        prev_run = 0
        j = i - 1
        while j >= 0 and bool(below_respected.iloc[j]):
            prev_run += 1
            j -= 1
        if prev_run >= min_days:
            flip_idx = i
            previous_side = "below"
            current_side = "above"
            break

    # If not found, try latest valid flip above->below.
    if flip_idx is None:
        for i in range(len(df) - 1, 0, -1):
            crossed_down = body_high.iloc[i] < bottom.iloc[i] and body_high.iloc[i - 1] >= bottom.iloc[i - 1]
            if not crossed_down:
                continue
            if not bool(below_respected.iloc[i:].all()):
                continue
            prev_run = 0
            j = i - 1
            while j >= 0 and bool(above_respected.iloc[j]):
                prev_run += 1
                j -= 1
            if prev_run >= min_days:
                flip_idx = i
                previous_side = "above"
                current_side = "below"
                break

    if flip_idx is None or previous_side is None or current_side is None:
        return None

    flip_ts = pd.to_datetime(df.iloc[flip_idx]["Date"])
    end_ts = pd.to_datetime(df.iloc[-1]["Date"])
    months = ((end_ts - flip_ts).days + 1) / 30.44

    flip = FlipResult("", previous_side, current_side, flip_ts.strftime("%Y-%m-%d"), round(months, 1), float(close.iloc[-1]))
    flip.retest_status, flip.retest_depth, flip.valid_retests_count = _detect_ichimoku_retest(df, flip_idx, current_side)
    return flip


def _classify_retest_depth(cloud_top: float, cloud_bottom: float, probe_price: float, side: str) -> str:
    thickness = max(cloud_top - cloud_bottom, 1e-9)
    rel = (cloud_top - probe_price) / thickness if side == "above" else (probe_price - cloud_bottom) / thickness
    shallow_limit = 0.2
    medium_limit = 0.6
    if rel <= shallow_limit:
        return "shallow"
    if thickness < probe_price * 0.01:
        return "deep"
    if rel <= medium_limit:
        return "medium"
    return "deep"


def _detect_ichimoku_retest(df: pd.DataFrame, flip_idx: int, current_side: str) -> tuple[str, str, int]:
    body_high = df[["Open", "Close"]].max(axis=1)
    body_low = df[["Open", "Close"]].min(axis=1)
    top = df["cloud_top"]
    bottom = df["cloud_bottom"]
    post = range(flip_idx + 1, len(df))
    if flip_idx <= 0 or (flip_idx + 1) >= len(df):
        return "breakout_confirmed", "-", 0

    waiting = False
    touch_idxs: list[int] = []
    for i in post:
        if current_side == "above":
            if body_low.iloc[i] < bottom.iloc[i]:
                return "invalidated_by_body_break_through_cloud", "-", 0
            touched = float(df["Low"].iloc[i]) <= float(top.iloc[i])
        else:
            if body_high.iloc[i] > top.iloc[i]:
                return "invalidated_by_body_break_through_cloud", "-", 0
            touched = float(df["High"].iloc[i]) >= float(bottom.iloc[i])
        if touched:
            waiting = True
            touch_idxs.append(i)

    if not waiting:
        return "breakout_confirmed", "-", 0

    first_touch = touch_idxs[0]
    latest_touch = touch_idxs[-1]
    w_start = max(first_touch - 2, flip_idx + 1)
    w = df.iloc[w_start: latest_touch + 1].reset_index(drop=True)
    if len(w) < 2:
        return "returned_to_cloud_waiting_for_pattern", "-", 0

    pattern_idx = -1
    if current_side == "above":
        for i in range(0, len(w)):
            if _is_bullish_hammer(w.iloc[i]):
                pattern_idx = i; break
        if pattern_idx < 0:
            for i in range(1, len(w)):
                if _is_bullish_harami(w.iloc[i - 1], w.iloc[i], float(w["cloud_top"].iloc[i])):
                    pattern_idx = i; break
    else:
        for i in range(0, len(w)):
            if _is_bearish_shooting_star(w.iloc[i]):
                pattern_idx = i; break
        if pattern_idx < 0:
            for i in range(1, len(w)):
                if _is_bearish_harami(w.iloc[i - 1], w.iloc[i], float(w["cloud_bottom"].iloc[i])):
                    pattern_idx = i; break

    if pattern_idx < 0:
        return "returned_to_cloud_waiting_for_pattern", "-", 0

    pattern_abs = w_start + pattern_idx
    local_reaction_abs = int(df["Low"].iloc[first_touch:latest_touch + 1].idxmin()) if current_side == "above" else int(df["High"].iloc[first_touch:latest_touch + 1].idxmax())
    if pattern_abs - local_reaction_abs >= 2:
        return "invalid_pattern_too_late", "-", 0

    probe = float(df["Low"].iloc[pattern_abs]) if current_side == "above" else float(df["High"].iloc[pattern_abs])
    depth = _classify_retest_depth(float(top.iloc[pattern_abs]), float(bottom.iloc[pattern_abs]), probe, current_side)
    return f"{depth}_retest_pattern", depth, 1


def run_ichimoku_search(target: str) -> int:
    group_name, members, source, exchange_suffix = _get_members(target)
    print(f"[search] grupa={group_name}, liczba instrumentów={len(members)}, źródło={source}")
    results: list[ScanResult] = []
    flip_results: list[FlipResult] = []

    if group_name == "WIG":
        print("[search] WIG mode: xdist-style parallel chunks with VPN confirmation between chunks.")
        chunk_size = WIG_PART_SIZE
        chunks = [members[i:i + chunk_size] for i in range(0, len(members), chunk_size)]
        for chunk_idx, chunk in enumerate(chunks, start=1):
            print(f"[search] starting chunk {chunk_idx}/{len(chunks)} (size={len(chunk)})")
            max_workers = min(6, max(2, (os.cpu_count() or 4) // 2), len(chunk))
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                fut_map = {
                    ex.submit(_scan_one, ticker, group_name, exchange_suffix): (idx, ticker)
                    for idx, ticker in enumerate(chunk, start=(chunk_idx - 1) * chunk_size + 1)
                }
                for fut in as_completed(fut_map):
                    idx, ticker = fut_map[fut]
                    display_symbol, result, flip, err, src = fut.result()
                    print(f"[{idx}/{len(members)}] skanuję {ticker} ({display_symbol})... [skanuję przez {_scan_source_label(src)}]")
                    if err:
                        print(f"  pominięto ({_compact_error(err)})")
                    elif result:
                        results.append(result)
                    if flip:
                        flip_results.append(flip)
            if chunk_idx < len(chunks):
                try:
                    answer = input("[search] Chunk done. Change VPN location and continue with next chunk? [y/N]: ").strip().lower()
                except EOFError:
                    answer = "n"
                if answer != "y":
                    print("[search] Scan paused/stopped by user before next WIG chunk.")
                    break

        SEARCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_csv = SEARCH_OUTPUT_DIR / f"search_{group_name.lower()}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
        with out_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["ticker", "side", "respect_days", "respect_months", "start_date", "close", "avg_turnover_10d_pln", "below_threshold_days_20d", "threshold_10d_pln", "threshold_20d_pln"])
            for row in sorted(results, key=lambda r: r.respect_days, reverse=True):
                writer.writerow([row.ticker, row.side, row.respect_days, f"{row.respect_months:.1f}", row.start_date, f"{row.close:.4f}", f"{row.avg_turnover_10d_pln:.2f}" if row.avg_turnover_10d_pln is not None else "", row.low_turnover_days_20d if row.low_turnover_days_20d is not None else "", f"{row.liquidity_threshold_10d_pln:.2f}" if row.liquidity_threshold_10d_pln is not None else "", f"{row.liquidity_threshold_20d_pln:.2f}" if row.liquidity_threshold_20d_pln is not None else ""])
        links_primary = _print_results_with_links(results)
        print(f"\nZapisano CSV: {out_csv}")
        print(f"Źródło danych CSV instrumentów: {UNIFIED_DATA_DIR}")
        links_flip = _print_flip_results_with_links(flip_results)
        out_csv_flip = SEARCH_OUTPUT_DIR / f"search_{group_name.lower()}_{datetime.now(UTC).strftime('%Y%m%d')}_flips.csv"
        with out_csv_flip.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["ticker", "previous_side", "current_side", "flip_date", "months_since_flip", "close"])
            for row in sorted(flip_results, key=lambda r: r.months_since_flip, reverse=True):
                writer.writerow([row.ticker, row.previous_side, row.current_side, row.flip_date, f"{row.months_since_flip:.1f}", f"{row.close:.4f}"])
        print(f"Zapisano CSV #2: {out_csv_flip}")
        all_links = links_primary + [x for x in links_flip if x not in links_primary]
        if all_links:
            try:
                open_all = input("Czy otworzyć wszystkie linki? [y/N]: ").strip().lower()
            except EOFError:
                open_all = "n"
            if open_all == "y":
                for link in all_links:
                    webbrowser.open_new_tab(link)
        return 0

    # Probe first symbol for rate limits/captcha; if present use sequential mode, otherwise parallel mode.
    first = members[0]
    print(f"[1/{len(members)}] skanuję {first}...")
    display_symbol, first_result, first_flip, first_err, first_source = _scan_one(first, group_name, exchange_suffix)
    print(f"[1/{len(members)}] skanuję {first} ({display_symbol})... [skanuję przez {_scan_source_label(first_source)}]")
    sequential = _rate_limit_detected(first_err)
    if group_name == "WIG":
        sequential = True
        print("[search] WIG mode: sequential scan with pause every 165 requests for VPN rotation.")
    elif group_name.startswith("WIG_PART"):
        sequential = False
        print("[search] WIG_PART mode: parallel scan enabled (xdist-friendly split batch).")
    if first_err:
        print(f"  pominięto ({first_err})")
    elif first_result:
        results.append(first_result)
    if first_flip:
        flip_results.append(first_flip)

    rest = members[1:]
    if sequential or len(rest) == 0:
        if sequential:
            print("[search] rate-limit/captcha detected -> switching to sequential mode.")
        for offset, ticker in enumerate(rest, start=2):
            if group_name == "WIG" and offset in {166, 331}:
                try:
                    answer = input(f"[search] Reached {offset-1} WIG checks. Change VPN location and continue? [y/N]: ").strip().lower()
                except EOFError:
                    answer = "n"
                if answer != "y":
                    print("[search] Scan paused/stopped by user before next WIG chunk.")
                    break
            display_symbol, result, flip, err, src = _scan_one(ticker, group_name, exchange_suffix)
            print(f"[{offset}/{len(members)}] skanuję {ticker} ({display_symbol})... [skanuję przez {_scan_source_label(src)}]")
            if err:
                print(f"  pominięto ({_compact_error(err)})")
            elif result:
                results.append(result)
            if flip:
                flip_results.append(flip)
    else:
        max_workers = min(6, max(2, (os.cpu_count() or 4) // 2), len(rest))
        print(f"[search] no rate-limit on probe -> parallel mode ({max_workers} workers).")
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            fut_map = {ex.submit(_scan_one, ticker, group_name, exchange_suffix): (idx, ticker) for idx, ticker in enumerate(rest, start=2)}
            for fut in as_completed(fut_map):
                idx, ticker = fut_map[fut]
                display_symbol, result, flip, err, src = fut.result()
                print(f"[{idx}/{len(members)}] skanuję {ticker} ({display_symbol})... [skanuję przez {_scan_source_label(src)}]")
                if err:
                    print(f"  pominięto ({_compact_error(err)})")
                elif result:
                    results.append(result)
                if flip:
                    flip_results.append(flip)

    SEARCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = SEARCH_OUTPUT_DIR / f"search_{group_name.lower()}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ticker", "side", "respect_days", "respect_months", "start_date", "close", "avg_turnover_10d_pln", "below_threshold_days_20d", "threshold_10d_pln", "threshold_20d_pln"])
        for row in sorted(results, key=lambda r: r.respect_days, reverse=True):
            writer.writerow([row.ticker, row.side, row.respect_days, f"{row.respect_months:.1f}", row.start_date, f"{row.close:.4f}", f"{row.avg_turnover_10d_pln:.2f}" if row.avg_turnover_10d_pln is not None else "", row.low_turnover_days_20d if row.low_turnover_days_20d is not None else "", f"{row.liquidity_threshold_10d_pln:.2f}" if row.liquidity_threshold_10d_pln is not None else "", f"{row.liquidity_threshold_20d_pln:.2f}" if row.liquidity_threshold_20d_pln is not None else ""])

    links_primary = _print_results_with_links(results)
    print(f"\nZapisano CSV: {out_csv}")
    print(f"Źródło danych CSV instrumentów: {UNIFIED_DATA_DIR}")

    links_flip = _print_flip_results_with_links(flip_results)

    out_csv_flip = SEARCH_OUTPUT_DIR / f"search_{group_name.lower()}_{datetime.now(UTC).strftime('%Y%m%d')}_flips.csv"
    with out_csv_flip.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ticker", "previous_side", "current_side", "flip_date", "months_since_flip", "close"])
        for row in sorted(flip_results, key=lambda r: r.months_since_flip, reverse=True):
            writer.writerow([row.ticker, row.previous_side, row.current_side, row.flip_date, f"{row.months_since_flip:.1f}", f"{row.close:.4f}"])
    print(f"Zapisano CSV #2: {out_csv_flip}")
    all_links = links_primary + [x for x in links_flip if x not in links_primary]
    if all_links:
        try:
            open_all = input("Czy otworzyć wszystkie linki? [y/N]: ").strip().lower()
        except EOFError:
            open_all = "n"
        if open_all == "y":
            for link in all_links:
                webbrowser.open_new_tab(link)
    return 0


def _find_fibo_setup(df: pd.DataFrame, direction: str = "long", end_offset: int = 0, explain: list[str] | None = None) -> FiboScanResult | None:
    def _log(msg: str) -> None:
        if explain is not None:
            explain.append(msg)
    if len(df) < 120:
        _log("Rejected: less than 120 candles.")
        return None
    tail_len = 220 + max(end_offset, 0)
    w_full = df.tail(tail_len).reset_index(drop=True)
    if end_offset > 0:
        w = w_full.iloc[:-end_offset].reset_index(drop=True)
    else:
        w = w_full
    close = w["Close"]
    high = w["High"]
    low = w["Low"]
    if direction == "long":
        min_incline_days = 10  # ~2 weeks
        min_correction_days = 2
        i_peak_sel = _select_peak_long(w, min_incline_days, min_tail_bars=min_correction_days)
        if i_peak_sel is None:
            _log("Rejected long: no valid peak selected.")
            return None
        i_peak = int(i_peak_sel)
        i_start = _select_impulse_start_long(w, i_peak, min_incline_days)
        if i_start is None or i_peak <= i_start + min_incline_days:
            left_fallback = max(0, i_peak - 140)
            right_fallback = i_peak - min_incline_days
            if right_fallback > left_fallback:
                i_start = int(low.iloc[left_fallback:right_fallback + 1].idxmin())
                _log(f"Long: fallback impulse start chosen at index={i_start}.")
            else:
                _log("Rejected long: invalid impulse start/peak distance.")
                return None
        if i_peak <= i_start + min_incline_days:
            _log("Rejected long: invalid impulse start/peak distance.")
            return None
        i_end = len(w) - 1
        corr_bars = i_end - i_peak
        early_correction_accepted = False
        if corr_bars < 8:
            corr_low_early = float(low.iloc[i_peak:i_end + 1].min())
            peak_high = float(high.iloc[i_peak])
            early_decline_pct = (peak_high - corr_low_early) / max(peak_high, 1e-9)
            if corr_bars >= min_correction_days and early_decline_pct >= 0.05:
                early_correction_accepted = True
                _log(
                    "Long: accepting early correction leg "
                    f"({corr_bars} bars, decline={early_decline_pct * 100:.2f}%)."
                )
            else:
                _log("Rejected long: correction leg too short (<8 bars).")
                return None
        # Extend fib-base search left of the selected impulse start.
        # In strong accelerations, impulse-start selector can land on a later pullback
        # (e.g. 2026-04-16) while the true swing base is a bit earlier (e.g. 2026-04-07).
        # We cap the extension to keep the setup local and avoid very old anchors.
        pre_start_left = max(0, min(i_start - 6, i_peak - 30))
        fib_start_idx = int(low.iloc[pre_start_left:i_start + 1].idxmin())
        _log(
            f"Long: fib start low searched in [{pre_start_left}, {i_start}] "
            f"(peak_idx={i_peak}) -> idx={fib_start_idx}."
        )
        i_start = fib_start_idx
        fib_start = float(low.iloc[fib_start_idx])
        fib_end = float(high.iloc[i_peak])
        # Guard against stale multi-cycle impulses:
        # if an earlier local peak (after the chosen start, before the chosen peak)
        # already completed a >=61.8 correction, this start is too old.
        # Skip guard checks for short pre-impulses (<= ~2 weeks) to avoid rejecting
        # noisy early bumps that do not represent a full impulse leg.
        min_stale_guard_days = 10  # ~2 weeks
        stale_cycle = False
        for p in range(i_start + min_incline_days, max(i_start + min_incline_days, i_peak - 8)):
            if (p - i_start) <= min_stale_guard_days:
                continue
            win_l = max(i_start, p - 4)
            win_r = min(i_peak, p + 5)
            if float(high.iloc[p]) < float(high.iloc[win_l:win_r].max()):
                continue
            p_high = float(high.iloc[p])
            p_base = fib_start
            p_rng = p_high - p_base
            if p_rng <= 0:
                continue
            p_fib_618 = p_high - p_rng * 0.618
            post_low = float(low.iloc[p:i_peak + 1].min())
            if post_low <= p_fib_618:
                stale_cycle = True
                _log(f"Rejected long: stale impulse start (earlier peak idx={p} already corrected below its 61.8).")
                break
        if stale_cycle:
            return None
        rng = fib_end - fib_start
        if rng <= 0:
            _log("Rejected long: non-positive fib range.")
            return None
        fib_236 = fib_end - rng * 0.236
        fib_382 = fib_end - rng * 0.382
        fib_500 = fib_end - rng * 0.5
        fib_618 = fib_end - rng * 0.618
        corr_low = float(low.iloc[i_peak:i_end + 1].min())
        correction_seg = w.iloc[i_peak:i_end + 1].reset_index(drop=True)
        correction_sideways = _latest_sideways_window(correction_seg, max_days=22, band_pct=0.12)
        if correction_sideways is not None:
            s, e, hi, lo, rng_pct = correction_sideways
            start_date = str(pd.to_datetime(correction_seg.iloc[s]["Date"]).date())
            end_date = str(pd.to_datetime(correction_seg.iloc[e]["Date"]).date())
            _log(
                "Rejected long: correction is sideways/flat. "
                f"window={s}-{e} ({start_date}..{end_date}), "
                f"hi={hi:.2f}, lo={lo:.2f}, range_pct={rng_pct * 100:.2f}% <= 12.00%."
            )
            return None
        if corr_low > fib_236:
            _log("Rejected long: correction never reached 23.6.")
            return None
        if _has_long_sideways(w.iloc[i_start:i_peak + 1], max_days=30, band_pct=0.06):
            _log("Rejected long: impulse is sideways/flat.")
            return None
        all_touch_idxs = [i for i in range(i_peak, i_end + 1) if low.iloc[i] <= fib_618 <= high.iloc[i]]
        touch_idxs: list[int] = []
        if all_touch_idxs:
            first_touch = all_touch_idxs[0]
            for i in range(first_touch, min(first_touch + 3, i_end + 1)):
                if low.iloc[i] <= fib_618 <= high.iloc[i]:
                    touch_idxs.append(i)
                else:
                    break
            _log(f"Long touches 61.8: all={all_touch_idxs}, contiguous_first_block={touch_idxs}")
        else:
            _log("Long: no 61.8 touches yet.")
        if not all_touch_idxs and corr_low > fib_236:
            return None
        status = "valid_reversal"
        pattern = "none"
        pattern_idx = touch_idxs[-1] if touch_idxs else i_end
        detect_end = min(i_end, (touch_idxs[-1] + 2) if touch_idxs else i_end)
        # 1-candle: hammer touching 61.8 and closing above 61.8
        for i in touch_idxs[:1]:
            c = w.iloc[i]
            if _is_bullish_hammer(c) and _touches_level(c, fib_618) and float(c["Close"]) > fib_618:
                pattern = "hammer"
                pattern_idx = i
                break
        # 2-candle: bullish engulfing, at least one candle touches 61.8, second close > 61.8
        if pattern == "none" and touch_idxs:
            for i in range(max(i_peak + 1, touch_idxs[0]), detect_end + 1):
                c1, c2 = w.iloc[i - 1], w.iloc[i]
                engulf = (
                    float(c1["Close"]) < float(c1["Open"])
                    and float(c2["Close"]) > float(c2["Open"])
                    and float(c2["Open"]) < float(c1["Close"])
                    and min(float(c2["Open"]), float(c2["Close"])) <= min(float(c1["Open"]), float(c1["Close"]))
                    and max(float(c2["Open"]), float(c2["Close"])) >= max(float(c1["Open"]), float(c1["Close"]))
                )
                includes_first_touch = touch_idxs[0] in {i - 1, i}
                if engulf and includes_first_touch and (_touches_level(c1, fib_618) or _touches_level(c2, fib_618)) and float(c2["Close"]) > fib_618:
                    pattern = "bullish_engulfing"
                    pattern_idx = i
                    break
        if pattern == "none" and touch_idxs:
            for i in range(max(i_peak + 1, touch_idxs[0]), detect_end + 1):
                c1, c2 = w.iloc[i - 1], w.iloc[i]
                includes_first_touch = touch_idxs[0] in {i - 1, i}
                if includes_first_touch and _is_bullish_piercing_line(c1, c2, fib_618):
                    pattern = "bullish_piercing_line"
                    pattern_idx = i
                    break
        if pattern == "none" and touch_idxs:
            for i in range(max(i_peak + 1, touch_idxs[0]), detect_end + 1):
                includes_first_touch = touch_idxs[0] in {i - 1, i}
                if includes_first_touch and _is_bullish_harami(w.iloc[i - 1], w.iloc[i], fib_618):
                    pattern = "bullish_harami"
                    pattern_idx = i
                    break
        if pattern == "none" and touch_idxs:
            for i in range(max(i_peak + 2, touch_idxs[0] + 2), detect_end + 1):
                includes_first_touch = touch_idxs[0] in {i - 2, i - 1, i}
                if includes_first_touch and _is_morning_star(w.iloc[i - 2], w.iloc[i - 1], w.iloc[i], fib_618, doji_middle=False):
                    pattern = "morning_star"
                    pattern_idx = i
                    break
        if pattern == "none" and touch_idxs:
            for i in range(max(i_peak + 2, touch_idxs[0] + 2), detect_end + 1):
                includes_first_touch = touch_idxs[0] in {i - 2, i - 1, i}
                if includes_first_touch and _is_morning_star(w.iloc[i - 2], w.iloc[i - 1], w.iloc[i], fib_618, doji_middle=True):
                    pattern = "morning_doji_star"
                    pattern_idx = i
                    break
        crossed_618 = corr_low <= fib_618
        _log(f"Long pattern={pattern}, crossed_618={crossed_618}, corr_low={corr_low:.4f}, fib_618={fib_618:.4f}")
        if pattern == "none":
            if crossed_618:
                _log("Rejected long: 61.8 crossed but no valid pattern.")
                return None
            if float(close.iloc[-1]) > fib_236:
                _log("Rejected long: current close is above 23.6, so not waiting-for-61.8 anymore.")
                return None
            status = "reached_23_6_waiting_for_61_8" if not crossed_618 else "touched_61_8_no_pattern"
        stop_loss = float(low.iloc[pattern_idx])
        next5 = w.iloc[pattern_idx + 1:pattern_idx + 6]
        if not next5.empty and (next5["Close"] < stop_loss).any():
            status = "invalidated_by_stop_loss"
        decline_end_idx = all_touch_idxs[0] if all_touch_idxs else i_end
        decline_bars = decline_end_idx - i_peak
        if decline_bars < 2:
            _log(f"Rejected long: decline leg too short for scoring ({decline_bars} bars).")
            return None
        ratio = round((i_peak - i_start) / max(decline_end_idx - i_peak, 1), 2)
        if ratio > 8.0 and not early_correction_accepted:
            _log(f"Rejected long: incline/decline ratio too high ({ratio} > 8.0).")
            return None
        if ratio > 8.0 and early_correction_accepted:
            _log(
                f"Long: keeping setup despite high incline/decline ratio ({ratio}) "
                "because early correction mode is active."
            )
        return FiboScanResult(
            ticker="", direction=direction, status=status,
            incline_start_date=str(pd.to_datetime(w.iloc[i_start]["Date"]).date()),
            incline_end_date=str(pd.to_datetime(w.iloc[i_peak]["Date"]).date()),
            incline_duration_days=i_peak - i_start,
            decline_end_date=str(pd.to_datetime(w.iloc[decline_end_idx]["Date"]).date()),
            decline_duration_days=decline_end_idx - i_peak,
            incline_decline_duration_ratio=ratio,
            fib_23_6=fib_236,
            fib_38_2=fib_382,
            fib_61_8=fib_618,
            first_61_8_touch_date=(str(pd.to_datetime(w.iloc[all_touch_idxs[0]]["Date"]).date()) if all_touch_idxs else ""),
            reversal_pattern_name=pattern, stop_loss=stop_loss, current_close=float(close.iloc[-1])
        )
    # short setup
    i_start = int(close.iloc[:-60].idxmax())
    min_incline_days = 10
    i_bottom = int(low.iloc[i_start + min_incline_days:].idxmin())
    if i_bottom <= i_start + min_incline_days:
        _log("Rejected short: invalid impulse start/bottom distance.")
        return None
    i_end = len(w) - 1
    if i_end - i_bottom < 8:
        _log("Rejected short: correction leg too short (<8 bars).")
        return None
    fib_start = float(high.iloc[i_start])
    fib_end = float(low.iloc[i_bottom])
    rng = fib_start - fib_end
    if rng <= 0:
        _log("Rejected short: non-positive fib range.")
        return None
    fib_236 = fib_end + rng * 0.236
    fib_382 = fib_end + rng * 0.382
    fib_500 = fib_end + rng * 0.5
    fib_618 = fib_end + rng * 0.618
    corr_high = float(high.iloc[i_bottom:i_end + 1].max())
    if _has_long_sideways(w.iloc[i_bottom:i_end + 1], max_days=22, band_pct=0.12):
        _log("Rejected short: correction is sideways/flat.")
        return None
    if corr_high < fib_236:
        _log("Rejected short: correction never reached 23.6.")
        return None
    all_touch_idxs = [i for i in range(i_bottom, i_end + 1) if low.iloc[i] <= fib_618 <= high.iloc[i]]
    touch_idxs: list[int] = []
    if all_touch_idxs:
        first_touch = all_touch_idxs[0]
        for i in range(first_touch, min(first_touch + 3, i_end + 1)):
            if low.iloc[i] <= fib_618 <= high.iloc[i]:
                touch_idxs.append(i)
            else:
                break
        _log(f"Short touches 61.8: all={all_touch_idxs}, contiguous_first_block={touch_idxs}")
    else:
        _log("Short: no 61.8 touches yet.")
    if not all_touch_idxs and corr_high < fib_236:
        return None
    status = "valid_reversal"
    pattern = "none"
    pattern_idx = touch_idxs[-1] if touch_idxs else i_end
    detect_end = min(i_end, (touch_idxs[-1] + 2) if touch_idxs else i_end)
    for i in touch_idxs:
        c = w.iloc[i]
        if _is_bearish_shooting_star(c) and _touches_level(c, fib_618) and float(c["Close"]) < fib_618:
            pattern = "shooting_star"
            pattern_idx = i
            break
    if pattern == "none" and touch_idxs:
        for i in range(max(i_bottom + 1, touch_idxs[0]), detect_end + 1):
            c1, c2 = w.iloc[i - 1], w.iloc[i]
            engulf = (
                float(c1["Close"]) > float(c1["Open"])
                and float(c2["Close"]) < float(c2["Open"])
                and float(c2["Open"]) > float(c1["Close"])
                and min(float(c2["Open"]), float(c2["Close"])) <= min(float(c1["Open"]), float(c1["Close"]))
                and max(float(c2["Open"]), float(c2["Close"])) >= max(float(c1["Open"]), float(c1["Close"]))
            )
            includes_first_touch = touch_idxs[0] in {i - 1, i}
            if engulf and includes_first_touch and (_touches_level(c1, fib_618) or _touches_level(c2, fib_618)) and float(c2["Close"]) < fib_618:
                pattern = "bearish_engulfing"
                pattern_idx = i
                break
    if pattern == "none" and touch_idxs:
        for i in range(max(i_bottom + 1, touch_idxs[0]), detect_end + 1):
            includes_first_touch = touch_idxs[0] in {i - 1, i}
            if includes_first_touch and _is_bearish_harami(w.iloc[i - 1], w.iloc[i], fib_618):
                pattern = "bearish_harami"
                pattern_idx = i
                break
    if pattern == "none" and touch_idxs:
        for i in range(max(i_bottom + 1, touch_idxs[0]), detect_end + 1):
            includes_first_touch = touch_idxs[0] in {i - 1, i}
            if includes_first_touch and _is_dark_cloud_cover(w.iloc[i - 1], w.iloc[i], fib_618):
                pattern = "dark_cloud_cover"
                pattern_idx = i
                break
    if pattern == "none" and touch_idxs:
        for i in range(max(i_bottom + 2, touch_idxs[0] + 2), detect_end + 1):
            includes_first_touch = touch_idxs[0] in {i - 2, i - 1, i}
            if includes_first_touch and _is_evening_star(w.iloc[i - 2], w.iloc[i - 1], w.iloc[i], fib_618, doji_middle=False):
                pattern = "evening_star"
                pattern_idx = i
                break
    if pattern == "none" and touch_idxs:
        for i in range(max(i_bottom + 2, touch_idxs[0] + 2), detect_end + 1):
            includes_first_touch = touch_idxs[0] in {i - 2, i - 1, i}
            if includes_first_touch and _is_evening_star(w.iloc[i - 2], w.iloc[i - 1], w.iloc[i], fib_618, doji_middle=True):
                pattern = "evening_doji_star"
                pattern_idx = i
                break
    crossed_618 = corr_high >= fib_618
    _log(f"Short pattern={pattern}, crossed_618={crossed_618}, corr_high={corr_high:.4f}, fib_618={fib_618:.4f}")
    if pattern == "none":
        if crossed_618:
            _log("Rejected short: 61.8 crossed but no valid pattern.")
            return None
        if float(close.iloc[-1]) < fib_236:
            _log("Rejected short: current close is below 23.6, so not waiting-for-61.8 anymore.")
            return None
        status = "reached_23_6_waiting_for_61_8" if not crossed_618 else "touched_61_8_no_pattern"
    stop_loss = float(high.iloc[pattern_idx])
    next5 = w.iloc[pattern_idx + 1:pattern_idx + 6]
    if not next5.empty and (next5["Close"] > stop_loss).any():
        status = "invalidated_by_stop_loss"
    decline_end_idx = all_touch_idxs[0] if all_touch_idxs else i_end
    if (decline_end_idx - i_bottom) < 2:
        return None
    ratio = round((i_bottom - i_start) / max(decline_end_idx - i_bottom, 1), 2)
    if ratio > 8.0:
        return None
    return FiboScanResult(
        ticker="", direction=direction, status=status,
        incline_start_date=str(pd.to_datetime(w.iloc[i_start]["Date"]).date()),
        incline_end_date=str(pd.to_datetime(w.iloc[i_bottom]["Date"]).date()),
        incline_duration_days=i_bottom - i_start,
        decline_end_date=str(pd.to_datetime(w.iloc[decline_end_idx]["Date"]).date()),
        decline_duration_days=decline_end_idx - i_bottom,
        incline_decline_duration_ratio=ratio,
        fib_23_6=fib_236,
        fib_38_2=fib_382,
        fib_61_8=fib_618,
        first_61_8_touch_date=(str(pd.to_datetime(w.iloc[all_touch_idxs[0]]["Date"]).date()) if all_touch_idxs else ""),
        reversal_pattern_name=pattern, stop_loss=stop_loss, current_close=float(close.iloc[-1])
    )


def _print_fibo_results(
    rows1: list[FiboScanResult],
    rows2: list[FiboScanResult],
    avg_turnover_10d_by_key: dict[tuple[str, str, str, str], float] | None = None,
) -> list[str]:
    print(f"\n{ANSI_BOLD}{ANSI_GREEN}WYNIKI FIBO #1 (current 23.6..61.8 OR 61.8+valid formation):{ANSI_RESET}")
    if not rows1:
        print("Brak wyników.")
        links = []
    else:
        print(f"{'Ticker':<10} {'Dir':<6} {'Status':<30} {'Pattern':<22} {'Incline':<23} {'Ratio(d)':>16} {'Touched_61.8_date':<16} {'Avg10Turn':>12} {'Near61.8':>10} {'Link':<0}")
        print("-" * 185)
        links = []
    top3_avg_keys: set[tuple[str, str, str, str]] = set()
    if avg_turnover_10d_by_key:
        top3 = sorted(avg_turnover_10d_by_key.items(), key=lambda kv: kv[1], reverse=True)[:3]
        top3_avg_keys = {k for k, _ in top3}
    for r in rows1:
        color = ANSI_GREEN if r.status == "valid_reversal" else ANSI_YELLOW if r.status == "touched_61_8_no_pattern" else "\033[31m"
        link = _stooq_chart_url(r.ticker)
        links.append(link)
        incline = f"{r.incline_start_date}->{r.incline_end_date}"
        ratio_txt = f"{r.incline_duration_days}/{max(r.decline_duration_days,1)} ({r.incline_decline_duration_ratio:.2f}:1)"
        avg_turn = "-"
        row_key = (r.ticker, r.direction, r.incline_start_date, r.incline_end_date)
        if avg_turnover_10d_by_key is not None:
            if row_key in avg_turnover_10d_by_key:
                avg_turn = f"{avg_turnover_10d_by_key[row_key]:,.0f}"
        avg_col = "\033[38;5;220m" if row_key in top3_avg_keys else ANSI_RESET
        near_txt = "-"
        near_col = ANSI_YELLOW
        try:
            dist = abs(float(r.current_close) - float(r.fib_61_8))
            band = max(abs(float(r.fib_23_6) - float(r.fib_61_8)), 1e-9)
            closeness = max(0.0, 1.0 - (dist / band))
            near_txt = f"{closeness*100:5.1f}%"
            near_col = ANSI_GREEN if closeness >= 0.7 else (ANSI_YELLOW if closeness >= 0.35 else "\033[31m")
        except Exception:
            pass
        print(f"{ANSI_CYAN}{r.ticker:<10}{ANSI_RESET} {r.direction:<6} {color}{r.status:<30}{ANSI_RESET} {r.reversal_pattern_name:<22} {incline:<23} {ratio_txt:>16} {(r.first_61_8_touch_date or '-'): <16} {avg_col}{avg_turn:>12}{ANSI_RESET} {near_col}{near_txt:>10}{ANSI_RESET} {ANSI_CYAN}{link}{ANSI_RESET}")
    print(f"\n{ANSI_BOLD}{ANSI_YELLOW}WYNIKI FIBO #2 (valid formation, last 2 months):{ANSI_RESET}")
    if not rows2:
        print("Brak wyników.")
        return links
    print(f"{'Ticker':<10} {'Dir':<6} {'Pattern':<22} {'Incline':<23} {'Ratio(d)':>16} {'Touched_61.8_date':<16} {'Close':>10} {'Link':<0}")
    print("-" * 140)
    for r in rows2:
        link = _stooq_chart_url(r.ticker)
        if link not in links:
            links.append(link)
        incline = f"{r.incline_start_date}->{r.incline_end_date}"
        ratio_txt = f"{r.incline_duration_days}/{max(r.decline_duration_days,1)} ({r.incline_decline_duration_ratio:.2f}:1)"
        print(f"{ANSI_CYAN}{r.ticker:<10}{ANSI_RESET} {r.direction:<6} {ANSI_GREEN}{r.reversal_pattern_name:<22}{ANSI_RESET} {incline:<23} {ratio_txt:>16} {(r.first_61_8_touch_date or '-'): <16} {r.current_close:>10.4f} {ANSI_CYAN}{link}{ANSI_RESET}")
    return links


def run_fibo_search(target: str) -> int:
    group_name, members, source, exchange_suffix = _get_members(target)
    print(f"[fibo] grupa={group_name}, liczba instrumentów={len(members)}, źródło={source}")
    rows: list[FiboScanResult] = []
    def _is_waiting_candidate_stale(df_full: pd.DataFrame, cand: FiboScanResult) -> bool:
        if cand.status != "reached_23_6_waiting_for_61_8" or not cand.incline_end_date:
            return False
        dts = pd.to_datetime(df_full["Date"], errors="coerce")
        try:
            end_ts = pd.to_datetime(cand.incline_end_date)
        except Exception:
            return False
        after = df_full.loc[dts > end_ts]
        if after.empty:
            return False
        if cand.direction == "long":
            # Long waiting setup becomes stale if market already made a higher high
            # after the selected impulse top (newer impulse supersedes older one),
            # or if price already reached the setup's 61.8 retracement.
            end_rows = df_full.loc[dts == end_ts]
            end_high = pd.to_numeric(end_rows["High"], errors="coerce").max() if not end_rows.empty else float("nan")
            after_high = pd.to_numeric(after["High"], errors="coerce")
            made_higher_high = pd.notna(end_high) and bool((after_high > float(end_high)).any())
            if made_higher_high:
                return True
            after_low = pd.to_numeric(after["Low"], errors="coerce")
            return bool((after_low <= float(cand.fib_61_8)).any())
        # Symmetric stale condition for short waiting setups.
        end_rows = df_full.loc[dts == end_ts]
        end_low = pd.to_numeric(end_rows["Low"], errors="coerce").min() if not end_rows.empty else float("nan")
        after_low = pd.to_numeric(after["Low"], errors="coerce")
        made_lower_low = pd.notna(end_low) and bool((after_low < float(end_low)).any())
        if made_lower_low:
            return True
        after_high = pd.to_numeric(after["High"], errors="coerce")
        return bool((after_high >= float(cand.fib_61_8)).any())

    def _scan_fibo_one(idx_ticker: tuple[int, str]) -> tuple[int, str, list[FiboScanResult], str | None]:
        idx, ticker = idx_ticker
        instrument = "stock"
        if group_name == "forex":
            instrument = "forex"
        elif group_name in {"commodities", "indexes"}:
            instrument = "commodity"
        elif group_name == "single":
            detected = detect_instrument_type(ticker, None)
            instrument = "commodity" if detected == "commodity" else ("forex" if detected == "forex" else "stock")
        fetch_symbol = ticker if instrument != "stock" or not exchange_suffix else f"{ticker}{exchange_suffix}"
        if instrument == "stock" and "." not in fetch_symbol and len(fetch_symbol) <= 5:
            fetch_symbol = f"{fetch_symbol}.WA"
        if instrument == "commodity":
            fetch_symbol = COMMODITY_STOOQ_MAP.get(ticker.upper(), fetch_symbol).upper()
        out_rows: list[FiboScanResult] = []
        try:
            df, _, _ = load_or_update_daily_data(symbol=fetch_symbol, instrument_type=instrument, persist=True)
            # Try multiple end offsets so older (but still recent) valid formations are not missed.
            long_candidates: list[FiboScanResult] = []
            long_offset0 = _find_fibo_setup(df, "long", end_offset=0)
            for off in [0, 5, 10, 15, 20, 30, 40]:
                cand = _find_fibo_setup(df, "long", end_offset=off)
                if cand:
                    long_candidates.append(cand)
            if long_candidates:
                # If current window (offset 0) no longer qualifies as "waiting",
                # drop stale waiting candidates coming from older offsets.
                if long_offset0 is None or long_offset0.status != "reached_23_6_waiting_for_61_8":
                    long_candidates = [c for c in long_candidates if c.status != "reached_23_6_waiting_for_61_8"]
                long_candidates = [c for c in long_candidates if not _is_waiting_candidate_stale(df, c)]
                # If multiple candidates end on the same impulse top, keep only the broadest leg
                # (earliest start). This removes nested mini-impulses like 2026-04-16->2026-05-11
                # when the proper formation is 2026-04-07->2026-05-11.
                by_end: dict[str, FiboScanResult] = {}
                for c in long_candidates:
                    prev = by_end.get(c.incline_end_date)
                    if prev is None or c.incline_start_date < prev.incline_start_date:
                        by_end[c.incline_end_date] = c
                long_candidates = list(by_end.values())
                # Keep at most two distinct formations (e.g. bigger + recent smaller).
                long_candidates = sorted(
                    long_candidates,
                    key=lambda r: (r.status == "valid_reversal", r.incline_end_date, r.first_61_8_touch_date),
                    reverse=True,
                )
                seen_long: set[tuple[str, str]] = set()
                seen_long_start: set[str] = set()
                picked_long: list[FiboScanResult] = []
                for c in long_candidates:
                    k = (c.incline_start_date, c.incline_end_date)
                    if k in seen_long or c.incline_start_date in seen_long_start:
                        continue
                    seen_long.add(k)
                    seen_long_start.add(c.incline_start_date)
                    picked_long.append(c)
                    if len(picked_long) >= 2:
                        break
                for c in picked_long:
                    c.ticker = ticker
                    out_rows.append(c)
            if instrument in {"commodity", "forex"}:
                short_candidates: list[FiboScanResult] = []
                short_offset0 = _find_fibo_setup(df, "short", end_offset=0)
                for off in [0, 5, 10, 15, 20, 30, 40]:
                    cand = _find_fibo_setup(df, "short", end_offset=off)
                    if cand:
                        short_candidates.append(cand)
                if short_candidates:
                    if short_offset0 is None or short_offset0.status != "reached_23_6_waiting_for_61_8":
                        short_candidates = [c for c in short_candidates if c.status != "reached_23_6_waiting_for_61_8"]
                    short_candidates = [c for c in short_candidates if not _is_waiting_candidate_stale(df, c)]
                    short_candidates = sorted(
                        short_candidates,
                        key=lambda r: (r.status == "valid_reversal", r.incline_end_date, r.first_61_8_touch_date),
                        reverse=True,
                    )
                    seen_short: set[tuple[str, str]] = set()
                    seen_short_start: set[str] = set()
                    picked_short: list[FiboScanResult] = []
                    for c in short_candidates:
                        k = (c.incline_start_date, c.incline_end_date)
                        if k in seen_short or c.incline_start_date in seen_short_start:
                            continue
                        seen_short.add(k)
                        seen_short_start.add(c.incline_start_date)
                        picked_short.append(c)
                        if len(picked_short) >= 2:
                            break
                    for c in picked_short:
                        c.ticker = ticker
                        out_rows.append(c)
            return idx, ticker, out_rows, None
        except Exception as exc:
            return idx, ticker, [], _compact_error(str(exc))

    cpu = os.cpu_count() or 4
    auto_workers = max(4, min(cpu * 3, 32))
    max_workers = min(auto_workers, len(members))
    print(f"[fibo] parallel mode ({max_workers} workers, xdist-style).")
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_map = {ex.submit(_scan_fibo_one, (idx, ticker)): (idx, ticker) for idx, ticker in enumerate(members, start=1)}
        for fut in as_completed(fut_map):
            idx, ticker = fut_map[fut]
            _, _, found, err = fut.result()
            print(f"[{idx}/{len(members)}] fibo {ticker}...")
            if err:
                print(f"  pominięto ({err})")
            rows.extend(found)
    SEARCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = SEARCH_OUTPUT_DIR / f"fibo_search_{group_name.lower()}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([f.name for f in FiboScanResult.__dataclass_fields__.values()])
        for row in rows:
            w.writerow([getattr(row, f) for f in FiboScanResult.__dataclass_fields__.keys()])
    two_months_ago = pd.Timestamp(datetime.now(UTC).date()) - pd.Timedelta(days=62)
    rows2 = [
        r for r in rows
        if r.status == "valid_reversal"
        and r.reversal_pattern_name != "none"
        and pd.Timestamp(r.first_61_8_touch_date) >= two_months_ago
    ]
    rows1 = []
    for r in rows:
        if (
            r.status == "valid_reversal"
            and r.reversal_pattern_name != "none"
            and pd.Timestamp(r.first_61_8_touch_date) >= two_months_ago
        ):
            rows1.append(r)
            continue
        if r.status == "touched_61_8_no_pattern":
            continue
        if r.direction == "long" and r.status == "reached_23_6_waiting_for_61_8" and r.fib_61_8 <= r.current_close <= r.fib_23_6:
            rows1.append(r)
            continue
        if r.direction == "short" and r.status == "reached_23_6_waiting_for_61_8" and r.fib_23_6 <= r.current_close <= r.fib_61_8:
            rows1.append(r)
            continue
    avg_turnover_10d_by_key: dict[tuple[str, str, str, str], float] = {}

    def _passes_fibo_liquidity(r: FiboScanResult) -> bool:
        row = rows_by_key.get((r.ticker, r.direction, r.incline_start_date, r.incline_end_date))
        if row is None:
            return False
        symbol = row[0]
        try:
            df_l, _, _ = load_or_update_daily_data(symbol=symbol, instrument_type=row[1], persist=True)
        except Exception:
            return False
        if "Close" not in df_l.columns or "Volume" not in df_l.columns or len(df_l) < 10:
            return False
        turnover_native = pd.to_numeric(df_l["Close"], errors="coerce") * pd.to_numeric(df_l["Volume"], errors="coerce")
        turnover_native = turnover_native.dropna()
        if len(turnover_native) < 10:
            return False
        try:
            cc = _country_code_from_ticker(symbol)
            country_to_currency = {"PL": "PLN", "US": "USD", "DE": "EUR", "FR": "EUR", "CN": "CNY"}
            currency = country_to_currency.get(cc, "USD")
            _, fx_to_pln = get_fx_to_pln_rate_yahoo(currency)
            fx_to_pln = float(fx_to_pln) if fx_to_pln and fx_to_pln > 0 else 1.0
        except Exception:
            fx_to_pln = 1.0
        avg_10d_pln = float((turnover_native.tail(10) * fx_to_pln).mean())
        avg_turnover_10d_by_key[(r.ticker, r.direction, r.incline_start_date, r.incline_end_date)] = avg_10d_pln
        min_avg = 500000.0 * _gdp_multiplier_for_ticker(symbol)
        return avg_10d_pln >= min_avg

    rows_by_key: dict[tuple[str, str, str, str], tuple[str, str]] = {}
    # Build lookup using the same symbol normalization as scanner.
    for ticker in members:
        instrument = "stock"
        if group_name == "forex":
            instrument = "forex"
        elif group_name in {"commodities", "indexes"}:
            instrument = "commodity"
        elif group_name == "single":
            detected = detect_instrument_type(ticker, None)
            instrument = "commodity" if detected == "commodity" else ("forex" if detected == "forex" else "stock")
        fetch_symbol = ticker if instrument != "stock" or not exchange_suffix else f"{ticker}{exchange_suffix}"
        if instrument == "stock" and "." not in fetch_symbol and len(fetch_symbol) <= 5:
            fetch_symbol = f"{fetch_symbol}.WA"
        if instrument == "commodity":
            fetch_symbol = COMMODITY_STOOQ_MAP.get(ticker.upper(), fetch_symbol).upper()
        for r in rows:
            if r.ticker == ticker:
                rows_by_key[(r.ticker, r.direction, r.incline_start_date, r.incline_end_date)] = (fetch_symbol, instrument)

    # Populate Avg10Turn display metric also for non-valid rows shown in WYNIKI #1.
    for r in rows1:
        k = (r.ticker, r.direction, r.incline_start_date, r.incline_end_date)
        if k in avg_turnover_10d_by_key:
            continue
        row = rows_by_key.get(k)
        if row is None:
            continue
        symbol, instrument_type = row
        try:
            df_l, _, _ = load_or_update_daily_data(symbol=symbol, instrument_type=instrument_type, persist=True)
            turnover_native = pd.to_numeric(df_l["Close"], errors="coerce") * pd.to_numeric(df_l["Volume"], errors="coerce")
            turnover_native = turnover_native.dropna()
            if len(turnover_native) < 10:
                continue
            cc = _country_code_from_ticker(symbol)
            country_to_currency = {"PL": "PLN", "US": "USD", "DE": "EUR", "FR": "EUR", "CN": "CNY"}
            currency = country_to_currency.get(cc, "USD")
            _, fx_to_pln = get_fx_to_pln_rate_yahoo(currency)
            fx_to_pln = float(fx_to_pln) if fx_to_pln and fx_to_pln > 0 else 1.0
            avg_turnover_10d_by_key[k] = float((turnover_native.tail(10) * fx_to_pln).mean())
        except Exception:
            continue

    rows1 = [r for r in rows1 if _passes_fibo_liquidity(r)]
    rows2 = [r for r in rows2 if _passes_fibo_liquidity(r)]
    rows1 = sorted(
        rows1,
        key=lambda r: (
            r.status != "valid_reversal",
            abs(float(r.current_close) - float(r.fib_61_8)),
            r.ticker,
            r.direction,
            r.incline_start_date,
            r.first_61_8_touch_date,
        ),
        reverse=False,
    )
    rows2 = sorted(
        rows2,
        key=lambda r: (r.ticker, r.direction, r.incline_start_date, r.first_61_8_touch_date),
        reverse=False,
    )
    rows2_keys = {(r.ticker, r.direction) for r in rows2}
    rows1 = [r for r in rows1 if (r.ticker, r.direction) not in rows2_keys]
    links = _print_fibo_results(rows1, rows2, avg_turnover_10d_by_key=avg_turnover_10d_by_key)
    print(f"\n[fibo] znaleziono: {len(rows)}")
    print(f"[fibo] csv: {out_csv}")
    if links:
        try:
            open_all = input("Czy otworzyć wszystkie linki? [y/N]: ").strip().lower()
        except EOFError:
            open_all = "n"
        if open_all == "y":
            for link in links:
                webbrowser.open_new_tab(link)
    return 0


def run_fibo_explain(scope: str, symbol: str) -> int:
    group_name, _, _, exchange_suffix = _get_members(scope)
    ticker = symbol.strip().upper()
    instrument = "stock"
    if group_name == "forex":
        instrument = "forex"
    elif group_name in {"commodities", "indexes"}:
        instrument = "commodity"
    elif group_name == "single":
        detected = detect_instrument_type(ticker, None)
        instrument = "commodity" if detected == "commodity" else ("forex" if detected == "forex" else "stock")
    fetch_symbol = ticker if instrument != "stock" or not exchange_suffix else f"{ticker}{exchange_suffix}"
    if instrument == "stock" and "." not in fetch_symbol and len(fetch_symbol) <= 5:
        fetch_symbol = f"{fetch_symbol}.WA"
    if instrument == "commodity":
        fetch_symbol = COMMODITY_STOOQ_MAP.get(ticker.upper(), fetch_symbol).upper()
    print(f"[fibo-explain] ticker={ticker}, fetch_symbol={fetch_symbol}, instrument={instrument}")
    df, _, _ = load_or_update_daily_data(symbol=fetch_symbol, instrument_type=instrument, persist=True)
    for direction in (["long", "short"] if instrument in {"commodity", "forex"} else ["long"]):
        print(f"\n=== Direction: {direction} ===")
        for off in [0, 5, 10, 15, 20, 30, 40]:
            steps: list[str] = []
            res = _find_fibo_setup(df, direction, end_offset=off, explain=steps)
            print(f"- offset={off}: {'MATCH' if res else 'NO MATCH'}")
            if res:
                print(f"  status={res.status}, pattern={res.reversal_pattern_name}, touch_date={res.first_61_8_touch_date}, close={res.current_close:.4f}")
            for s in steps:
                print(f"    • {s}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skaner ichimoku cloud search")
    parser.add_argument("target", help="Nazwa indeksu albo: commodities / forex")
    args = parser.parse_args()
    return run_ichimoku_search(args.target)


if __name__ == "__main__":
    raise SystemExit(main())
ANSI_BOLD = "\033[1m"
ANSI_GREEN = "\033[32m"
ANSI_CYAN = "\033[36m"
ANSI_YELLOW = "\033[33m"
ANSI_RESET = "\033[0m"
