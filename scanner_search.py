from __future__ import annotations

import argparse
import json
import os
import random
import re
import webbrowser
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as dt_time, timedelta
import math
from importlib import util
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd

from chart_program.instrument_detector import detect_instrument_type
from chart_program.chart_loader import (
    CSV_DATA_DIR,
    STATE_DATA_DIR,
    COMMODITY_STOOQ_MAP,
    COMMODITY_YAHOO_MAP,
    load_or_update_daily_data,
    has_new_remote_data,
    local_csv_path_for_symbol,
    _yahoo_download,
    _yahoo_download_window,
)
from utilities.yahoo_finance import get_fx_to_pln_rate_yahoo
from utilities.output_silence import call_silenced

PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_MEMBERS_FILE = STATE_DATA_DIR / "indices" / "memberships.json"
SEARCH_OUTPUT_DIR = PROJECT_ROOT / "chart_program" / "data" / "search"
ICHIMOKU_SEARCH_OUTPUT_DIR = SEARCH_OUTPUT_DIR / "ichimoku"
FIBO_SEARCH_OUTPUT_DIR = SEARCH_OUTPUT_DIR / "fibo"

STOP_SCAN_EVENT = threading.Event()
PAUSE_SCAN_EVENT = threading.Event()
PROMPT_LOCK = threading.Lock()
REFRESH_STATE_FILE = STATE_DATA_DIR / "sessions" / "search_refresh_state.json"
API_METAL_COMMODITIES: set[str] = set()


@dataclass(frozen=True)
class MarketDataRule:
    rule_name: str
    timezone: str
    availability_time: dt_time
    trading_weekdays: tuple[int, ...]
    weekend_fallback_weekday: int = 4
    holidays: frozenset[date] = frozenset()


MARKET_DATA_RULES: dict[str, MarketDataRule] = {
    "stock_market_pl": MarketDataRule("stock_market_pl", "Europe/Warsaw", dt_time(17, 30), (0, 1, 2, 3, 4)),
    "stock_market_de": MarketDataRule("stock_market_de", "Europe/Berlin", dt_time(18, 30), (0, 1, 2, 3, 4)),
    "stock_market_us": MarketDataRule("stock_market_us", "America/New_York", dt_time(18, 0), (0, 1, 2, 3, 4)),
    "stock_market_generic": MarketDataRule("stock_market_generic", "UTC", dt_time(22, 0), (0, 1, 2, 3, 4)),
    # Commodity data is intentionally separate from stock-market rules.  Many
    # contracts trade across Sunday-Friday sessions, but daily scanner data is
    # provider-settlement based, so use a conservative post-settlement UTC gate.
    "commodity_market": MarketDataRule("commodity_market", "UTC", dt_time(1, 0), (0, 1, 2, 3, 4)),
    "forex_market": MarketDataRule("forex_market", "UTC", dt_time(1, 0), (0, 1, 2, 3, 4)),
}

GROUP_MARKET_DATA_RULES: dict[str, str] = {
    "WIG": "stock_market_pl",
    "WIG_PART1": "stock_market_pl",
    "WIG_PART2": "stock_market_pl",
    "WIG_PART3": "stock_market_pl",
    "WIG20": "stock_market_pl",
    "DAX": "stock_market_de",
    "DAX40": "stock_market_de",
    "NDX100": "stock_market_us",
    "US": "stock_market_us",
    "US100": "stock_market_us",
    "COMMODITIES": "commodity_market",
    "FOREX": "forex_market",
    "INDEXES": "commodity_market",
}


def _market_rule_name_for_instrument(instrument: str, group: str, symbol: str | None = None) -> str:
    group_key = (group or "").strip().upper()
    if group_key in GROUP_MARKET_DATA_RULES:
        return GROUP_MARKET_DATA_RULES[group_key]
    if instrument == "commodity":
        return "commodity_market"
    if instrument == "forex":
        return "forex_market"
    suffix = (symbol or "").strip().upper().rsplit(".", 1)[-1] if "." in (symbol or "") else ""
    if suffix == "WA":
        return "stock_market_pl"
    if suffix == "DE":
        return "stock_market_de"
    if suffix == "US":
        return "stock_market_us"
    return "stock_market_generic"


def _previous_session_day(day: date, rule: MarketDataRule) -> date:
    candidate = day
    for _ in range(14):
        if candidate.weekday() in rule.trading_weekdays and candidate not in rule.holidays:
            return candidate
        candidate -= timedelta(days=1)
    return candidate


def get_expected_latest_session_date(instrument: str, group: str, current_datetime: datetime, symbol: str | None = None) -> date:
    """Return the newest provider-expected closed daily session for a scanner row.

    The rule is market/group based so grouped reports use one consistent
    expectation per market, while commodities and forex remain on their own
    extensible calendar branches.
    """
    if current_datetime.tzinfo is None:
        current_datetime = current_datetime.replace(tzinfo=UTC)
    rule = MARKET_DATA_RULES[_market_rule_name_for_instrument(instrument, group, symbol)]
    local_now = current_datetime.astimezone(ZoneInfo(rule.timezone))
    candidate = _previous_session_day(local_now.date(), rule)
    if candidate == local_now.date() and local_now.time() < rule.availability_time:
        candidate = _previous_session_day(candidate - timedelta(days=1), rule)
    return candidate


def has_latest_expected_data(latest_candle_date: date | None, expected_latest_session_date: date | None) -> bool:
    if latest_candle_date is None or expected_latest_session_date is None:
        return False
    return latest_candle_date >= expected_latest_session_date


def _latest_candle_date_from_df(df: pd.DataFrame) -> date | None:
    if df is None or df.empty or "Date" not in df.columns:
        return None
    dates = pd.to_datetime(df["Date"], errors="coerce").dropna()
    if dates.empty:
        return None
    return dates.max().date()


def _latest_data_marker(latest_candle_date: date | None, expected_latest_session_date: date | None) -> str:
    return "✅" if has_latest_expected_data(latest_candle_date, expected_latest_session_date) else "❌"


def _fmt_optional_date(value: date | None) -> str:
    return value.isoformat() if value else "-"



def _search_output_dir(prefix: str) -> Path:
    return FIBO_SEARCH_OUTPUT_DIR if prefix.startswith("fibo") else ICHIMOKU_SEARCH_OUTPUT_DIR

COMMODITIES_SEARCH_TICKERS = [
    "COFFEE", "COCOA", "SUGAR", "WHEAT", "CORN", "SOYBEAN", "SOYOIL",
    "COPPER", "ALUMINIUM", "PLATINUM", "PALLADIUM", "WTI",
    "OIL", "NATURAL_GAS", "GOLD", "SILVER",
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
    "MRB","MSP","MSW","MSZ","NEU","3RG","NTT","NVA","ODL","OTM","PAT","PCE","PCO","PHN","PJP","PLZ","FHB","PRM","PPS",
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
    retest_count: int | None = None
    latest_retest_date: str | None = None
    latest_retest_pattern: str | None = None
    ichimoku_status: str | None = None
    latest_candle_date: date | None = None
    expected_latest_session_date: date | None = None
    ichimoku_risk: str | None = None
    tk_cross: str | None = None
    breakout_dynamic: str | None = None
    cloud_thickness: str | None = None
    chikou_confirmation: str | None = None
    kumo_twist: str | None = None
    tk_plus: str | None = None
    tenkan_in_cloud: str | None = None


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
    first_valid_retest_pattern_date: str = "-"
    retest_events: list[tuple[str, str, str]] | None = None  # (date, formation, depth)
    avg_turnover_10d_pln: float | None = None
    ichimoku_status: str | None = None
    latest_candle_date: date | None = None
    expected_latest_session_date: date | None = None
    ichimoku_risk: str | None = None
    tk_cross: str | None = None
    breakout_dynamic: str | None = None
    cloud_thickness: str | None = None
    chikou_confirmation: str | None = None
    kumo_twist: str | None = None
    tk_plus: str | None = None
    tenkan_in_cloud: str | None = None
    previous_respect_months: float | None = None




@dataclass
class WedgeScanResult:
    ticker: str
    start_date: str
    end_date: str
    duration_days: int
    upper_start_date: str
    upper_start_price: float
    upper_end_date: str
    upper_end_price: float
    lower_start_date: str
    lower_start_price: float
    lower_end_date: str
    lower_end_price: float
    upper_touches: int
    lower_touches: int
    width_start_pct: float
    width_end_pct: float
    slope_pct_per_day: float
    slope_strength: str
    fit_quality: float
    recent_proximity_pct: float
    compression_pct: float
    score: float
    current_close: float
    breakout_date: str = "-"
    breakout_direction: str = "-"
    avg_turnover_10d_pln: float | None = None
    latest_candle_date: date | None = None
    expected_latest_session_date: date | None = None

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
    latest_candle_date: date | None = None
    expected_latest_session_date: date | None = None



def _fibo_retracement_progress_pct(result: FiboScanResult) -> float:
    """Return pullback progress from 23.6 to 61.8; crossing 61.8 can exceed 100%."""
    try:
        band = max(abs(float(result.fib_23_6) - float(result.fib_61_8)), 1e-9)
        if str(result.direction).lower() == "short":
            return ((float(result.current_close) - float(result.fib_23_6)) / band) * 100.0
        return ((float(result.fib_23_6) - float(result.current_close)) / band) * 100.0
    except Exception:
        return -1.0


def _format_fibo_progress_pct(result: FiboScanResult) -> str:
    pct = _fibo_retracement_progress_pct(result)
    return f"{pct:5.1f}%" if pct >= 0 else "-"

def _fibo_formation_size(result: FiboScanResult) -> float:
    """Approximate absolute fib range from the 23.6 line and stop anchor."""
    try:
        anchor = float(result.stop_loss)
        fib_end = (float(result.fib_23_6) - 0.236 * anchor) / 0.764
        return abs(fib_end - anchor)
    except Exception:
        return 0.0


def _fibo_formation_strength(result: FiboScanResult) -> float:
    """Average daily impulse gain; used to choose between close-bottom duplicates."""
    try:
        return _fibo_formation_size(result) / max(abs(float(result.stop_loss)), 1e-9) / max(int(result.incline_duration_days), 1)
    except Exception:
        return 0.0


def _fibo_has_minimum_small_impulse(result: FiboScanResult) -> bool:
    """Reject tiny nested Fibo candidates unless time or price expansion is meaningful."""
    try:
        if int(result.incline_duration_days) >= 10:  # about two trading weeks
            return True
        size = _fibo_formation_size(result)
        anchor = max(abs(float(result.stop_loss)), 1e-9)
        return (size / anchor) >= 0.30
    except Exception:
        return False


def _same_scale_fibo_formation(a: FiboScanResult, b: FiboScanResult) -> bool:
    if str(a.ticker).upper() != str(b.ticker).upper() or str(a.direction).lower() != str(b.direction).lower():
        return False
    size_a = _fibo_formation_size(a)
    size_b = _fibo_formation_size(b)
    if size_a <= 0 or size_b <= 0:
        return False
    size_similarity = min(size_a, size_b) / max(size_a, size_b)
    anchor_gap = abs(float(a.stop_loss) - float(b.stop_loss)) / max(abs(float(a.stop_loss)), abs(float(b.stop_loss)), 1e-9)
    # Nested formations are useful only when they are materially different. If
    # bottoms are close, require a clearly larger fib range before keeping both;
    # otherwise choose the stronger following impulse from those nearby bottoms.
    if anchor_gap <= 0.08:
        return size_similarity >= 0.62
    return size_similarity >= 0.78




def _limit_fibo_formations_per_ticker(items: list[FiboScanResult], max_per_ticker: int = 2) -> list[FiboScanResult]:
    """Keep at most two Fibo formations per ticker across both directions."""
    grouped: dict[str, list[FiboScanResult]] = {}
    for item in items:
        if not _fibo_has_minimum_small_impulse(item):
            continue
        grouped.setdefault(str(item.ticker).upper(), []).append(item)
    limited: list[FiboScanResult] = []
    for group in grouped.values():
        if len(group) <= max_per_ticker:
            limited.extend(group)
            continue
        ordered = sorted(
            group,
            key=lambda r: (int(r.incline_duration_days), _fibo_formation_size(r), str(r.incline_start_date)),
        )
        keep = [ordered[0], ordered[-1]] if max_per_ticker >= 2 else [ordered[-1]]
        keep_ids = {id(x) for x in keep[:max_per_ticker]}
        limited.extend([item for item in group if id(item) in keep_ids])
    return limited

def _dedupe_same_scale_fibo_formations(items: list[FiboScanResult]) -> list[FiboScanResult]:
    picked: list[FiboScanResult] = []

    def prefer(candidate: FiboScanResult, current: FiboScanResult) -> bool:
        candidate_steep = str(candidate.status).startswith("3p_steep")
        current_steep = str(current.status).startswith("3p_steep")
        # If a synthetic #0 steep row and a regular Fibo row describe the same
        # scale, keep the regular row. The #0 row is only a watchlist substitute
        # while regular 23.6/61.8 logic has not produced a formation.
        if candidate_steep != current_steep:
            return not candidate_steep
        candidate_anchor = float(candidate.stop_loss)
        current_anchor = float(current.stop_loss)
        anchor_gap = abs(candidate_anchor - current_anchor) / max(abs(candidate_anchor), abs(current_anchor), 1e-9)
        candidate_size = _fibo_formation_size(candidate)
        current_size = _fibo_formation_size(current)
        if anchor_gap <= 0.08:
            candidate_strength = _fibo_formation_strength(candidate)
            current_strength = _fibo_formation_strength(current)
            if abs(candidate_strength - current_strength) > max(candidate_strength, current_strength, 1e-9) * 0.03:
                return candidate_strength > current_strength
        if abs(candidate_size - current_size) > max(candidate_size, current_size, 1e-9) * 0.03:
            return candidate_size > current_size
        if candidate.incline_duration_days != current.incline_duration_days:
            return candidate.incline_duration_days > current.incline_duration_days
        return candidate.incline_start_date < current.incline_start_date

    for item in items:
        duplicate_idx = next((idx for idx, existing in enumerate(picked) if _same_scale_fibo_formation(item, existing)), None)
        if duplicate_idx is None:
            picked.append(item)
        elif prefer(item, picked[duplicate_idx]):
            picked[duplicate_idx] = item
    return picked


def _is_bullish_hammer(c: pd.Series) -> bool:
    body = abs(float(c["Close"] - c["Open"]))
    candle_range = float(c["High"] - c["Low"])
    lower = min(float(c["Open"]), float(c["Close"])) - float(c["Low"])
    upper = float(c["High"]) - max(float(c["Open"]), float(c["Close"]))
    if body == 0:
        # Doji hammers are valid only when the lower shadow is dominant;
        # balanced long-legged doji candles should not be treated as hammers.
        return candle_range > 0 and lower > 0 and lower >= 1.5 * max(upper, 1e-9)
    return lower >= 2 * body and upper <= 2 * body and lower >= 1.5 * max(upper, 1e-9)


def _is_bearish_shooting_star(c: pd.Series) -> bool:
    body = abs(float(c["Close"] - c["Open"]))
    candle_range = float(c["High"] - c["Low"])
    upper = float(c["High"]) - max(float(c["Open"]), float(c["Close"]))
    lower = min(float(c["Open"]), float(c["Close"])) - float(c["Low"])
    if body == 0:
        # Doji shooting stars are valid only when the upper shadow is dominant;
        # candles with long wicks on both sides are neutral long-legged doji.
        return candle_range > 0 and upper > 0 and upper >= 1.5 * max(lower, 1e-9)
    return upper >= 2 * body and lower <= 2 * body and upper >= 1.5 * max(lower, 1e-9)


def _touches_level(c: pd.Series, level: float) -> bool:
    return float(c["Low"]) <= level <= float(c["High"])


def _overlaps_price_zone(c: pd.Series, lower: float, upper: float) -> bool:
    return float(c["Low"]) <= upper and float(c["High"]) >= lower


def _is_bullish_engulfing(
    c1: pd.Series,
    c2: pd.Series,
    level: float,
    close_floor: float | None = None,
    zone_floor: float | None = None,
) -> bool:
    c1_open = float(c1["Open"])
    c1_close = float(c1["Close"])
    c2_open = float(c2["Open"])
    c2_close = float(c2["Close"])
    if not (c1_close < c1_open and c2_close > c2_open):
        return False
    close_floor = level if close_floor is None else close_floor
    if zone_floor is None:
        touched_retest_area = _touches_level(c1, level) or _touches_level(c2, level)
    else:
        touched_retest_area = _overlaps_price_zone(c1, zone_floor, level) or _overlaps_price_zone(c2, zone_floor, level)
    return (
        c2_open < c1_close
        and c2_close > c1_open
        and min(c2_open, c2_close) <= min(c1_open, c1_close)
        and max(c2_open, c2_close) >= max(c1_open, c1_close)
        and touched_retest_area
        and c2_close > close_floor
    )


def _is_bullish_piercing_line(c1: pd.Series, c2: pd.Series, level: float) -> bool:
    c1_open = float(c1["Open"])
    c1_close = float(c1["Close"])
    c2_open = float(c2["Open"])
    c2_close = float(c2["Close"])
    if not (c1_close < c1_open and c2_close > c2_open):
        return False
    midpoint_c1 = (c1_open + c1_close) / 2.0
    c1_body_low = min(c1_open, c1_close)
    return (
        c2_open < c1_body_low
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
    return lo1 <= lo2 and hi2 <= hi1 and (_touches_level(c1, level) or _touches_level(c2, level))

def _is_morning_star(c1: pd.Series, c2: pd.Series, c3: pd.Series, level: float, doji_middle: bool = False, allow_equal_third_close: bool = False) -> bool:
    o1, cl1, _, _, b1 = _candle_parts(c1); o2, cl2, _, _, b2 = _candle_parts(c2); o3, cl3, _, _, _ = _candle_parts(c3)
    c1_body_low = min(o1, cl1)
    c2_body_high = max(o2, cl2)
    c3_body_low = min(o3, cl3)
    if not (cl1 < o1 and cl3 > o3):
        return False
    if b2 >= b1 * 0.6:
        return False
    if doji_middle and not _is_doji(c2):
        return False
    if c2_body_high >= c1_body_low:
        return False
    if allow_equal_third_close:
        if c2_body_high > c3_body_low:
            return False
    elif c2_body_high >= c3_body_low:
        return False
    mid1 = (o1 + cl1) / 2.0
    return cl3 > mid1 and (_touches_level(c1, level) or _touches_level(c2, level) or _touches_level(c3, level)) and cl3 > level

def _is_bearish_harami(c1: pd.Series, c2: pd.Series, level: float) -> bool:
    o1, cl1, _, _, b1 = _candle_parts(c1); o2, cl2, _, _, b2 = _candle_parts(c2)
    if not (cl1 > o1 and cl2 < o2 and b2 < b1):
        return False
    lo1, hi1 = sorted((o1, cl1)); lo2, hi2 = sorted((o2, cl2))
    return lo1 <= lo2 and hi2 <= hi1 and (_touches_level(c1, level) or _touches_level(c2, level))

def _is_bearish_engulfing(
    c1: pd.Series,
    c2: pd.Series,
    level: float,
    close_ceiling: float | None = None,
    zone_ceiling: float | None = None,
) -> bool:
    o1, cl1, _, _, _ = _candle_parts(c1)
    o2, cl2, _, _, _ = _candle_parts(c2)
    if not (cl1 > o1 and cl2 < o2):
        return False
    close_ceiling = level if close_ceiling is None else close_ceiling
    if zone_ceiling is None:
        touched_retest_area = _touches_level(c1, level) or _touches_level(c2, level)
    else:
        touched_retest_area = _overlaps_price_zone(c1, level, zone_ceiling) or _overlaps_price_zone(c2, level, zone_ceiling)
    return (
        o2 > cl1
        and cl2 < o1
        and min(o2, cl2) <= min(o1, cl1)
        and max(o2, cl2) >= max(o1, cl1)
        and touched_retest_area
        and cl2 < close_ceiling
    )


def _is_dark_cloud_cover(c1: pd.Series, c2: pd.Series, level: float) -> bool:
    o1, cl1, _, _, _ = _candle_parts(c1); o2, cl2, _, _, _ = _candle_parts(c2)
    c1_body_high = max(o1, cl1)
    if not (cl1 > o1 and cl2 < o2 and o2 > c1_body_high):
        return False
    mid1 = (o1 + cl1) / 2.0
    return cl2 < mid1 and (_touches_level(c1, level) or _touches_level(c2, level)) and cl2 < level

def _is_evening_star(c1: pd.Series, c2: pd.Series, c3: pd.Series, level: float, doji_middle: bool = False, allow_equal_third_close: bool = False) -> bool:
    o1, cl1, _, _, b1 = _candle_parts(c1); o2, cl2, _, _, b2 = _candle_parts(c2); o3, cl3, _, _, _ = _candle_parts(c3)
    c1_body_high = max(o1, cl1)
    c2_body_low = min(o2, cl2)
    c3_body_high = max(o3, cl3)
    if not (cl1 > o1 and cl3 < o3):
        return False
    if b2 >= b1 * 0.6:
        return False
    if doji_middle and not _is_doji(c2):
        return False
    if c2_body_low <= c1_body_high:
        return False
    if allow_equal_third_close:
        if c2_body_low < c3_body_high:
            return False
    elif c2_body_low <= c3_body_high:
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


def _early_sideways_after_anchor_window(
    w: pd.DataFrame,
    i_start: int,
    direction: str = "long",
    min_days: int = 22,
    max_days: int = 32,
    band_pct: float = 0.10,
    max_progress_pct: float = 0.12,
) -> tuple[int, int, float, float, float, float] | None:
    """Detect an anchor followed by a flat month instead of an immediate impulse.

    Fibo anchors should mark the start of the incline.  If the first month after
    the anchor remains in a tight band and makes little directional progress, the
    selected old anchor is stale; a later breakout point should become the anchor.
    """
    if i_start < 0 or i_start >= len(w) - min_days:
        return None
    end = min(len(w), i_start + max_days)
    seg = w.iloc[i_start:end].reset_index(drop=True)
    if len(seg) < min_days:
        return None
    highs = pd.to_numeric(seg["High"], errors="coerce")
    lows = pd.to_numeric(seg["Low"], errors="coerce")
    if highs.dropna().empty or lows.dropna().empty:
        return None
    hi = float(highs.max())
    lo = float(lows.min())
    mid = (hi + lo) / 2.0
    if mid <= 0:
        return None
    rng_pct = (hi - lo) / mid
    anchor_price = float(lows.iloc[0] if direction == "long" else highs.iloc[0])
    if anchor_price <= 0:
        return None
    progress_pct = ((hi - anchor_price) / anchor_price) if direction == "long" else ((anchor_price - lo) / anchor_price)
    if rng_pct <= band_pct and progress_pct <= max_progress_pct:
        return (i_start, i_start + len(seg) - 1, hi, lo, rng_pct, progress_pct)
    return None


def _select_impulse_start_long(
    w: pd.DataFrame,
    peak_idx: int,
    min_days: int,
    max_lookback: int = 140,
    reset_after_sideways: bool = True,
) -> int | None:
    low = pd.to_numeric(w["Low"], errors="coerce")
    left = max(0, peak_idx - max_lookback)
    right = peak_idx - min_days
    if right <= left:
        return None
    # If a long sideways block exists before the selected peak, treat the breakout
    # after that block as a newer impulse and avoid anchoring to very old lows.
    # 3P can disable this to prefer a larger valid formation when one exists.
    if reset_after_sideways:
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



def _wait_if_scan_paused() -> bool:
    while PAUSE_SCAN_EVENT.is_set() and not STOP_SCAN_EVENT.is_set():
        time.sleep(0.25)
    return not STOP_SCAN_EVENT.is_set()


def _retry_error_brief(exc: BaseException | str) -> str:
    text = str(exc)
    lowered = text.lower()
    markers = [
        ("connection reset by peer", "Connection reset by peer"),
        ("connection refused", "Connection refused"),
        ("timed out", "Timeout"),
        ("timeout", "Timeout"),
        ("too many requests", "Too many requests"),
        ("http error 429", "HTTP 429"),
        ("temporarily unavailable", "Temporarily unavailable"),
        ("service unavailable", "Service unavailable"),
        ("captcha", "Captcha/rate limit"),
        ("przekroczony dzienny limit", "Stooq daily limit"),
    ]
    for needle, label in markers:
        if needle in lowered:
            m = re.search(r"\[Errno\s+\d+\]", text)
            return f"{label} {m.group(0)}" if m else label
    return _compact_error(text)[:240] if "_compact_error" in globals() else text[:240]


def _is_rate_limit_download_error(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    markers = (
        "rate limit",
        "captcha",
        "przekroczony dzienny limit",
        "too many requests",
        "http error 429",
    )
    return any(m in text for m in markers)


def _is_retryable_download_error(exc: BaseException | str) -> bool:
    if _is_rate_limit_download_error(exc):
        return False
    text = str(exc).lower()
    markers = (
        "connection refused", "connection reset by peer", "timed out", "timeout",
        "temporarily unavailable", "service unavailable",
        "remote end closed connection", "bad gateway", "gateway timeout",
    )
    return any(m in text for m in markers)


def _load_daily_data_with_retries(*, symbol: str, instrument_type: str, persist: bool = True, fetch_older_data: bool = False):
    last_exc: BaseException | None = None
    for attempt in range(1, 4):
        if STOP_SCAN_EVENT.is_set() or not _wait_if_scan_paused():
            raise RuntimeError("scan stopped")
        try:
            return load_or_update_daily_data(
                symbol=symbol,
                instrument_type=instrument_type,
                persist=persist,
                fetch_older_data=fetch_older_data,
            )
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit_download_error(exc):
                # Forex and commodity Playwright flows have their own automatic
                # Tor/CAPTCHA/fallback handling; never block their worker pool on
                # an interactive VPN-change pause.
                if instrument_type not in {"forex", "commodity"}:
                    PAUSE_SCAN_EVENT.set()
                raise
            if not _is_retryable_download_error(exc) or attempt >= 3:
                raise
            print(f"[download-retry] {symbol}: attempt {attempt}/3 failed ({_retry_error_brief(exc)}); retrying...", flush=True)
            for _ in range(8 * attempt):
                if STOP_SCAN_EVENT.is_set() or not _wait_if_scan_paused():
                    raise RuntimeError("scan stopped")
                time.sleep(0.25)
    raise last_exc or RuntimeError("download failed")


def _search_fetch_symbol(ticker: str, group_name: str, exchange_suffix: str | None) -> tuple[str, str]:
    if group_name == "forex":
        instrument = "forex"
    elif group_name in {"commodities", "indexes"}:
        instrument = "commodity"
    elif group_name == "single":
        detected = detect_instrument_type(ticker, None)
        instrument = "commodity" if detected == "commodity" else ("forex" if detected == "forex" else "stock")
    else:
        instrument = "stock"
    fetch_symbol = ticker
    if instrument == "stock" and exchange_suffix and not ticker.endswith(exchange_suffix.upper()):
        fetch_symbol = f"{ticker}{exchange_suffix}"
    if instrument == "stock" and "." not in fetch_symbol and len(fetch_symbol) <= 5:
        fetch_symbol = f"{fetch_symbol}.WA"
    if instrument == "commodity" and group_name != "indexes" and ticker.upper() not in API_METAL_COMMODITIES:
        fetch_symbol = str(COMMODITY_STOOQ_MAP.get(ticker.upper(), fetch_symbol)).upper()
    return fetch_symbol, instrument


def _read_refresh_state() -> dict:
    try:
        if REFRESH_STATE_FILE.exists():
            return json.loads(REFRESH_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_refresh_state(state: dict) -> None:
    try:
        REFRESH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        REFRESH_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:
        print(f"[refresh-check] warning: could not write state: {_retry_error_brief(exc)}")


def _warsaw_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Warsaw"))
    except Exception:
        return datetime.now(UTC)


def _warsaw_phase_now() -> tuple[str, str]:
    now = _warsaw_now()
    phase = "pre1945" if now.time() < dt_time(19, 45) else "post1945"
    return now.strftime("%Y-%m-%d"), phase


def _warsaw_daily_bulk_day() -> str | None:
    now = _warsaw_now()
    if now.time() < dt_time(3, 0):
        return None
    return now.strftime("%Y-%m-%d")


def _is_after_warsaw_stock_close() -> bool:
    return _warsaw_now().time() >= dt_time(17, 30)


def _is_ui_commodity_ticker(ticker: str) -> bool:
    raw = (ticker or "").strip().upper()
    mapped = str(COMMODITY_STOOQ_MAP.get(raw, raw)).lower()
    return raw in COMMODITY_STOOQ_MAP and not mapped.startswith("^")


def _commodity_missing_days_vs_yahoo(ticker: str) -> int:
    raw = (ticker or "").strip().upper()
    if not _is_ui_commodity_ticker(raw):
        return 0
    symbol = str(COMMODITY_STOOQ_MAP.get(raw, raw)).upper()
    csv_path = local_csv_path_for_symbol(symbol, "commodity")
    if not csv_path.exists():
        return 9999
    try:
        local = pd.read_csv(csv_path)
        local_dates = pd.to_datetime(local.get("Date"), errors="coerce").dropna()
        if local_dates.empty:
            return 9999
        local_latest = local_dates.max().date()
        yahoo_symbol = raw
        remote, _candidate, _name = call_silenced(_yahoo_download, yahoo_symbol, "commodity")
        remote_dates = pd.to_datetime(remote.get("Date"), errors="coerce").dropna()
        if remote_dates.empty:
            return 0
        return int((remote_dates.dt.date > local_latest).sum())
    except Exception as exc:
        print(f"[refresh-check] {raw}: Yahoo freshness probe skipped ({_retry_error_brief(exc)})")
        return 0


def _commodity_refresh_targets_from_env() -> set[str]:
    raw = os.getenv("STOCKHELPER_COMMODITIES_REFRESH_TICKERS", "")
    return {part.strip().upper() for part in re.split(r"[,;\s]+", raw) if part.strip()}


def _commodity_refresh_target_matches(ticker: str, fetch_symbol: str, refresh_targets: set[str]) -> bool:
    if not refresh_targets:
        return False
    return ticker.upper() in refresh_targets or fetch_symbol.upper() in refresh_targets


def _commodity_csv_health_check(members: Sequence[str]) -> None:
    try:
        min_rows = max(1, int(os.getenv("STOCKHELPER_COMMODITIES_MIN_ROWS", "250")))
    except ValueError:
        min_rows = 250

    def _health_row(ticker: str) -> tuple[str, Path, int, str, Exception | None]:
        raw = (ticker or "").strip().upper()
        csv_path = local_csv_path_for_symbol(raw, "commodity")
        if not csv_path.exists():
            mapped = str(COMMODITY_STOOQ_MAP.get(raw, raw)).upper()
            csv_path = local_csv_path_for_symbol(mapped, "commodity")
        try:
            if not csv_path.exists():
                raise FileNotFoundError(str(csv_path))
            df = pd.read_csv(csv_path, usecols=lambda col: col in {"Date"})
            rows = len(df)
            dates = pd.to_datetime(df.get("Date"), errors="coerce").dropna() if "Date" in df.columns else pd.Series(dtype="datetime64[ns]")
            latest = dates.max().date().isoformat() if not dates.empty else "-"
            return raw, csv_path, rows, latest, None
        except Exception as exc:
            return raw, csv_path, 0, "-", exc

    print(f"[commodity-check] CSV row-count check (min_rows={min_rows})")
    def _print_summary(checked: Sequence[tuple[str, Path, int, str, Exception | None]]) -> list[str]:
        ok_count = 0
        retry_tickers: list[str] = []
        for raw, csv_path, rows, latest, exc in checked:
            if exc is not None:
                retry_tickers.append(raw)
                print(f"[commodity-check] WARN {raw}: could not read CSV ({_retry_error_brief(exc)})")
                continue
            status = "OK" if rows >= min_rows else "WARN"
            if status == "OK":
                ok_count += 1
            else:
                retry_tickers.append(raw)
            print(f"[commodity-check] {status} {raw}: rows={rows}, latest={latest}, csv={csv_path}")
        print(f"[commodity-check] summary: ok={ok_count}, warn={len(retry_tickers)}, total={len(checked)}")
        return retry_tickers

    checked = [_health_row(ticker) for ticker in members]
    retry_tickers = _print_summary(checked)

    if retry_tickers and os.getenv("STOCKHELPER_COMMODITIES_HEALTH_RETRY", "1") != "0":
        print(f"[commodity-check] replacing and retrying {len(retry_tickers)} warned commodity CSV(s) once: {', '.join(retry_tickers[:8])}{' ...' if len(retry_tickers) > 8 else ''}")
        old_force = os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH")
        try:
            os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
            for raw in retry_tickers:
                _raw, csv_path, _rows, _latest, _exc = _health_row(raw)
                backup = csv_path.read_bytes() if csv_path.exists() else None
                try:
                    # A forced merge can leave a short CSV short. Remove it first so
                    # the retry performs a clean full-history download/replacement.
                    csv_path.unlink(missing_ok=True)
                    load_or_update_daily_data(symbol=raw, instrument_type="commodity", persist=True, fetch_older_data=False)
                    if not csv_path.exists():
                        raise FileNotFoundError(f"replacement did not create {csv_path}")
                except Exception as exc:
                    print(f"[commodity-check] retry failed for {raw}: {_retry_error_brief(exc)}")
                    if backup is not None:
                        csv_path.parent.mkdir(parents=True, exist_ok=True)
                        csv_path.write_bytes(backup)
        finally:
            if old_force is None:
                os.environ.pop("STOCKHELPER_FORCE_REMOTE_REFRESH", None)
            else:
                os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = old_force
        print("[commodity-check] post-retry CSV row-count check")
        _print_summary([_health_row(ticker) for ticker in members])


def _forex_csv_health_check(members: Sequence[str], sources: dict[str, str] | None = None) -> None:
    """Report and retry FX caches that do not cover the rolling 1.5-year window."""
    source_by_ticker = {
        (ticker or "").strip().upper(): source
        for ticker, source in (sources or {}).items()
    }
    try:
        required_days = max(1, int(os.getenv("STOCKHELPER_FOREX_REQUIRED_DAYS", "548")))
    except ValueError:
        required_days = 548
    today = datetime.now(UTC).date()
    required_start = today - timedelta(days=required_days)
    # Markets may be closed on the exact boundary date.
    oldest_tolerance = required_start + timedelta(days=7)

    def _health_row(ticker: str) -> tuple[str, Path, int, str, str, int, Exception | None]:
        raw = (ticker or "").strip().upper()
        csv_path = local_csv_path_for_symbol(raw, "forex")
        try:
            dates = pd.to_datetime(pd.read_csv(csv_path, usecols=["Date"])["Date"], errors="coerce").dropna()
            if dates.empty:
                raise ValueError("CSV has no valid dates")
            oldest = dates.min().date()
            latest = dates.max().date()
            return raw, csv_path, len(dates), oldest.isoformat(), latest.isoformat(), (latest - oldest).days, None
        except Exception as exc:
            return raw, csv_path, 0, "-", "-", 0, exc

    def _warned(row: tuple[str, Path, int, str, str, int, Exception | None]) -> bool:
        _raw, _path, _rows, oldest, _latest, _span, exc = row
        return (
            exc is not None
            or oldest == "-"
            or date.fromisoformat(oldest) > oldest_tolerance
            or _latest == "-"
            or date.fromisoformat(_latest) < today - timedelta(days=7)
        )

    def _print_summary(rows: Sequence[tuple[str, Path, int, str, str, int, Exception | None]]) -> list[str]:
        retry: list[str] = []
        for raw, csv_path, row_count, oldest, latest, span_days, exc in rows:
            warn = _warned((raw, csv_path, row_count, oldest, latest, span_days, exc))
            if warn:
                retry.append(raw)
            detail = f"error={_retry_error_brief(exc)}" if exc else f"rows={row_count}, oldest={oldest}, latest={latest}, span_days={span_days}"
            source = _forex_source_summary_label(source_by_ticker.get(raw, "unknown"))
            print(f"[forex-check] {'WARN' if warn else 'OK'} {raw}: {detail}, source={source}, csv={csv_path}")
        print(f"[forex-check] summary: ok={len(rows) - len(retry)}, warn={len(retry)}, total={len(rows)}")
        return retry

    print(f"[forex-check] rolling 1.5-year coverage check (required_start<={required_start}, tolerance=7d)")
    retry_tickers = _print_summary([_health_row(ticker) for ticker in members])
    if not retry_tickers or os.getenv("STOCKHELPER_FOREX_HEALTH_RETRY", "1") == "0":
        return

    try:
        retry_workers_setting = max(1, int(os.getenv("STOCKHELPER_FOREX_HEALTH_WORKERS", "4")))
    except ValueError:
        retry_workers_setting = 4
    try:
        retry_rounds = max(1, int(os.getenv("STOCKHELPER_FOREX_HEALTH_RETRY_ROUNDS", "4")))
    except ValueError:
        retry_rounds = 4
    def _replace(raw: str) -> str:
        _raw, csv_path, _rows, _oldest, _latest, _span, _exc = _health_row(raw)
        backup = csv_path.read_bytes() if csv_path.exists() else None
        try:
            csv_path.unlink(missing_ok=True)
            _df, _path, meta = load_or_update_daily_data(
                symbol=raw, instrument_type="forex", persist=True, fetch_older_data=False
            )
            if not csv_path.exists():
                raise FileNotFoundError(f"replacement did not create {csv_path}")
            return str((meta or {}).get("source", "unknown"))
        except Exception:
            if backup is not None:
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                csv_path.write_bytes(backup)
            raise

    for retry_round in range(1, retry_rounds + 1):
        retry_workers = min(retry_workers_setting, len(retry_tickers))
        print(
            f"[forex-check] retry round {retry_round}/{retry_rounds}: replacing and retrying "
            f"{len(retry_tickers)} incomplete CSV(s) with {retry_workers} worker(s): {', '.join(retry_tickers)}"
        )
        with ThreadPoolExecutor(max_workers=retry_workers) as executor:
            futures = {executor.submit(_replace, raw): raw for raw in retry_tickers}
            for future, raw in [(future, futures[future]) for future in futures]:
                try:
                    source_by_ticker[raw] = future.result()
                except Exception as exc:
                    print(f"[forex-check] retry round {retry_round} failed for {raw}: {_retry_error_brief(exc)}")
        print(f"[forex-check] post-retry round {retry_round} rolling coverage check")
        retry_tickers = _print_summary([_health_row(ticker) for ticker in members])
        if not retry_tickers:
            print(f"[forex-check] all forex CSVs complete after retry round {retry_round}.")
            break
        if retry_round < retry_rounds:
            print(f"[forex-check] {len(retry_tickers)} CSV(s) still incomplete; starting another condition-driven download round.")


def _passes_scanner_liquidity(avg_10d_pln: float | None, instrument_type: str, min_avg: float) -> bool:
    """Apply turnover filtering only when the data source has usable volume."""
    # FX feeds expose either zero volume or broker-specific tick volume, neither
    # of which is comparable to the PLN turnover threshold used for shares.
    # Commodity turnover is enforced only when the source supplies usable volume.
    if instrument_type == "forex":
        return True
    if instrument_type == "commodity" and (avg_10d_pln is None or avg_10d_pln <= 0):
        return True
    return avg_10d_pln is not None and avg_10d_pln >= min_avg



def _business_day_gap_after_local(local_latest: date, remote_latest: date) -> int:
    if remote_latest <= local_latest:
        return 0
    try:
        days = pd.bdate_range(
            pd.Timestamp(local_latest) + pd.Timedelta(days=1),
            pd.Timestamp(remote_latest),
        )
        return int(len(days))
    except Exception:
        return max(0, (remote_latest - local_latest).days)


def _wig20_index_yahoo_freshness_probe() -> tuple[int, str, str, str]:
    csv_path = local_csv_path_for_symbol("WIG20", "commodity")
    if not csv_path.exists():
        return 9999, "-", "-", "missing-local-cache"
    try:
        local = pd.read_csv(csv_path)
        local_dates = pd.to_datetime(local.get("Date"), errors="coerce").dropna()
        if local_dates.empty:
            return 9999, "-", "-", "empty-local-cache"
        local_latest = local_dates.max().date()

        # WIG20.WA on Yahoo can expose only the newest candle.  To decide
        # whether the local Stooq-base WIG20 cache is missing *more than one*
        # Warsaw session, cross-check against a liquid WIG20 constituent that
        # reliably updates on Yahoo when WIG20 does (KGH.WA).
        reference, candidate, _name = call_silenced(_yahoo_download_window, "KGH.WA", "stock", period="10d")
        reference_dates = pd.to_datetime(reference.get("Date"), errors="coerce").dropna()
        if reference_dates.empty:
            return 0, local_latest.isoformat(), "-", candidate
        reference_latest = reference_dates.max().date()
        missing = _business_day_gap_after_local(local_latest, reference_latest)
        return missing, local_latest.isoformat(), reference_latest.isoformat(), candidate
    except Exception as exc:
        print(f"[refresh-check] WIG20/KGH.WA: Yahoo freshness probe skipped ({_retry_error_brief(exc)})")
        try:
            local_latest_text = "-"
            if 'local_latest' in locals():
                local_latest_text = local_latest.isoformat()
            remote, candidate, _name = call_silenced(_yahoo_download_window, "WIG20", "commodity", period="10d")
            remote_dates = pd.to_datetime(remote.get("Date"), errors="coerce").dropna()
            if remote_dates.empty:
                return 0, local_latest_text, "-", candidate
            remote_latest = remote_dates.max().date()
            if local_latest_text == "-":
                return 0, local_latest_text, remote_latest.isoformat(), candidate
            local_latest_date = pd.Timestamp(local_latest_text).date()
            remote_new_rows = int((remote_dates.dt.date > local_latest_date).sum())
            return remote_new_rows, local_latest_text, remote_latest.isoformat(), candidate
        except Exception as fallback_exc:
            print(f"[refresh-check] WIG20: Yahoo fallback freshness probe skipped ({_retry_error_brief(fallback_exc)})")
            return 0, "-", "-", "probe-error"

def _stock_csv_has_data_for_symbol(fetch_symbol: str) -> bool:
    path = local_csv_path_for_symbol(fetch_symbol, "stock")
    try:
        if not path.exists():
            return False
        df = pd.read_csv(path, nrows=5)
        return not df.empty and "Date" in df.columns
    except Exception:
        return False


def _missing_wig_csv_members(members: list[str], exchange_suffix: str | None) -> list[str]:
    missing: list[str] = []
    for ticker in members:
        fetch_symbol, instrument = _search_fetch_symbol(ticker, "wig", exchange_suffix)
        if instrument == "stock" and not _stock_csv_has_data_for_symbol(fetch_symbol):
            missing.append(ticker)
    return missing


def _stock_yahoo_freshness_probe(fetch_symbol: str) -> tuple[int, str, str, str]:
    csv_path = local_csv_path_for_symbol(fetch_symbol, "stock")
    if not csv_path.exists():
        return 9999, "-", "-", "missing-local-cache"
    try:
        local = pd.read_csv(csv_path)
        local_dates = pd.to_datetime(local.get("Date"), errors="coerce").dropna()
        if local_dates.empty:
            return 9999, "-", "-", "empty-local-cache"
        local_latest = local_dates.max().date()
        remote, candidate, _name = call_silenced(_yahoo_download_window, fetch_symbol, "stock", period="10d")
        remote_dates = pd.to_datetime(remote.get("Date"), errors="coerce").dropna()
        if remote_dates.empty:
            return 0, local_latest.isoformat(), "-", candidate
        remote_latest = remote_dates.max().date()
        missing = int((remote_dates.dt.date > local_latest).sum())
        return missing, local_latest.isoformat(), remote_latest.isoformat(), candidate
    except Exception as exc:
        print(f"[refresh-check] {fetch_symbol}: Yahoo freshness probe skipped ({_retry_error_brief(exc)})")
        return 0, "-", "-", "probe-error"


def _stock_missing_candles_vs_yahoo(fetch_symbol: str) -> int:
    missing, _local_latest, _remote_latest, _candidate = _stock_yahoo_freshness_probe(fetch_symbol)
    return missing


def _stooq_bulk_bucket(day: str | None = None) -> str | None:
    daily_bulk_day = day or _warsaw_daily_bulk_day()
    if not daily_bulk_day:
        return None
    return f"stooq_bulk:{daily_bulk_day}"


def _mark_stooq_bulk_attempt(bucket: str, result: str) -> None:
    state = _read_refresh_state()
    state[bucket] = {"checked_at": datetime.now(UTC).isoformat(), "result": result}
    _write_refresh_state(state)
    os.environ["STOCKHELPER_STOOQ_BULK_ATTEMPTED_BUCKET"] = bucket


def _stooq_bulk_already_attempted(bucket: str | None) -> bool:
    if not bucket:
        return False
    if os.environ.get("STOCKHELPER_STOOQ_BULK_ATTEMPTED_BUCKET") == bucket:
        return True
    return bool(_read_refresh_state().get(bucket))


def _try_refresh_wig_with_stooq_bulk(group_name: str, reason: str) -> bool:
    """Refresh Warsaw stock/index CSVs from Stooq bulk before per-symbol Yahoo merging."""
    group_l = (group_name or "").lower()
    if not ((group_name or "").upper().startswith("WIG") or group_l == "indexes"):
        return False
    if os.environ.get("STOCKHELPER_DISABLE_WIG_BULK_REFRESH") == "1":
        return False
    bucket = _stooq_bulk_bucket()
    if _stooq_bulk_already_attempted(bucket):
        print(
            f"[refresh-check] {group_name}: Stooq d_pl_txt bulk already attempted for this Warsaw day; "
            "skipping duplicate bulk download and using per-symbol/Yahoo refresh if needed."
        )
        return False
    if bucket:
        _mark_stooq_bulk_attempt(bucket, "attempted")
    try:
        from utilities.stooq_playwright import download_and_import_stooq_wig_bulk_data
        label = "indexes" if group_l == "indexes" else "WIG"
        print(f"[refresh-check] {label}: {reason}; downloading Stooq d_pl_txt bulk archive.")
        result = download_and_import_stooq_wig_bulk_data(
            stocks_dir=CSV_DATA_DIR / "stocks",
            commodities_dir=CSV_DATA_DIR / "commodities",
            indexes_dir=CSV_DATA_DIR / "indexes",
        )
        print(
            f"[refresh-check] {label}: bulk refresh completed "
            f"written={result['written']} skipped={result['skipped']} members={result['members']} "
            f"indices_written={result.get('indices_written', 0)} "
            f"indices_members={result.get('indices_members', 0)}."
        )
        os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
        os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
        if bucket:
            _mark_stooq_bulk_attempt(bucket, "bulk")
        return True
    except Exception as exc:
        print(f"[refresh-check] WIG: bulk refresh failed ({_retry_error_brief(exc)}); falling back to per-symbol refresh.")
        return False

def _should_refresh_group_data(group_name: str, members: list[str], exchange_suffix: str | None) -> bool:
    if os.environ.get("STOCKHELPER_CACHE_ONLY") == "1":
        print(f"[refresh-check] {group_name}: cache-only already requested; skipping remote probe.")
        os.environ.pop("STOCKHELPER_FORCE_REMOTE_REFRESH", None)
        return False
    STOP_SCAN_EVENT.clear(); PAUSE_SCAN_EVENT.clear()
    group_l = (group_name or "").lower()
    if group_l == "commodities":
        day, phase = _warsaw_phase_now()
        state = _read_refresh_state()
        bucket = f"commodities:{day}:{phase}"
        stale: list[str] = []
        stale_tickers: list[str] = []
        for t in members:
            missing = _commodity_missing_days_vs_yahoo(t)
            if missing > 0:
                stale.append(f"{t}({missing} candle{'s' if missing != 1 else ''})")
                stale_tickers.append(t.upper())
        if stale:
            print(f"[refresh-check] commodities stale vs Yahoo: {', '.join(stale[:8])}{' ...' if len(stale)>8 else ''} -> refresh only missing/stale")
            state[bucket] = {"checked_at": datetime.now(UTC).isoformat(), "result": "stale", "tickers": stale_tickers}
            _write_refresh_state(state)
            os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
            os.environ.pop("STOCKHELPER_FORCE_REMOTE_REFRESH", None)
            os.environ["STOCKHELPER_COMMODITIES_REFRESH_TICKERS"] = ",".join(stale_tickers)
            return True
        os.environ.pop("STOCKHELPER_COMMODITIES_REFRESH_TICKERS", None)
        if state.get(bucket):
            print(f"[refresh-check] commodities {phase}: already checked today -> cache-only mode ON")
            os.environ["STOCKHELPER_CACHE_ONLY"] = "1"
            os.environ.pop("STOCKHELPER_FORCE_REMOTE_REFRESH", None)
            return False
        print(f"[refresh-check] commodities {phase}: no Yahoo-stale UI commodities; marking bucket checked")
        state[bucket] = {"checked_at": datetime.now(UTC).isoformat(), "result": "fresh"}
        _write_refresh_state(state)
        os.environ["STOCKHELPER_CACHE_ONLY"] = "1"
        os.environ.pop("STOCKHELPER_FORCE_REMOTE_REFRESH", None)
        return False

    daily_bulk_day = _warsaw_daily_bulk_day()
    if daily_bulk_day and (group_l.startswith("wig") or group_l == "indexes"):
        bucket = _stooq_bulk_bucket(daily_bulk_day)
        if not _stooq_bulk_already_attempted(bucket):
            if _try_refresh_wig_with_stooq_bulk(group_name, f"first WIG/index search after 03:00 Warsaw on {daily_bulk_day}"):
                return True

    if group_l == "indexes" and "WIG20" in {str(member).upper() for member in members}:
        missing_candles, local_latest, yahoo_latest, yahoo_candidate = _wig20_index_yahoo_freshness_probe()
        print(
            f"[refresh-check] WIG20: reference Yahoo {yahoo_candidate} latest={yahoo_latest}, "
            f"local WIG20 latest={local_latest}, estimated missing sessions={missing_candles}"
        )
        if missing_candles > 1:
            if _try_refresh_wig_with_stooq_bulk(
                group_name,
                f"WIG20 is missing {missing_candles} sessions vs Yahoo latest; Stooq bulk needed before Yahoo fresh-candle merge",
            ):
                return True
            os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
            os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
            return True
        if missing_candles == 1:
            os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
            os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
            return True

    if group_l.startswith("wig"):
        missing_members = _missing_wig_csv_members(members, exchange_suffix)
        if missing_members:
            preview = ", ".join(missing_members[:10])
            suffix = " ..." if len(missing_members) > 10 else ""
            reason = f"missing local bulk CSV(s): {preview}{suffix}"
            print(f"[refresh-check] {group_name}: {len(missing_members)} expected WIG CSV(s) missing -> Stooq bulk refresh ({reason})")
            if _try_refresh_wig_with_stooq_bulk(group_name, reason):
                return True
            os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
            os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
            return True

    if group_l == "single":
        probes = members[:1]
    else:
        probe_count = min(3 if group_l == "wig" else 5, len(members))
        probes = random.sample(list(members), k=probe_count) if probe_count else []
        if probes:
            print(f"[refresh-check] {group_name}: random freshness probes: {', '.join(probes)}")
    checked = 0
    for ticker in probes:
        fetch_symbol, instrument = _search_fetch_symbol(ticker, group_name, exchange_suffix)
        try:
            if instrument == "stock":
                missing_candles, local_latest, yahoo_latest, yahoo_candidate = _stock_yahoo_freshness_probe(fetch_symbol)
                checked += 1
                print(
                    f"[refresh-check] {ticker}: Yahoo {yahoo_candidate} latest={yahoo_latest}, "
                    f"local latest={local_latest}, newer candles={missing_candles}"
                )
                if missing_candles > 0:
                    if group_l == "wig":
                        after_close = _is_after_warsaw_stock_close()
                        needs_bulk_first = (not after_close) or missing_candles > 1
                        if needs_bulk_first:
                            phase_reason = "before Warsaw close" if not after_close else "more than one Yahoo candle missing after Warsaw close"
                            if _try_refresh_wig_with_stooq_bulk(
                                group_name,
                                f"probe {ticker} found {missing_candles} newer Yahoo candles ({phase_reason})",
                            ):
                                return True
                    os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
                    os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
                    return True
                continue
            newer = has_new_remote_data(fetch_symbol, instrument)
            checked += 1
            print(f"[refresh-check] {ticker}: remote {'newer' if newer else 'not newer'}")
            if newer:
                if _try_refresh_wig_with_stooq_bulk(group_name, f"probe {ticker} found newer remote data"):
                    return True
                os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
                os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
                return True
        except Exception as exc:
            print(f"[refresh-check] {ticker}: probe failed ({_retry_error_brief(exc)}); refreshing to avoid stale cache")
            if _try_refresh_wig_with_stooq_bulk(group_name, f"probe {ticker} failed"):
                return True
            os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
            os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
            return True
    if group_l == "wig" and _is_after_warsaw_stock_close():
        print(
            f"[refresh-check] {group_name}: checked {checked} probe(s), no newer Yahoo data found, "
            "but it is after 17:30 Warsaw -> refresh mode ON to merge per-symbol Yahoo candles where available"
        )
        os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
        os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
        return True
    print(f"[refresh-check] {group_name}: checked {checked} probe(s), no newer remote data -> cache-only mode ON")
    os.environ["STOCKHELPER_CACHE_ONLY"] = "1"
    os.environ.pop("STOCKHELPER_FORCE_REMOTE_REFRESH", None)
    return False

def _scan_workers_override() -> int | None:
    raw = os.getenv("STOCKHELPER_SCAN_WORKERS", "").strip()
    if not raw:
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        print(f"[workers] ignoring invalid STOCKHELPER_SCAN_WORKERS={raw!r}", flush=True)
        return None


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
    out["span_a"] = span_a
    out["span_b"] = span_b
    out["cloud_top"] = pd.concat([span_a, span_b], axis=1).max(axis=1)
    out["cloud_bottom"] = pd.concat([span_a, span_b], axis=1).min(axis=1)
    return out.dropna(subset=["cloud_top", "cloud_bottom"])


def _qualifies(df: pd.DataFrame, min_days: int = 80, debug_ticker: str | None = None) -> ScanResult | None:
    if len(df) < min_days + 2:
        if debug_ticker:
            _debug_log_scan(debug_ticker, f"qualifies failed: insufficient rows len={len(df)} required={min_days+2}")
        return None

    def _qdbg(msg: str) -> None:
        if debug_ticker:
            _debug_log_scan(debug_ticker, msg)

    body_high = df[["Open", "Close"]].max(axis=1)
    body_low = df[["Open", "Close"]].min(axis=1)
    top = df["cloud_top"]
    bottom = df["cloud_bottom"]
    close = df["Close"]

    # WYNIKI 1 aligned with WYNIKI 2 retest-style tolerance:
    # side is maintained through "inside cloud" closes; only opposite-side close breaks trend.
    above_respected = close >= bottom
    below_respected = close <= top

    def _run_with_inside_tolerance(target_side: str) -> int:
        run = 0
        for i in range(len(df) - 1, -1, -1):
            c = float(close.iloc[i])
            t = float(top.iloc[i])
            b = float(bottom.iloc[i])
            if target_side == "above":
                if c < b:  # opposite side break
                    break
            else:
                if c > t:  # opposite side break
                    break
            run += 1
        return run

    run_above = _run_with_inside_tolerance("above")
    run_below = _run_with_inside_tolerance("below")
    current_side = "above" if run_above >= run_below else "below"
    run = run_above if current_side == "above" else run_below

    if run < min_days:
        _qdbg(f"qualifies failed: current_side={current_side}, run={run} < min_days={min_days} (inside-cloud tolerated, opposite-side close breaks)")
        return None

    window_start = len(df) - run
    start_idx = window_start
    for i in range(window_start, len(df)):
        prev_i = i - 1
        if current_side == "below":
            crossed_now = close.iloc[i] < bottom.iloc[i]
            prev_not_below = True if i == 0 else close.iloc[prev_i] >= bottom.iloc[prev_i]
            if crossed_now and prev_not_below:
                start_idx = i
                break
        else:
            crossed_now = close.iloc[i] > top.iloc[i]
            prev_not_above = True if i == 0 else close.iloc[prev_i] <= top.iloc[prev_i]
            if crossed_now and prev_not_above:
                start_idx = i
                break

    start_ts = pd.to_datetime(df.iloc[start_idx]["Date"])
    end_ts = pd.to_datetime(df.iloc[-1]["Date"])
    months = ((end_ts - start_ts).days + 1) / 30.44

    _qdbg(f"qualifies ok: current_side={current_side}, run={run}, start={start_ts.strftime('%Y-%m-%d')}, end={end_ts.strftime('%Y-%m-%d')} (inside-cloud tolerated)")
    return ScanResult(
        ticker="",
        side=current_side,
        respect_days=run,
        close=float(close.iloc[-1]),
        start_date=start_ts.strftime("%Y-%m-%d"),
        respect_months=round(months, 1),
    )



def _country_code_from_ticker(symbol: str) -> str:
    sym = (symbol or "").strip().upper()
    if "." in sym:
        suffix = sym.split(".")[-1]
        return SUFFIX_TO_COUNTRY.get(suffix, "US")
    # Heuristic for Polish stocks frequently used without .WA suffix
    # in single-symbol mode (e.g., BNP). If symbol exists in WIG list,
    # treat as PL for liquidity/GDP threshold calculations.
    if sym in WIG_SEARCH_TICKERS:
        return "PL"
    return "US"


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




def _debug_symbol_target() -> str | None:
    raw = os.environ.get("STOCKHELPER_DEBUG_SYMBOL", "").strip().upper()
    return raw or None


def _debug_enabled_for(ticker: str) -> bool:
    target = _debug_symbol_target()
    return bool(target and ticker.upper() == target)


def _debug_log_scan(ticker: str, message: str) -> None:
    if _debug_enabled_for(ticker):
        print(f"[debug:{ticker.upper()}] {message}")



def _find_latest_breakout_idx(
    df: pd.DataFrame,
    current_side: str,
    min_age_days: int = 80,
    min_age_calendar_days: int = 120,
    debug_ticker: str | None = None,
) -> int | None:
    close = df["Close"]
    top = df["cloud_top"]
    bottom = df["cloud_bottom"]
    n = len(df)
    # WYNIKI 1 breakout day = earliest candle that closes on the other side
    # and then does NOT close back to the opposite side for at least 4 months.
    date_series = pd.to_datetime(df["Date"], errors="coerce")
    fallback_transition_idx: int | None = None
    # Search from newest to oldest: we need the LAST valid breakout candle.
    for i in range(n - 1, 0, -1):
        i_date = pd.to_datetime(df.iloc[i]["Date"]).strftime("%Y-%m-%d") if not pd.isna(date_series.iloc[i]) else "-"
        if (n - i) < min_age_days:
            if debug_ticker:
                _debug_log_scan(debug_ticker, f"breakout candidate {i_date} rejected: fewer than min_age_days bars ({n-i} < {min_age_days})")
            continue
        if pd.isna(date_series.iloc[i]):
            continue
        age_days = int((date_series.iloc[-1] - date_series.iloc[i]).days)
        if age_days < min_age_calendar_days:
            if debug_ticker:
                _debug_log_scan(debug_ticker, f"breakout candidate {i_date} rejected: age_days={age_days} < min_age_calendar_days={min_age_calendar_days}")
            continue

        end_idx = min(n, i + min_age_days)
        if current_side == "below":
            crossed = close.iloc[i] < bottom.iloc[i] and close.iloc[i - 1] >= bottom.iloc[i - 1]
            maintained = bool((close.iloc[i:end_idx] <= top.iloc[i:end_idx]).all())
            in_side_now = bool(close.iloc[i] <= top.iloc[i])
            prev_in_side = bool(close.iloc[i - 1] <= top.iloc[i - 1])
        else:
            crossed = close.iloc[i] > top.iloc[i] and close.iloc[i - 1] <= top.iloc[i - 1]
            maintained = bool((close.iloc[i:end_idx] >= bottom.iloc[i:end_idx]).all())
            in_side_now = bool(close.iloc[i] >= bottom.iloc[i])
            prev_in_side = bool(close.iloc[i - 1] >= bottom.iloc[i - 1])

        # Primary rule: true breakout candle crossing opposite side boundary.
        if crossed and maintained:
            if debug_ticker:
                _debug_log_scan(debug_ticker, f"breakout accepted at {i_date}: crossed and maintained for {min_age_days} bars")
            return i

        # Fallback only for transition into target side without strict boundary cross.
        # This avoids picking arbitrary in-trend candles deep inside an existing run.
        transitioned_into_side = in_side_now and (not prev_in_side)
        if fallback_transition_idx is None and transitioned_into_side and maintained:
            fallback_transition_idx = i
            if debug_ticker:
                _debug_log_scan(debug_ticker, f"fallback transition noted at {i_date}: entered target side and maintained for {min_age_days} bars")

        if debug_ticker and crossed and not maintained:
            fail_rel = (close.iloc[i:end_idx] > top.iloc[i:end_idx]) if current_side == "below" else (close.iloc[i:end_idx] < bottom.iloc[i:end_idx])
            bad = fail_rel[fail_rel].index
            if len(bad) > 0:
                k = int(bad[0])
                bad_date = pd.to_datetime(df.iloc[k]["Date"]).strftime("%Y-%m-%d")
                _debug_log_scan(debug_ticker, f"breakout candidate {i_date} rejected: opposite-side close at {bad_date}")

    if fallback_transition_idx is not None:
        if debug_ticker:
            d = pd.to_datetime(df.iloc[fallback_transition_idx]["Date"]).strftime("%Y-%m-%d")
            _debug_log_scan(debug_ticker, f"using fallback transition start at {d} (no strict cross found)")
        return fallback_transition_idx
    return None


def _retest_meta_for_side(df: pd.DataFrame, breakout_idx: int, current_side: str, allow_equal_third_close: bool = False) -> tuple[int, str, str]:
    _status, _depth, count, _first_date, events = _detect_ichimoku_retest(df, breakout_idx, current_side, allow_equal_third_close=allow_equal_third_close)
    if count > 0 and events:
        d, pattern, _ = events[-1]
        return count, d, pattern
    return 0, "-", "-"



def _load_full_cached_history_for_scan(symbol: str, instrument_type: str) -> tuple[pd.DataFrame, Path, dict]:
    """Refresh newest data first, then run calculations on full cached CSV history.

    Scanners must not perform older-history backfills implicitly. Older backfill
    requests are network-heavy, easy to rate-limit, and can stall a bounded scan
    worker queue. Use the explicit launcher command `python run --fetch-older-data`
    when older cache extension is needed.
    """
    # Auto cache-only mode is useful for avoiding full group refreshes, but it
    # must not prevent the scanner from merging the newest Yahoo candle for the
    # actual calculation.  Only the explicit --onlycache mode should skip this.
    old_auto_cache = os.environ.get("STOCKHELPER_CACHE_ONLY")
    user_onlycache = os.environ.get("STOCKHELPER_USER_ONLYCACHE") == "1"
    if old_auto_cache == "1" and not user_onlycache:
        os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
    try:
        _runtime_df, csv_path, meta = _load_daily_data_with_retries(
            symbol=symbol,
            instrument_type=instrument_type,
            persist=True,
            fetch_older_data=False,
        )
    finally:
        if old_auto_cache == "1" and not user_onlycache:
            os.environ["STOCKHELPER_CACHE_ONLY"] = old_auto_cache
    df = pd.read_csv(csv_path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return df, csv_path, meta

def _ichimoku_latest_pattern_still_active(df: pd.DataFrame, pattern_date: str | None, side: str, *, max_days: int = 3) -> bool:
    if not pattern_date or pattern_date == "-" or df is None or df.empty:
        return False
    try:
        pdate = pd.to_datetime(pattern_date).date()
    except Exception:
        return False
    dates = pd.to_datetime(df["Date"], errors="coerce")
    matches = df.loc[dates.dt.date == pdate]
    if matches.empty:
        return False
    latest = dates.dropna().max()
    if pd.isna(latest) or (latest.date() - pdate).days > max_days:
        return False
    pattern_row = matches.iloc[-1]
    after = df.loc[dates.dt.date > pdate]
    if after.empty:
        return True
    if side == "above":
        floor = float(pd.to_numeric(pd.Series([pattern_row.get("Low")]), errors="coerce").iloc[0])
        lows = pd.to_numeric(after["Low"], errors="coerce")
        return not bool((lows < floor).any())
    ceiling = float(pd.to_numeric(pd.Series([pattern_row.get("High")]), errors="coerce").iloc[0])
    highs = pd.to_numeric(after["High"], errors="coerce")
    return not bool((highs > ceiling).any())


def _ichimoku_pattern_status_label(status: str) -> str:
    low = (status or "").lower()
    if "inside" in low and "cloud" in low:
        return "Inside the cloud - PATTERN!"
    if "touch" in low and "cloud" in low:
        return "Touched the Cloud - PATTERN"
    return status

def _scan_one(ticker: str, group_name: str, exchange_suffix: str | None, current_datetime: datetime | None = None) -> tuple[str, ScanResult | None, FlipResult | None, str | None, str]:
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
    elif instrument == "stock" and "." not in fetch_symbol and len(fetch_symbol) <= 5:
        # Keep single Warsaw-stock scans aligned with the refresh probe and CSV
        # path logic. Without this, e.g. -allsearch xtb probes/refreshes XTB.WA
        # but the scan itself loads/persists XTB.csv, leaving XTB_WA.csv stale.
        fetch_symbol = f"{fetch_symbol}.WA"
    _debug_log_scan(ticker, f"instrument={instrument}, fetch_symbol={fetch_symbol}, group={group_name}")
    if instrument == "commodity":
        t_upper = ticker.upper()
        mapped = None if group_name == "indexes" or t_upper in API_METAL_COMMODITIES else COMMODITY_STOOQ_MAP.get(t_upper)
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
        df, _, meta = _load_full_cached_history_for_scan(symbol=fetch_symbol, instrument_type=instrument)
        source_label = str((meta or {}).get("source", "unknown")).lower()
        latest_candle_date = _latest_candle_date_from_df(df)
        expected_latest_session_date = get_expected_latest_session_date(
            instrument, group_name, current_datetime or datetime.now(UTC), fetch_symbol
        )
        enriched = _ichimoku(df)
        result = _qualifies(enriched, debug_ticker=ticker if _debug_enabled_for(ticker) else None)
        flip = _flip_after_long_respect(enriched, allow_equal_third_close=(instrument == "forex"))
        _debug_log_scan(ticker, f"result_side={(result.side if result else None)}, respect_days={(result.respect_days if result else 0)}, flip_side={(flip.current_side if flip else None)}, flip_status={(flip.retest_status if flip else None)}")
        stock_liquidity_ok = True
        if instrument == "stock" and (result or flip):
            metrics = _compute_stock_liquidity_metrics(df, fetch_symbol)
            if metrics is None:
                return display_symbol, None, None, "insufficient turnover data", source_label
            avg_10d, below_20d, threshold_10d, threshold_20d = metrics
            stock_liquidity_ok = avg_10d >= threshold_10d and below_20d <= 2
            _debug_log_scan(ticker, f"liquidity avg10={avg_10d:.0f} threshold10={threshold_10d:.0f} below20d={below_20d} threshold20={threshold_20d:.0f} ok={stock_liquidity_ok}")
        if result:
            result.ticker = ticker
            bidx = _find_latest_breakout_idx(enriched, result.side, debug_ticker=ticker if _debug_enabled_for(ticker) else None)
            if bidx is not None:
                result.start_date = pd.to_datetime(enriched.iloc[bidx]["Date"]).strftime("%Y-%m-%d")
                rc, rd, rp = _retest_meta_for_side(enriched, bidx, result.side, allow_equal_third_close=(instrument == "forex"))
                result.retest_count = rc
                result.latest_retest_date = rd
                result.latest_retest_pattern = rp
            else:
                result.retest_count = 0
                result.latest_retest_date = "-"
                result.latest_retest_pattern = "-"
            result.ichimoku_status = _ichimoku_status(enriched, result.side)
            active_latest_pattern = bool(result.latest_retest_pattern and result.latest_retest_pattern != "-") and _ichimoku_latest_pattern_still_active(enriched, result.latest_retest_date, result.side)
            metric_context = result.ichimoku_status or ""
            if active_latest_pattern:
                metric_context = f"{metric_context} retest_pattern"
                result.ichimoku_status = _ichimoku_pattern_status_label(result.ichimoku_status or "")
            _apply_ichimoku_extra_metrics(result, _ichimoku_extra_metrics(enriched, result.side, metric_context))
            result.latest_candle_date = latest_candle_date
            result.expected_latest_session_date = expected_latest_session_date
            if instrument == "stock":
                result.avg_turnover_10d_pln = avg_10d
                result.low_turnover_days_20d = below_20d
                result.liquidity_threshold_10d_pln = threshold_10d
                result.liquidity_threshold_20d_pln = threshold_20d
                if not stock_liquidity_ok:
                    _debug_log_scan(ticker, "excluded from WYNIKI 1 by liquidity filter")
                    return display_symbol, None, None, (
                        f"liquidity filter failed (avg10={avg_10d:.0f} < {threshold_10d:.0f} or below20d={below_20d} > 2)"
                    ), source_label
        if flip:
            if instrument == "stock" and not stock_liquidity_ok:
                return display_symbol, result, None, (
                    f"liquidity filter failed (avg10={avg_10d:.0f} < {threshold_10d:.0f} or below20d={below_20d} > 2)"
                ), source_label
            flip.ticker = ticker
            flip.ichimoku_status = _ichimoku_status(enriched, flip.current_side)
            _apply_ichimoku_extra_metrics(flip, _ichimoku_extra_metrics(enriched, flip.current_side, flip.retest_status or ""))
            flip.latest_candle_date = latest_candle_date
            flip.expected_latest_session_date = expected_latest_session_date
            if instrument == "stock":
                flip.avg_turnover_10d_pln = avg_10d
        _debug_log_scan(ticker, f"final include_result={bool(result)} include_flip={bool(flip)} source={source_label}")
        return display_symbol, result, flip, None, source_label
    except Exception as exc:
        return display_symbol, None, None, str(exc), "unknown"




def _ensure_flip_ticker(flip: FlipResult | None, fallback_ticker: str) -> FlipResult | None:
    if flip is None:
        return None
    if not getattr(flip, "ticker", ""):
        flip.ticker = fallback_ticker
    return flip
def _rate_limit_detected(err: str | None) -> bool:
    text = (err or "").lower()
    retryable_markers = (
        "rate limit",
        "captcha",
        "przekroczony dzienny limit",
        "too many requests",
        "http error 429",
        "connection reset by peer",
        "timed out",
        "temporarily unavailable",
        "service unavailable",
    )
    return any(marker in text for marker in retryable_markers)




def _should_prompt_rate_limit(group_name: str) -> bool:
    return (group_name or "").lower() not in {"commodities", "forex"}


def _prompt_vpn_continue_or_stop() -> bool:
    with PROMPT_LOCK:
        if not PAUSE_SCAN_EVENT.is_set():
            return not STOP_SCAN_EVENT.is_set()
        print("[search] Network/rate-limit issue detected. Pausing scan for VPN change.", flush=True)
        try:
            answer = input(
                "[search] Network/rate-limit issue detected (e.g. captcha/rate-limit/429). "
                "Change VPN/solve captcha, then press Enter to continue (type q to stop): "
            ).strip().lower()
        except EOFError:
            answer = "q"
        if answer in {"q", "quit", "stop", "n", "no"}:
            STOP_SCAN_EVENT.set()
            PAUSE_SCAN_EVENT.clear()
            return False
        STOP_SCAN_EVENT.clear()
        PAUSE_SCAN_EVENT.clear()
        return True



def _scan_one_with_retry_on_rate_limit(ticker: str, group_name: str, exchange_suffix: str | None, current_datetime: datetime | None = None, *, allow_prompt: bool = True):
    while True:
        if STOP_SCAN_EVENT.is_set() or not _wait_if_scan_paused():
            return ticker, None, None, "scan stopped", "unknown", True
        display_symbol, result, flip, err, src = _scan_one(ticker, group_name, exchange_suffix, current_datetime)
        if err and _rate_limit_detected(err):
            if not _should_prompt_rate_limit(group_name):
                PAUSE_SCAN_EVENT.clear()
                return display_symbol, result, flip, err, src, False
            PAUSE_SCAN_EVENT.set()
            if not allow_prompt:
                return display_symbol, result, flip, err, src, False
            if _prompt_vpn_continue_or_stop():
                print("[search] Retrying same instrument after VPN change...", flush=True)
                continue
            print("[search] Scan stopped by user after rate-limit detection.", flush=True)
            return display_symbol, result, flip, err, src, True
        return display_symbol, result, flip, err, src, False

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


def _forex_source_summary_label(src: str) -> str:
    """Collapse loader metadata into the three user-facing forex fetch paths."""
    source = (src or "").strip().lower()
    if source.startswith("stooq_web_csv"):
        return "downloaded_csv"
    if source.startswith("stooq_web"):
        return "table_ui"
    if source == "cache":
        return "cache"
    return source or "unknown"


def _print_forex_source_summary(prefix: str, members: Sequence[str], sources: dict[str, str]) -> None:
    counts: dict[str, int] = {}
    for ticker in members:
        label = _forex_source_summary_label(sources.get(ticker, "unknown"))
        counts[label] = counts.get(label, 0) + 1
        print(f"[{prefix}-source] {ticker}: {label}")
    summary = ", ".join(f"{source}={count}" for source, count in sorted(counts.items()))
    print(f"[{prefix}-source] summary: {summary}")




def _build_chart_command(ticker: str, mode: str, anchor_start: str = "", anchor_end: str = "", wedge: WedgeScanResult | None = None) -> str:
    t = (ticker or "").strip()
    if "." not in t and len(t) <= 5:
        cfg_stocks = PROJECT_ROOT / "configs" / "stocks"
        stock_csv = CSV_DATA_DIR / "stocks" / f"{t.upper()}_WA.csv"
        if (cfg_stocks / f"{t}.py").exists() or stock_csv.exists() or t.upper() in WIG_SEARCH_TICKERS:
            t = f"{t}.WA"
    base = f"python run -c {t}"
    if mode == "fibo":
        start = anchor_start or "YYYY-MM-DD"
        end = anchor_end or "YYYY-MM-DD"
        return f"{base} --fibo-lines 5 --fibo-anchor-start {start} --fibo-anchor-end {end} --fibo-right"
    if mode == "wedge" and wedge is not None:
        return (
            f"{base} --wedge-lines "
            f"--wedge-upper-start {wedge.upper_start_date},{wedge.upper_start_price} "
            f"--wedge-upper-end {wedge.upper_end_date},{wedge.upper_end_price} "
            f"--wedge-lower-start {wedge.lower_start_date},{wedge.lower_start_price} "
            f"--wedge-lower-end {wedge.lower_end_date},{wedge.lower_end_price} "
            f"--wedge-right"
        )
    return base + " --ichimoku-mode on"


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _write_md_table(
    path: Path,
    title: str,
    headers: list[str],
    rows: list[list[str]],
    append: bool = False,
    description: str | None = None,
) -> None:
    link_col = headers.index("Link") if "Link" in headers else None
    with path.open("a" if append else "w", encoding="utf-8") as fh:
        fh.write(f"## {title}\n\n")
        if description:
            fh.write(description.strip() + "\n\n")
        fh.write("| " + " | ".join(headers) + " |\n")
        fh.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
        for row in rows:
            safe: list[str] = []
            for col_idx, cell in enumerate(row):
                cell_txt = str(cell).replace("\n", " ")
                if link_col is not None and col_idx == link_col and _is_http_url(cell_txt):
                    cell_txt = f"[📈]({cell_txt})"
                safe.append(cell_txt.replace("|", "\\|"))
            fh.write("| " + " | ".join(safe) + " |\n")


def _daily_report_path(prefix: str, group_name: str) -> Path:
    day = datetime.now(UTC).strftime("%Y%m%d")
    return _search_output_dir(prefix) / f"{prefix}_{group_name.lower()}_{day}.md"
def _prune_search_history(group_name: str, keep_last: int = 3) -> None:
    base = f"search_{group_name.lower()}_"
    files = [p for p in ICHIMOKU_SEARCH_OUTPUT_DIR.glob(f"{base}*.md") if p.is_file()]
    if len(files) <= keep_last:
        return
    files_sorted = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files_sorted[keep_last:]:
        try:
            old.unlink()
        except Exception:
            pass



def _fmt_metric_or_dash(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text else "-"


def _ichimoku_extra_metrics(df: pd.DataFrame, side: str, context_status: str = "") -> dict[str, str]:
    """Calculate compact Ichimoku fields once during the scanner run.

    Trójpolówki and allsearch reports should only reuse these persisted values;
    they must not rescan instruments later.
    """
    missing = {
        "ichimoku_risk": "-",
        "tk_cross": "-",
        "breakout_dynamic": "-",
        "cloud_thickness": "-",
        "chikou_confirmation": "-",
        "kumo_twist": "-",
        "tk_plus": "-",
        "tenkan_in_cloud": "-",
    }
    required = {"Close", "High", "Low", "Open", "tenkan", "kijun", "cloud_top", "cloud_bottom"}
    if df is None or df.empty or not required.issubset(set(df.columns)):
        return missing
    try:
        c = df.iloc[-1]
        side_n = (side or "").strip().lower()
        is_short = side_n == "below"
        close = float(c["Close"])
        cloud_top = float(c["cloud_top"])
        cloud_bottom = float(c["cloud_bottom"])
        thickness = max(cloud_top - cloud_bottom, 1e-9)
        thickness_pct = thickness / max(abs(close), 1e-9)
        if thickness_pct < 0.025:
            cloud_thickness = "shallow"
        elif thickness_pct > 0.06:
            cloud_thickness = "thick"
        else:
            cloud_thickness = "normal"

        def _tk_cross_at(pos: int) -> str | None:
            if pos <= 0 or pos >= len(df):
                return None
            prev_delta = float(df["tenkan"].iloc[pos - 1] - df["kijun"].iloc[pos - 1])
            cur_delta = float(df["tenkan"].iloc[pos] - df["kijun"].iloc[pos])
            if prev_delta <= 0 < cur_delta:
                return "bullish TK cross"
            if prev_delta >= 0 > cur_delta:
                return "bearish TK cross"
            return None

        def _recent_tk_cross_around_cloud_entry(lookback: int = 22) -> str | None:
            intersects_cloud = (df["High"] >= df["cloud_bottom"]) & (df["Low"] <= df["cloud_top"])
            if not bool(intersects_cloud.iloc[-1]):
                return None
            entry_pos = len(df) - 1
            while entry_pos > 0 and bool(intersects_cloud.iloc[entry_pos - 1]):
                entry_pos -= 1
            start_pos = max(1, entry_pos - lookback)
            for pos in range(len(df) - 1, start_pos - 1, -1):
                cross = _tk_cross_at(pos)
                if cross:
                    return cross
            return None

        def _current_tk_alignment() -> str:
            cur_delta = float(c["tenkan"] - c["kijun"])
            if cur_delta > 0:
                return "bullish TK cross"
            if cur_delta < 0:
                return "bearish TK cross"
            return "neutral TK cross"

        if len(df) >= 2:
            # Prefer an actual fresh cross near the current cloud interaction,
            # but never report "no cross" when the latest Tenkan/Kijun
            # relationship is visible on the chart. 3P needs the newest
            # actionable TK direction when no fresh crossing event is found.
            tk_cross = _recent_tk_cross_around_cloud_entry() or _tk_cross_at(len(df) - 1) or _current_tk_alignment()
        else:
            tk_cross = _current_tk_alignment()

        if len(df) >= 52 and pd.notna(c.get("tenkan")) and pd.notna(c.get("kijun")):
            # Kumo twist should describe the leading cloud projected to the
            # right of the current candle, not the shifted cloud under price.
            # The shifted span_a/span_b columns are used for current support/
            # resistance; here we recompute the unshifted leading spans so a
            # newly appearing red/green future kumo is visible in reports.
            leading_span_a = (float(c["tenkan"]) + float(c["kijun"])) / 2.0
            high52 = pd.to_numeric(df["High"].tail(52), errors="coerce")
            low52 = pd.to_numeric(df["Low"].tail(52), errors="coerce")
            if high52.notna().any() and low52.notna().any():
                leading_span_b = (float(high52.max()) + float(low52.min())) / 2.0
                diff = leading_span_a - leading_span_b
                kumo_twist = "green" if diff > 0 else ("red" if diff < 0 else "neutral")
            else:
                kumo_twist = "-"
        else:
            kumo_twist = "-"

        tk_plus = "yes" if ((not is_short and float(c["tenkan"]) > float(c["kijun"])) or (is_short and float(c["tenkan"]) < float(c["kijun"]))) else "no"
        tenkan = float(c["tenkan"])
        tenkan_in_cloud = "yes" if cloud_bottom <= tenkan <= cloud_top else "no"

        chikou_is_confirming = False
        if len(df) > 26:
            past_close = float(df["Close"].iloc[-27])
            if close > past_close:
                chikou_confirmation = "↑ over"
                chikou_is_confirming = not is_short
            elif close < past_close:
                chikou_confirmation = "↓ under"
                chikou_is_confirming = is_short
            else:
                chikou_confirmation = "↔ equal"
        else:
            chikou_confirmation = "-"

        recent = pd.to_numeric(df["Close"].tail(6), errors="coerce").dropna()
        if len(recent) >= 2:
            move = abs(float(recent.iloc[-1]) - float(recent.iloc[0]))
            units = move / thickness
            if units >= 2.0:
                breakout_dynamic = "aggressive"
            elif units >= 1.0:
                breakout_dynamic = "high"
            elif units >= 0.35:
                breakout_dynamic = "mild"
            else:
                breakout_dynamic = "slow"
        else:
            breakout_dynamic = "-"

        context = (context_status or "").lower()
        risk_context = any(
            token in context
            for token in (
                "breakout_confirmed",
                "breakout confirmed",
                "retest_breakout",
                "retest breakout",
                "retest_pattern",
                "retest pattern",
            )
        )
        pattern_context = "retest_pattern" in context or "retest pattern" in context
        risk_text = "-"
        if risk_context:
            risk = 0
            if pattern_context:
                risk += 1
            if chikou_is_confirming:
                risk += 1
            if (not is_short and kumo_twist == "green") or (is_short and kumo_twist == "red"):
                risk += 1
            correct_cloud_side = close > cloud_top if not is_short else close < cloud_bottom
            if correct_cloud_side:
                risk += 1
            risk_text = f"{min(risk, 3)}%"

        return {
            "ichimoku_risk": risk_text,
            "tk_cross": tk_cross,
            "breakout_dynamic": breakout_dynamic,
            "cloud_thickness": cloud_thickness,
            "chikou_confirmation": chikou_confirmation,
            "kumo_twist": kumo_twist,
            "tk_plus": tk_plus,
            "tenkan_in_cloud": tenkan_in_cloud,
        }
    except Exception:
        return missing


def _apply_ichimoku_extra_metrics(row: ScanResult | FlipResult, metrics: dict[str, str]) -> None:
    row.ichimoku_risk = _fmt_metric_or_dash(metrics.get("ichimoku_risk"))
    row.tk_cross = _fmt_metric_or_dash(metrics.get("tk_cross"))
    row.breakout_dynamic = _fmt_metric_or_dash(metrics.get("breakout_dynamic"))
    row.cloud_thickness = _fmt_metric_or_dash(metrics.get("cloud_thickness"))
    row.chikou_confirmation = _fmt_metric_or_dash(metrics.get("chikou_confirmation"))
    row.kumo_twist = _fmt_metric_or_dash(metrics.get("kumo_twist"))
    row.tk_plus = _fmt_metric_or_dash(metrics.get("tk_plus"))
    row.tenkan_in_cloud = _fmt_metric_or_dash(metrics.get("tenkan_in_cloud"))


def _ichimoku_status(df: pd.DataFrame, side: str) -> str:
    if df.empty:
        return "-"
    c = df.iloc[-1]
    close = float(c["Close"])
    open_ = float(c["Open"])
    high = float(c["High"])
    low = float(c["Low"])
    top = float(c["cloud_top"])
    bottom = float(c["cloud_bottom"])
    kijun = float(c["kijun"])

    inside_cloud = bottom <= close <= top
    if inside_cloud:
        # A single wick through the far cloud boundary is not enough to call the
        # breakout unsuccessful; only a body-side failure should receive that label.
        if side == "above":
            broke_other_side_by_body = open_ < bottom and close < bottom
        else:
            broke_other_side_by_body = open_ > top and close > top
        if broke_other_side_by_body:
            return "Unsuccessful breakout to the other side"
        return "Inside the cloud"

    touched_cloud = high >= bottom and low <= top
    if touched_cloud:
        return "Touched the cloud"

    touched_kijun = low <= kijun <= high
    if touched_kijun:
        return "Touched Kijun-sen"
    if side == "above":
        return "Over Kijun-sen" if low > kijun else "Under Kijun-sen"
    return "Under Kijun-sen" if high < kijun else "Over Kijun-sen"


def _flip_still_actionable(row: FlipResult) -> bool:
    # Keep every detected cloud-side flip in the scanner output.  The previous
    # short-flip filter removed clean continuation breakouts as soon as price was
    # also on the correct side of Kijun-sen, which hid fresh/valid formations
    # such as OPL.WA from every report table.  Ranking/top-choice logic can
    # decide importance, but the raw scanner result should stay findable.
    return True


def _print_results_with_links(results: list[ScanResult], retest_by_ticker_side: dict[tuple[str, str], str] | None = None) -> list[str]:
    print(f"\n{ANSI_BOLD}{ANSI_GREEN}WYNIKI (instrumenty spełniające warunki):{ANSI_RESET}")
    if not results:
        print("Brak wyników.")
        return []
    print(f"{'Ticker':<10} {'Pozycja':<8} {'Świece':<8} {'Mies.':<6} {'Start':<12} {'Close':>10} {'Avg10d PLN':>14} {'Ichimoku status':<52} {'Retest count':<13} {'Latest Retest date':<18} {'Latest Retest pattern':<22} {'Link':<0}")
    print("-" * 230)
    sorted_rows = sorted(results, key=lambda r: r.respect_days, reverse=True)
    links: list[str] = []
    for row in sorted_rows:
        avg_10d = f"{row.avg_turnover_10d_pln:,.0f}" if row.avg_turnover_10d_pln is not None else "-"
        link = _stooq_chart_url(row.ticker)
        links.append(link)
        retest_count = "-"
        retest_date = "-"
        retest_pattern = "-"
        if retest_by_ticker_side is not None:
            retest_count = str(row.retest_count if row.retest_count is not None else "-")
            retest_date = row.latest_retest_date if row.latest_retest_date else "-"
            retest_pattern = row.latest_retest_pattern if row.latest_retest_pattern else "-"
        print(f"{row.ticker:<10} {row.side:<8} {row.respect_days:<8} {row.respect_months:<6.1f} {row.start_date:<12} {row.close:>10.4f} {avg_10d:>14} {((row.ichimoku_status or "-")[:52]):<52} {retest_count:<13} {retest_date:<18} {retest_pattern:<22} {ANSI_CYAN}{link}{ANSI_RESET}")
    return links

def run_checkavg(target: str) -> int:
    ticker = (target or "").strip()
    if not ticker:
        print("Usage: python run -checkavg <instrument>")
        return 2

    detected = detect_instrument_type(ticker, None)
    instrument = "commodity" if detected == "commodity" else ("forex" if detected == "forex" else "stock")
    fetch_symbol = ticker
    if instrument == "commodity":
        mapped = COMMODITY_STOOQ_MAP.get(ticker.upper())
        if mapped:
            fetch_symbol = str(mapped).upper()
    elif instrument == "stock":
        if "." not in fetch_symbol and len(fetch_symbol) <= 5:
            fetch_symbol = f"{fetch_symbol}.WA"

    try:
        df, _, meta = _load_full_cached_history_for_scan(symbol=fetch_symbol, instrument_type=instrument)
    except Exception as exc:
        print(f"[checkavg] failed to load data for {ticker}: {exc}")
        return 1

    source = str((meta or {}).get("source", "unknown")).lower()
    if source != "stooq":
        print(f"[checkavg] expected stooq source, got: {source}")
        return 1

    if "Close" not in df.columns or "Volume" not in df.columns:
        print(f"[checkavg] missing Close/Volume for {ticker}")
        return 1

    turnover_pln = pd.to_numeric(df["Close"], errors="coerce") * pd.to_numeric(df["Volume"], errors="coerce")
    turnover_pln = turnover_pln.dropna()
    if len(turnover_pln) < 10:
        print(f"[checkavg] insufficient turnover data for {ticker} (need >= 10 bars)")
        return 1

    avg_10d_pln = float(turnover_pln.tail(10).mean())
    print(f"[checkavg] instrument={instrument} ticker={ticker} fetch_symbol={fetch_symbol} source={source}")
    print(f"[checkavg] Avg10d PLN: {avg_10d_pln:,.0f}")
    print(f"[checkavg] 1% max capital: {avg_10d_pln * 0.01:,.2f} PLN")
    return 0


def _print_flip_results_with_links(flip_results: list[FlipResult]) -> list[str]:
    print(f"\n{ANSI_BOLD}{ANSI_YELLOW}WYNIKI 2 (po >=4 mies. po jednej stronie, potem wybicie i utrzymanie po drugiej):{ANSI_RESET}")
    if not flip_results:
        print("Brak wyników.")
        return []
    max_events = max((len(r.retest_events or []) for r in flip_results), default=0)
    base_header = f"{'Ticker':<10} {'Było':<8} {'Jest':<8} {'Data wybicia':<12} {'Mies. od wybicia':<16} {'Mies. respektu':<14} {'Latest Retest status':<36} {'Retest count':<12} {'Avg10d PLN':>14}"
    event_headers = " ".join([f"{f'Retest #{i} (date pattern)':<34}" for i in range(1, max_events + 1)])
    print(f"{base_header} {event_headers} {'Link':<0}".rstrip())
    print("-" * 150)
    links: list[str] = []
    for row in sorted(flip_results, key=lambda r: r.months_since_flip, reverse=True):
        link = _stooq_chart_url(row.ticker)
        links.append(link)
        events = row.retest_events or []
        event_cells = []
        for idx in range(max_events):
            if idx < len(events):
                event_cells.append(f"{events[idx][0]} {events[idx][1]}")
            else:
                event_cells.append("-")
        event_cols = " ".join([f"{cell:<34}" for cell in event_cells])
        avg10_txt = f"{row.avg_turnover_10d_pln:,.0f}" if row.avg_turnover_10d_pln is not None else "-"
        prev_respect_txt = f"{row.previous_respect_months:.1f}" if row.previous_respect_months is not None else "-"
        print(f"{row.ticker:<10} {row.previous_side:<8} {row.current_side:<8} {row.flip_date:<12} {row.months_since_flip:<16.1f} {prev_respect_txt:<14} {row.retest_status:<36} {row.valid_retests_count:<12} {avg10_txt:>14} {event_cols} {ANSI_CYAN}{link}{ANSI_RESET}".rstrip())
    return links


def _flip_after_long_respect(df: pd.DataFrame, min_days: int = 80, allow_equal_third_close: bool = False) -> FlipResult | None:
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
    previous_respect_run = 0

    # Allow a multi-week cloud transition before the final close on the other
    # side.  OPL.WA-style setups can spend longer than 15 sessions inside/near
    # the cloud after many months of respect before printing the actual breakout.
    max_transition_days = 35

    # Prefer latest valid flip below->above.
    for i in range(len(df) - 1, 0, -1):
        crossed_up = body_low.iloc[i] > top.iloc[i] and body_low.iloc[i - 1] <= top.iloc[i - 1]
        if not crossed_up:
            continue
        if not bool(above_respected.iloc[i:].all()):
            continue
        prev_run = 0
        j = i - 1
        transition = 0
        while j >= 0 and not bool(below_respected.iloc[j]) and float(body_low.iloc[j]) <= float(top.iloc[j]) and transition < max_transition_days:
            transition += 1
            j -= 1
        while j >= 0 and bool(below_respected.iloc[j]):
            prev_run += 1
            j -= 1
        if prev_run >= min_days:
            flip_idx = i
            previous_side = "below"
            current_side = "above"
            previous_respect_run = prev_run
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
            transition = 0
            while j >= 0 and not bool(above_respected.iloc[j]) and float(body_high.iloc[j]) >= float(bottom.iloc[j]) and transition < max_transition_days:
                transition += 1
                j -= 1
            while j >= 0 and bool(above_respected.iloc[j]):
                prev_run += 1
                j -= 1
            if prev_run >= min_days:
                flip_idx = i
                previous_side = "above"
                current_side = "below"
                previous_respect_run = prev_run
                break

    if flip_idx is None or previous_side is None or current_side is None:
        return None

    flip_ts = pd.to_datetime(df.iloc[flip_idx]["Date"])
    end_ts = pd.to_datetime(df.iloc[-1]["Date"])
    months = ((end_ts - flip_ts).days + 1) / 30.44

    previous_respect_start_idx = max(0, flip_idx - previous_respect_run)
    previous_respect_start_ts = pd.to_datetime(df.iloc[previous_respect_start_idx]["Date"])
    previous_respect_months = max(0.0, (flip_ts - previous_respect_start_ts).days / 30.44)

    flip = FlipResult("", previous_side, current_side, flip_ts.strftime("%Y-%m-%d"), round(months, 1), float(close.iloc[-1]))
    flip.previous_respect_months = round(previous_respect_months, 1)
    (
        flip.retest_status,
        flip.retest_depth,
        flip.valid_retests_count,
        flip.first_valid_retest_pattern_date,
        flip.retest_events,
    ) = _detect_ichimoku_retest(df, flip_idx, current_side, allow_equal_third_close=allow_equal_third_close)
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


def _detect_ichimoku_retest(df: pd.DataFrame, flip_idx: int, current_side: str, allow_equal_third_close: bool = False) -> tuple[str, str, int, str, list[tuple[str, str, str]]]:
    def _breakout_status_for_age() -> str:
        try:
            flip_date = pd.to_datetime(df.iloc[flip_idx]["Date"]).date()
            latest_date = pd.to_datetime(df.iloc[-1]["Date"]).date()
            return "breakout_confirmed" if 0 <= (latest_date - flip_date).days <= 5 else "no_breakout"
        except Exception:
            return "breakout_confirmed"

    body_high = df[["Open", "Close"]].max(axis=1)
    body_low = df[["Open", "Close"]].min(axis=1)
    top = df["cloud_top"]
    bottom = df["cloud_bottom"]
    post = range(flip_idx + 1, len(df))
    if flip_idx <= 0 or (flip_idx + 1) >= len(df):
        return _breakout_status_for_age(), "-", 0, "-", []

    waiting = False
    touch_idxs: list[int] = []
    for i in post:
        if current_side == "above":
            # Retests may enter cloud; invalidate only when close breaks to opposite side.
            if float(df["Close"].iloc[i]) < float(bottom.iloc[i]):
                return "invalidated_by_close_on_opposite_side", "-", 0, "-", []
            touched = float(df["Low"].iloc[i]) <= float(top.iloc[i])
        else:
            # Retests may enter cloud; invalidate only when close breaks to opposite side.
            if float(df["Close"].iloc[i]) > float(top.iloc[i]):
                return "invalidated_by_close_on_opposite_side", "-", 0, "-", []
            touched = float(df["High"].iloc[i]) >= float(bottom.iloc[i])
        if touched:
            waiting = True
            touch_idxs.append(i)

    if not waiting:
        return _breakout_status_for_age(), "-", 0, "-", []

    first_valid_date = "-"
    first_valid_status = "-"
    first_valid_depth = "-"
    valid_count = 0
    found_too_late = False
    events: list[tuple[str, str, str]] = []
    last_pattern_abs: int | None = None
    i = flip_idx + 1
    while i < len(df):
        if current_side == "above":
            touched = float(df["Low"].iloc[i]) <= float(top.iloc[i])
            outside = body_low.iloc[i] > top.iloc[i]
        else:
            touched = float(df["High"].iloc[i]) >= float(bottom.iloc[i])
            outside = body_high.iloc[i] < bottom.iloc[i]

        if not touched:
            i += 1
            continue

        cycle_start = i
        cycle_end = i
        while cycle_end + 1 < len(df):
            n = cycle_end + 1
            if current_side == "above":
                n_touched = float(df["Low"].iloc[n]) <= float(top.iloc[n])
                n_outside = body_low.iloc[n] > top.iloc[n]
            else:
                n_touched = float(df["High"].iloc[n]) >= float(bottom.iloc[n])
                n_outside = body_high.iloc[n] < bottom.iloc[n]
            if n_touched:
                cycle_end = n
                continue
            if n_outside:
                break
            cycle_end = n

        w_start = max(cycle_start - 2, flip_idx + 1)
        # Include the first candle that leaves the cloud after a retest cycle.
        # Bearish/bullish harami confirmation often prints on that outside candle.
        detect_until = min(cycle_end + 1, len(df) - 1)
        w = df.iloc[w_start: detect_until + 1].reset_index(drop=True)
        if len(w) >= 2:
            pattern_candidates: list[tuple[int, str]] = []
            if current_side == "above":
                for j in range(0, len(w)):
                    if _is_bullish_hammer(w.iloc[j]):
                        pattern_candidates.append((j, "hammer"))
                for j in range(1, len(w)):
                    lvl = float(w["cloud_top"].iloc[j])
                    floor = float(w["cloud_bottom"].iloc[j])
                    if _is_bullish_engulfing(
                        w.iloc[j - 1],
                        w.iloc[j],
                        lvl,
                        close_floor=floor,
                        zone_floor=floor,
                    ):
                        pattern_candidates.append((j, "bullish_engulfing"))
                    if _is_bullish_harami(w.iloc[j - 1], w.iloc[j], lvl):
                        pattern_candidates.append((j, "bullish_harami"))
                    if _is_bullish_piercing_line(w.iloc[j - 1], w.iloc[j], lvl):
                        pattern_candidates.append((j, "bullish_piercing_line"))
                for j in range(2, len(w)):
                    lvl = float(w["cloud_top"].iloc[j])
                    if _is_morning_star(w.iloc[j - 2], w.iloc[j - 1], w.iloc[j], lvl, doji_middle=False, allow_equal_third_close=allow_equal_third_close):
                        pattern_candidates.append((j, "morning_star"))
                    if _is_morning_star(w.iloc[j - 2], w.iloc[j - 1], w.iloc[j], lvl, doji_middle=True, allow_equal_third_close=allow_equal_third_close):
                        pattern_candidates.append((j, "morning_doji_star"))
            else:
                for j in range(0, len(w)):
                    if _is_bearish_shooting_star(w.iloc[j]):
                        pattern_candidates.append((j, "shooting_star"))
                    # Accept bearish hammer-shaped rejection (same geometry as shooting star)
                    # under explicit "hammer" naming used by some users.
                    if _is_bearish_shooting_star(w.iloc[j]):
                        pattern_candidates.append((j, "bearish_hammer"))
                for j in range(1, len(w)):
                    lvl = float(w["cloud_bottom"].iloc[j])
                    ceiling = float(w["cloud_top"].iloc[j])
                    if _is_bearish_engulfing(
                        w.iloc[j - 1],
                        w.iloc[j],
                        lvl,
                        close_ceiling=ceiling,
                        zone_ceiling=ceiling,
                    ):
                        pattern_candidates.append((j, "bearish_engulfing"))
                    if _is_bearish_harami(w.iloc[j - 1], w.iloc[j], lvl):
                        pattern_candidates.append((j, "bearish_harami"))
                    if _is_dark_cloud_cover(w.iloc[j - 1], w.iloc[j], lvl):
                        pattern_candidates.append((j, "dark_cloud_cover"))
                for j in range(2, len(w)):
                    lvl = float(w["cloud_bottom"].iloc[j])
                    if _is_evening_star(w.iloc[j - 2], w.iloc[j - 1], w.iloc[j], lvl, doji_middle=False, allow_equal_third_close=allow_equal_third_close):
                        pattern_candidates.append((j, "evening_star"))
                    if _is_evening_star(w.iloc[j - 2], w.iloc[j - 1], w.iloc[j], lvl, doji_middle=True, allow_equal_third_close=allow_equal_third_close):
                        pattern_candidates.append((j, "evening_doji_star"))
            # Prefer stronger multi-candle formations over partial-overlap and 1-candle
            # signals when more than one pattern ends on the same retest candle.
            formation_priority = {
                "bullish_engulfing": 0,
                "bearish_engulfing": 0,
                "morning_star": 1,
                "morning_doji_star": 1,
                "evening_star": 1,
                "evening_doji_star": 1,
                "bullish_piercing_line": 2,
                "dark_cloud_cover": 2,
                "bullish_harami": 3,
                "bearish_harami": 3,
                "hammer": 4,
                "shooting_star": 4,
                "bearish_hammer": 4,
            }
            ordered_candidates = sorted(
                set(pattern_candidates),
                key=lambda x: (x[0], formation_priority.get(x[1], 99)),
            )
            for pattern_idx, formation in ordered_candidates:
                pattern_abs = w_start + pattern_idx
                local_reaction_abs = int(df["Low"].iloc[cycle_start:pattern_abs + 1].idxmin()) if current_side == "above" else int(df["High"].iloc[cycle_start:pattern_abs + 1].idxmax())
                if pattern_abs - local_reaction_abs >= 2:
                    found_too_late = True
                    continue
                probe = float(df["Low"].iloc[pattern_abs]) if current_side == "above" else float(df["High"].iloc[pattern_abs])
                depth = _classify_retest_depth(float(top.iloc[pattern_abs]), float(bottom.iloc[pattern_abs]), probe, current_side)
                # shallow if only shadow pierces/touches cloud or very slight entry
                body_lo = min(float(df["Open"].iloc[pattern_abs]), float(df["Close"].iloc[pattern_abs]))
                body_hi = max(float(df["Open"].iloc[pattern_abs]), float(df["Close"].iloc[pattern_abs]))
                if (current_side == "above" and body_lo >= float(top.iloc[pattern_abs])) or (current_side == "below" and body_hi <= float(bottom.iloc[pattern_abs])):
                    depth = "shallow"
                valid_count += 1
                ev_date = pd.to_datetime(df.iloc[pattern_abs]["Date"]).strftime("%Y-%m-%d")
                events.append((ev_date, formation, depth))
                last_pattern_abs = pattern_abs
                if first_valid_date == "-":
                    first_valid_date = ev_date
                    first_valid_depth = depth
                    first_valid_status = f"{depth}_retest_pattern"
                break
        i = cycle_end + 1

    if valid_count > 0:
        # If after a valid retest pattern price returned to cloud and then broke
        # the last pattern candle extreme in the opposite direction, downgrade
        # current state back to waiting_for_pattern.
        if last_pattern_abs is not None and last_pattern_abs + 1 < len(df):
            if current_side == "above":
                last_pattern_floor = float(df["Low"].iloc[last_pattern_abs])
                returned_to_cloud = False
                for k in range(last_pattern_abs + 1, len(df)):
                    if float(df["Low"].iloc[k]) <= float(top.iloc[k]):
                        returned_to_cloud = True
                    if returned_to_cloud and float(df["Close"].iloc[k]) < last_pattern_floor:
                        latest_idx = len(df) - 1
                        if body_low.iloc[latest_idx] > top.iloc[latest_idx]:
                            return _breakout_status_for_age(), "-", valid_count, first_valid_date, events
                        return "returned_to_cloud_waiting_for_pattern", "-", valid_count, first_valid_date, events
            else:
                last_pattern_ceiling = float(df["High"].iloc[last_pattern_abs])
                returned_to_cloud = False
                for k in range(last_pattern_abs + 1, len(df)):
                    if float(df["High"].iloc[k]) >= float(bottom.iloc[k]):
                        returned_to_cloud = True
                    if returned_to_cloud and float(df["Close"].iloc[k]) > last_pattern_ceiling:
                        latest_idx = len(df) - 1
                        if body_high.iloc[latest_idx] < bottom.iloc[latest_idx]:
                            return _breakout_status_for_age(), "-", valid_count, first_valid_date, events
                        return "returned_to_cloud_waiting_for_pattern", "-", valid_count, first_valid_date, events
        latest_depth = events[-1][2]
        latest_status = f"{latest_depth}_retest_pattern"
        return latest_status, latest_depth, valid_count, first_valid_date, events
    if found_too_late:
        return "invalid_pattern_too_late", "-", 0, "-", []
    latest_idx = len(df) - 1
    latest_outside = (
        body_low.iloc[latest_idx] > top.iloc[latest_idx]
        if current_side == "above"
        else body_high.iloc[latest_idx] < bottom.iloc[latest_idx]
    )
    if latest_outside:
        return _breakout_status_for_age(), "-", 0, "-", []
    return "returned_to_cloud_waiting_for_pattern", "-", 0, "-", []


def run_ichimoku_search(target: str) -> int:
    group_name, members, source, exchange_suffix = _get_members(target)
    _should_refresh_group_data(group_name, members, exchange_suffix)
    print(f"[search] grupa={group_name}, liczba instrumentów={len(members)}, źródło={source}")
    dbg = _debug_symbol_target()
    if dbg:
        print(f"[search] debug symbol enabled: {dbg} (set via STOCKHELPER_DEBUG_SYMBOL)")
    current_datetime = datetime.now(UTC)
    results: list[ScanResult] = []
    flip_results: list[FlipResult] = []
    processed_count = 0
    error_count = 0
    error_samples: list[str] = []
    data_source_by_ticker: dict[str, str] = {}

    def _record_scan_error(ticker: str, err: str | None) -> None:
        nonlocal error_count
        error_count += 1
        if len(error_samples) < 12:
            error_samples.append(f"{ticker}: {_compact_error(err)}")

    # Scan the first symbol as a live rate-limit/captcha check; if clean, scan the rest in parallel.
    first = members[0]
    print(f"[1/{len(members)}] {first}")
    display_symbol, first_result, first_flip, first_err, first_source, first_stopped = _scan_one_with_retry_on_rate_limit(first, group_name, exchange_suffix, current_datetime)
    data_source_by_ticker[first] = first_source
    sequential = _rate_limit_detected(first_err)
    if group_name == "WIG":
        sequential = False
        print("[search] WIG mode: parallel scan enabled (refresh probe already completed).")
    elif group_name == "commodities":
        if os.getenv("STOCKHELPER_COMMODITIES_SEQUENTIAL", "0") == "1":
            sequential = True
            print("[search] COMMODITIES mode: sequential Stooq web fetch by STOCKHELPER_COMMODITIES_SEQUENTIAL=1.")
        else:
            sequential = False
            print("[search] COMMODITIES mode: bounded parallel Stooq web fetch (xdist-style workers; prompts still locked).")
    elif group_name.startswith("WIG_PART"):
        sequential = False
        print("[search] WIG_PART mode: parallel scan enabled (xdist-friendly split batch).")
    if first_stopped:
        return 1
    processed_count += 1
    if first_err:
        _record_scan_error(first, first_err)
        print(f"  pominięto ({first_err})")
    elif first_result:
        results.append(first_result)
    if first_flip:
        first_flip = _ensure_flip_ticker(first_flip, first)
        flip_results.append(first_flip)

    workers_override = _scan_workers_override()
    if workers_override == 1 and not sequential:
        sequential = True
        print("[workers] STOCKHELPER_SCAN_WORKERS=1 -> sequential Ichimoku scan mode.")

    rest = members[1:]
    if sequential or len(rest) == 0:
        if sequential and group_name != "commodities":
            print("[search] rate-limit/captcha detected -> switching to sequential mode.")
        for offset, ticker in enumerate(rest, start=2):
            display_symbol, result, flip, err, src, stopped = _scan_one_with_retry_on_rate_limit(ticker, group_name, exchange_suffix, current_datetime)
            data_source_by_ticker[ticker] = src
            print(f"[{offset}/{len(members)}] {ticker}", flush=True)
            processed_count += 1
            if stopped:
                break
            if err:
                _record_scan_error(ticker, err)
                print(f"  pominięto ({_compact_error(err)})", flush=True)
            elif result:
                results.append(result)
            if flip:
                flip = _ensure_flip_ticker(flip, ticker)
                flip_results.append(flip)
    else:
        if workers_override is not None:
            max_workers = min(max(1, workers_override), len(rest))
        elif group_name == "commodities":
            try:
                commodity_workers = int(os.getenv("STOCKHELPER_COMMODITIES_WORKERS", "6"))
            except ValueError:
                commodity_workers = 6
            max_workers = min(max(4, commodity_workers), len(rest))
        else:
            max_workers = min(6, max(2, (os.cpu_count() or 4) // 2), len(rest))
        print(f"[search] no rate-limit on probe -> parallel mode ({max_workers} workers, bounded queue).")
        try:
            stall_seconds = max(10.0, float(os.getenv("STOCKHELPER_SCAN_STALL_SECONDS", "45")))
        except ValueError:
            stall_seconds = 45.0
        indexed_rest = list(enumerate(rest, start=2))
        next_pos = 0
        pending: dict = {}
        queue_limit = max_workers * 2
        last_stall_log = 0.0
        last_vpn_continue_at = 0.0
        ex = ThreadPoolExecutor(max_workers=max_workers)

        def _submit_more() -> None:
            nonlocal next_pos
            while (
                next_pos < len(indexed_rest)
                and len(pending) < queue_limit
                and not STOP_SCAN_EVENT.is_set()
                and not PAUSE_SCAN_EVENT.is_set()
            ):
                idx, ticker = indexed_rest[next_pos]
                fut = ex.submit(_scan_one_with_retry_on_rate_limit, ticker, group_name, exchange_suffix, current_datetime, allow_prompt=False)
                pending[fut] = (idx, ticker, time.monotonic())
                next_pos += 1

        try:
            _submit_more()
            while pending:
                done, _not_done = wait(list(pending.keys()), timeout=1.0, return_when=FIRST_COMPLETED)
                now = time.monotonic()
                if not done:
                    if STOP_SCAN_EVENT.is_set():
                        break
                    stalled = [
                        f"{idx}/{len(members)} {ticker} ({int(now - started)}s)"
                        for _f, (idx, ticker, started) in pending.items()
                        if now - started >= stall_seconds
                    ]
                    if stalled and not PAUSE_SCAN_EVENT.is_set() and now - last_stall_log >= 30.0:
                        shown = ", ".join(stalled[:3])
                        extra = f" (+{len(stalled) - 3})" if len(stalled) > 3 else ""
                        print(f"[search] slow workers: {shown}{extra}. Ctrl+C cancels; STOCKHELPER_SCAN_STALL_SECONDS tunes this.", flush=True)
                        last_stall_log = now
                    if not PAUSE_SCAN_EVENT.is_set():
                        _submit_more()
                    continue
                for fut in done:
                    idx, ticker, _started = pending.pop(fut)
                    try:
                        display_symbol, result, flip, err, src, stopped = fut.result()
                    except Exception as exc:
                        display_symbol, result, flip, err, src, stopped = ticker, None, None, _compact_error(str(exc)), "unknown", False
                    data_source_by_ticker[ticker] = src
                    if err and _rate_limit_detected(err) and _should_prompt_rate_limit(group_name):
                        print(f"[{idx}/{len(members)}] {ticker}", flush=True)
                        print(f"  pauza VPN/rate-limit ({_compact_error(err)})", flush=True)
                        if _started < last_vpn_continue_at:
                            print(f"[search] stale pre-VPN rate-limit result for {ticker}; retrying without another prompt...", flush=True)
                            fut_retry = ex.submit(_scan_one_with_retry_on_rate_limit, ticker, group_name, exchange_suffix, current_datetime, allow_prompt=False)
                            pending[fut_retry] = (idx, ticker, time.monotonic())
                            continue
                        PAUSE_SCAN_EVENT.set()
                        if _prompt_vpn_continue_or_stop():
                            last_vpn_continue_at = time.monotonic()
                            print(f"[search] VPN continue confirmed; retrying {ticker}...", flush=True)
                            fut_retry = ex.submit(_scan_one_with_retry_on_rate_limit, ticker, group_name, exchange_suffix, current_datetime, allow_prompt=False)
                            pending[fut_retry] = (idx, ticker, time.monotonic())
                            continue
                        print("[search] Scan stopped by user after rate-limit detection.", flush=True)
                        STOP_SCAN_EVENT.set()
                        break
                    print(f"[{idx}/{len(members)}] {ticker}", flush=True)
                    processed_count += 1
                    if stopped:
                        STOP_SCAN_EVENT.set()
                        break
                    if err:
                        _record_scan_error(ticker, err)
                        print(f"  pominięto ({_compact_error(err)})", flush=True)
                    elif result:
                        results.append(result)
                    if flip:
                        flip = _ensure_flip_ticker(flip, ticker)
                        flip_results.append(flip)
                if STOP_SCAN_EVENT.is_set():
                    break
                _submit_more()
        except KeyboardInterrupt:
            STOP_SCAN_EVENT.set()
            for fut in pending:
                fut.cancel()
            print(
                "\n[search] Ctrl+C received: cancelling pending Ichimoku workers. "
                "Running downloads will stop after their current network timeout.",
                flush=True,
            )
            ex.shutdown(wait=False, cancel_futures=True)
            return 130
        finally:
            ex.shutdown(wait=not STOP_SCAN_EVENT.is_set(), cancel_futures=True)
        if STOP_SCAN_EVENT.is_set():
            return 1

    flip_results = [f for f in flip_results if _flip_still_actionable(f)]
    retest_by_ticker_side = {(f.ticker, f.current_side): (f"{f.retest_status} ({f.valid_retests_count})" if f.valid_retests_count > 0 else f.retest_status) for f in flip_results}
    ICHIMOKU_SEARCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_md = _daily_report_path("search", group_name)
    rows_md = []
    for row in sorted(results, key=lambda r: r.respect_days, reverse=True):
        side_col = "⚪ above" if row.side == "above" else ("🔴 below" if row.side == "below" else row.side)
        rows_md.append([row.ticker, side_col, row.respect_days, f"{row.respect_months:.1f}", row.start_date, f"{row.close:.4f}", f"{row.avg_turnover_10d_pln:.0f}" if row.avg_turnover_10d_pln is not None else "-", (row.ichimoku_status if row.ichimoku_status is not None else "-"), str(row.retest_count if row.retest_count is not None else "-"), (row.latest_retest_date if row.latest_retest_date is not None else "-"), (row.latest_retest_pattern if row.latest_retest_pattern is not None else "-"), row.ichimoku_risk or "-", row.tk_cross or "-", row.breakout_dynamic or "-", row.cloud_thickness or "-", row.chikou_confirmation or "-", row.kumo_twist or "-", row.tk_plus or "-", row.tenkan_in_cloud or "-", _stooq_chart_url(row.ticker), _build_chart_command(row.ticker, 'ichimoku'), _latest_data_marker(row.latest_candle_date, row.expected_latest_session_date), _fmt_optional_date(row.latest_candle_date), _fmt_optional_date(row.expected_latest_session_date)])
    _write_md_table(
        out_md,
        "WYNIKI",
        ["Ticker","Pozycja","Świece","Mies.","Start","Close","Avg10d PLN","Ichimoku status","Retest count","Latest Retest date","Latest Retest pattern","Risk","TK cross","Dynamic","Cloud","Chikou","Twist","TK plus","Tenkan in cloud","Link","Python command","Latest data?","Latest date","Expected date"],
        rows_md,
        description="WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).",
    )

    links_primary = _print_results_with_links(results, retest_by_ticker_side)
    print(f"\nZapisano MD: {out_md}")
    print(f"Źródło danych CSV instrumentów: {CSV_DATA_DIR}")
    print(f"[search] summary {group_name}: processed={processed_count}/{len(members)}, errors={error_count}")
    if error_samples:
        print(f"[search] error samples: {'; '.join(error_samples)}")
    if group_name == "forex":
        _print_forex_source_summary("search", members, data_source_by_ticker)
    if group_name == "commodities":
        _commodity_csv_health_check(members)
    elif group_name == "forex":
        _forex_csv_health_check(members, data_source_by_ticker)

    links_flip = _print_flip_results_with_links(flip_results)

    out_md_flip = out_md
    rows_flip_md=[]
    for row in sorted(flip_results, key=lambda r: r.months_since_flip, reverse=True):
        cur_col = "⚪ above" if row.current_side == "above" else ("🔴 below" if row.current_side == "below" else row.current_side)
        rows_flip_md.append([row.ticker,row.previous_side,cur_col,row.flip_date,f"{row.months_since_flip:.1f}",(f"{row.previous_respect_months:.1f}" if row.previous_respect_months is not None else "-"),row.retest_status,row.valid_retests_count,(f"{row.avg_turnover_10d_pln:.0f}" if row.avg_turnover_10d_pln is not None else "-"),(row.retest_events[-1][0] if row.retest_events else '-'),(row.retest_events[-1][1] if row.retest_events else '-'), (row.ichimoku_status if row.ichimoku_status is not None else "-"), row.ichimoku_risk or "-", row.tk_cross or "-", row.breakout_dynamic or "-", row.cloud_thickness or "-", row.chikou_confirmation or "-", row.kumo_twist or "-", row.tk_plus or "-", row.tenkan_in_cloud or "-", _stooq_chart_url(row.ticker),_build_chart_command(row.ticker, 'ichimoku'), _latest_data_marker(row.latest_candle_date, row.expected_latest_session_date), _fmt_optional_date(row.latest_candle_date), _fmt_optional_date(row.expected_latest_session_date)])
    _write_md_table(
        out_md_flip,
        "WYNIKI 2",
        ["Ticker","Było","Jest","Data wybicia","Mies. od wybicia","Mies. respektu przed wybiciem","Latest Retest status","Retest count","Avg10d PLN","Latest Retest date","Latest Retest pattern","Ichimoku status","Risk","TK cross","Dynamic","Cloud","Chikou","Twist","TK plus","Tenkan in cloud","Link","Python command","Latest data?","Latest date","Expected date"],
        rows_flip_md,
        append=True,
        description="WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.",
    )
    print(f"Zapisano MD: {out_md_flip}")
    _prune_search_history(group_name, keep_last=3)
    all_links = links_primary + [x for x in links_flip if x not in links_primary]
    if all_links and os.environ.get("STOCKHELPER_DEFER_OPEN_LINKS") != "1":
        try:
            open_all = input("Czy otworzyć wszystkie linki? [y/N]: ").strip().lower()
        except EOFError:
            open_all = "n"
        if open_all == "y":
            for link in all_links:
                webbrowser.open_new_tab(link)
    return 0





def _wedge_line_value(idx: int, anchor_a: tuple[int, float], anchor_b: tuple[int, float]) -> float:
    ia, ya = anchor_a
    ib, yb = anchor_b
    if ib == ia:
        return float(ya)
    return float(ya) + (float(yb) - float(ya)) * ((idx - ia) / (ib - ia))


def _wedge_probable_stop_touched_after_breakout(
    i: int,
    breakout_idx: int | None,
    breakout_direction: str,
    upper_a: tuple[int, float],
    upper_b: tuple[int, float],
    lower_a: tuple[int, float],
    lower_b: tuple[int, float],
    highs: Sequence[float],
    lows: Sequence[float],
    eps: float = 0.0,
) -> bool:
    """Return True when a post-breakout candle touches the midpoint stop.

    Wedge charts use the midpoint between the upper and lower wedge lines on
    the breakout candle as the probable stop loss.  A later wick touch burns the
    setup, so the scanner should reject this anchor set and keep searching for a
    fresher wedge.
    """
    if breakout_idx is None or i <= breakout_idx:
        return False
    breakout_upper = _wedge_line_value(breakout_idx, upper_a, upper_b)
    breakout_lower = _wedge_line_value(breakout_idx, lower_a, lower_b)
    probable_stop = (breakout_upper + breakout_lower) / 2.0
    stop_eps = max(float(eps), abs(probable_stop) * 1e-6)
    if breakout_direction == "long":
        return float(lows[i]) <= probable_stop + stop_eps
    if breakout_direction == "short":
        return float(highs[i]) >= probable_stop - stop_eps
    return False


def _post_anchor_touch_tolerance_static(price: float) -> float:
    pip = 0.0001 if abs(float(price)) < 1 else 0.01
    return max(pip * 5, abs(float(price)) * 0.0005)


def _clustered_contact_count(indices: list[int], max_gap: int = 1) -> int:
    # Touches separated only by glued/adjacent candles count as one contact;
    # a new contact requires at least one full non-touching candle between them.
    if not indices:
        return 0
    ordered = sorted(set(indices))
    groups = 1
    prev = ordered[0]
    for idx in ordered[1:]:
        if idx - prev > max_gap:
            groups += 1
        prev = idx
    return groups


def _clustered_contact_indices(indices: list[int], max_gap: int = 1) -> list[int]:
    """Return one representative index per visually separate touch cluster."""
    ordered = sorted(set(indices))
    if not ordered:
        return []
    reps = [ordered[0]]
    prev = ordered[0]
    for idx in ordered[1:]:
        if idx - prev > max_gap:
            reps.append(idx)
        prev = idx
    return reps


def _scanner_session_path_for_ticker(ticker: str) -> Path:
    stem = re.sub(r"\.(WA|PL)$", "", str(ticker), flags=re.IGNORECASE).strip()
    return STATE_DATA_DIR / "sessions" / f"{stem}.json"


def _manual_wedge_objects_for_ticker(ticker: str) -> tuple[dict, dict] | None:
    path = _scanner_session_path_for_ticker(ticker)
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    objects = state.get("drawn_objects") if isinstance(state, dict) else None
    if not isinstance(objects, list):
        return None
    wedges = [obj for obj in objects if isinstance(obj, dict) and (obj.get("type") == "wedge" or obj.get("group_id") == "auto-wedge")]
    if len(wedges) < 2:
        return None
    upper = next((obj for obj in wedges if "upper" in str(obj.get("label", "")).lower()), wedges[0])
    lower = next((obj for obj in wedges if "lower" in str(obj.get("label", "")).lower() and obj is not upper), None)
    if lower is None:
        lower = next((obj for obj in wedges if obj is not upper), None)
    if lower is None:
        return None
    return upper, lower


def _manual_wedge_anchor(obj: dict) -> tuple[tuple[str, float], tuple[str, float]] | None:
    anchor_x = obj.get("anchor_x")
    anchor_y = obj.get("anchor_y")
    if isinstance(anchor_x, list) and isinstance(anchor_y, list) and len(anchor_x) >= 2 and len(anchor_y) >= 2:
        try:
            return (str(anchor_x[0]), float(anchor_y[0])), (str(anchor_x[1]), float(anchor_y[1]))
        except Exception:
            return None
    try:
        return (str(obj["x0"]), float(obj["y0"])), (str(obj["x1"]), float(obj["y1"]))
    except Exception:
        return None


def _find_manual_unbroken_wedge_setup(df: pd.DataFrame, ticker: str) -> WedgeScanResult | None:
    pair = _manual_wedge_objects_for_ticker(ticker)
    if pair is None:
        return None
    upper_raw = _manual_wedge_anchor(pair[0])
    lower_raw = _manual_wedge_anchor(pair[1])
    if upper_raw is None or lower_raw is None:
        return None
    required = {"Date", "Open", "High", "Low", "Close"}
    if df is None or df.empty or not required.issubset(df.columns):
        return None
    w = df.copy()
    w["Date"] = pd.to_datetime(w["Date"], errors="coerce")
    for col in ["Open", "High", "Low", "Close"]:
        w[col] = pd.to_numeric(w[col], errors="coerce")
    w = w.dropna(subset=["Date", "Open", "High", "Low", "Close"]).sort_values("Date").reset_index(drop=True)
    date_to_idx = {str(pd.to_datetime(dt).date()): i for i, dt in enumerate(w["Date"])}

    def _idx_anchor(raw: tuple[str, float]) -> tuple[int, float] | None:
        try:
            key = str(pd.to_datetime(raw[0]).date())
        except Exception:
            return None
        idx = date_to_idx.get(key)
        return None if idx is None else (idx, float(raw[1]))

    up0 = _idx_anchor(upper_raw[0]); up1 = _idx_anchor(upper_raw[1])
    lo0 = _idx_anchor(lower_raw[0]); lo1 = _idx_anchor(lower_raw[1])
    if up0 is None or up1 is None or lo0 is None or lo1 is None or up0[0] == up1[0] or lo0[0] == lo1[0]:
        return None
    upper_a, upper_b = up0, up1
    lower_a, lower_b = lo0, lo1
    highs = w["High"].astype(float).to_numpy(); lows = w["Low"].astype(float).to_numpy(); closes = w["Close"].astype(float).to_numpy()
    end = len(w) - 1
    first_validation = max(min(up0[0], up1[0]), min(lo0[0], lo1[0]))
    tol = max(float(pd.Series(highs[first_validation:end + 1] - lows[first_validation:end + 1]).tail(30).mean()) * 0.18, abs(float(closes[end])) * 0.004)
    close_eps = max(tol * 0.02, abs(float(closes[end])) * 1e-6)
    upper_contacts = [up0[0], up1[0]]; lower_contacts = [lo0[0], lo1[0]]
    breakout_idx = None; breakout_direction = "-"
    for i in range(first_validation, end + 1):
        up = _wedge_line_value(i, upper_a, upper_b); lo = _wedge_line_value(i, lower_a, lower_b)
        if lo >= up:
            return None
        if closes[i] > up + close_eps or closes[i] < lo - close_eps:
            direction = "long" if closes[i] > up + close_eps else "short"
            if i < end - 5:
                return None
            if breakout_idx is None:
                breakout_idx = i; breakout_direction = direction
                continue
            if direction != breakout_direction:
                return None
        if breakout_idx is not None:
            if _wedge_probable_stop_touched_after_breakout(i, breakout_idx, breakout_direction, upper_a, upper_b, lower_a, lower_b, highs, lows, close_eps):
                return None
            continue
        if closes[i] <= up + close_eps and highs[i] >= up - min(tol, _post_anchor_touch_tolerance_static(up)):
            upper_contacts.append(i)
        if closes[i] >= lo - close_eps and lows[i] <= lo + min(tol, _post_anchor_touch_tolerance_static(lo)):
            lower_contacts.append(i)
    up_count = _clustered_contact_count(upper_contacts); lo_count = _clustered_contact_count(lower_contacts)
    # Manual saved wedges remain authoritative while unbroken, and after a
    # breakout/breakdown for up to five candles unless the probable midpoint SL
    # was touched inside that period.
    if up_count < 2 or lo_count < 2:
        return None
    width_start = _wedge_line_value(first_validation, upper_a, upper_b) - _wedge_line_value(first_validation, lower_a, lower_b)
    width_end = _wedge_line_value(end, upper_a, upper_b) - _wedge_line_value(end, lower_a, lower_b)
    last_close = float(closes[end])
    upper_start, upper_end = sorted([upper_a, upper_b], key=lambda x: x[0])
    lower_start, lower_end = sorted([lower_a, lower_b], key=lambda x: x[0])
    def _fmt(i: int) -> str: return str(pd.to_datetime(w["Date"].iloc[i]).date())
    return WedgeScanResult(
        ticker=ticker, start_date=_fmt(first_validation), end_date=_fmt(end), duration_days=end - first_validation + 1,
        upper_start_date=_fmt(upper_start[0]), upper_start_price=round(float(upper_start[1]), 5), upper_end_date=_fmt(upper_end[0]), upper_end_price=round(float(upper_end[1]), 5),
        lower_start_date=_fmt(lower_start[0]), lower_start_price=round(float(lower_start[1]), 5), lower_end_date=_fmt(lower_end[0]), lower_end_price=round(float(lower_end[1]), 5),
        upper_touches=up_count, lower_touches=lo_count, width_start_pct=round(width_start / max(abs(last_close), 1e-9) * 100, 2), width_end_pct=round(width_end / max(abs(last_close), 1e-9) * 100, 2),
        slope_pct_per_day=round(abs(((upper_b[1] - upper_a[1]) / (upper_b[0] - upper_a[0])) - ((lower_b[1] - lower_a[1]) / (lower_b[0] - lower_a[0]))) / max(abs(last_close), 1e-9) * 100, 4),
        slope_strength="manual", fit_quality=100.0, recent_proximity_pct=100.0, compression_pct=round(max(0.0, min(100.0, (1.0 - width_end / max(width_start, 1e-9)) * 100.0)), 1), score=1000000.0, current_close=last_close,
        breakout_date=_fmt(breakout_idx) if breakout_idx is not None else "-", breakout_direction=breakout_direction,
    )

def _find_falling_wedge_setup(df: pd.DataFrame) -> WedgeScanResult | None:
    """Detect an unbroken descending wedge ending at the latest candle.

    The first two touches on each side are exact OHLC extremes (line anchors).
    Later touches may be wick/body probes as long as the candle does not close
    outside the line. Adjacent candles touching a line are counted as one touch.
    """
    required = {"Date", "Open", "High", "Low", "Close"}
    if df is None or df.empty or not required.issubset(df.columns) or len(df) < 55:
        return None
    w = df.copy()
    w["Date"] = pd.to_datetime(w["Date"], errors="coerce")
    for col in ["Open", "High", "Low", "Close"]:
        w[col] = pd.to_numeric(w[col], errors="coerce")
    w = w.dropna(subset=["Date", "Open", "High", "Low", "Close"]).sort_values("Date").reset_index(drop=True)
    if len(w) < 55:
        return None
    if len(w) > 420:
        w = w.tail(420).reset_index(drop=True)

    best: WedgeScanResult | None = None
    highs = w["High"].astype(float).to_numpy()
    lows = w["Low"].astype(float).to_numpy()
    opens = w["Open"].astype(float).to_numpy()
    closes = w["Close"].astype(float).to_numpy()
    dates = w["Date"]
    n = len(w)
    global_high = max(float(pd.Series(highs).max()), 1e-9)


    def _fmt_date(i: int) -> str:
        return str(pd.to_datetime(dates.iloc[i]).date())

    def _touch_tolerance(start: int, end: int) -> float:
        avg_range = float(pd.Series(highs[start : end + 1] - lows[start : end + 1]).dropna().tail(30).mean())
        last_close = max(abs(float(closes[end])), 1e-9)
        return max(avg_range * 0.18 if pd.notna(avg_range) else 0.0, last_close * 0.004)

    def _post_anchor_touch_tolerance(price: float) -> float:
        # After the two strict anchor touches, count only candles whose relevant
        # wick reaches the wedge line.  Wicks that pass through the line are
        # still touches as long as the candle closes back inside the wedge.
        return _post_anchor_touch_tolerance_static(price)

    for length in range(min(360, n), 44, -5):
        start = n - length
        end = n - 1
        seg_high = highs[start : end + 1]
        seg_low = lows[start : end + 1]
        if len(seg_high) < 45:
            continue
        high_abs = start + int(seg_high.argmax())
        low_abs = start + int(seg_low.argmin())
        # A falling wedge should be a currently active formation, not a random
        # old channel. Its highest point normally starts the formation.
        if high_abs > start + int(length * 0.45):
            continue

        upper_anchor1_candidates: list[int] = [high_abs]
        upper_anchor1_latest = min(end - 12, start + int(length * 0.72))
        for j in range(start + 2, upper_anchor1_latest + 1):
            if j == high_abs:
                continue
            if highs[j] > highs[high_abs] * 1.000001:
                continue
            if highs[j] >= highs[j - 1] and highs[j] >= highs[j + 1]:
                upper_anchor1_candidates.append(j)
        # Do not force a blow-off high to be the first upper anchor.  Longer,
        # still-descending wedges can be more useful when a later swing high
        # creates the active line and keeps recent price near the boundary.
        upper_anchor1_candidates = sorted(
            set(upper_anchor1_candidates),
            key=lambda j: (0 if j == high_abs else 1, -float(highs[j]), j),
        )[:12]
        upper_anchor_pairs: list[tuple[int, int]] = []
        for uh1 in upper_anchor1_candidates:
            upper_anchor2_candidates: list[int] = []
            for j in range(uh1 + 5, end - 4):
                if highs[j] >= highs[uh1]:
                    continue
                if highs[j] >= highs[j - 1] and highs[j] >= highs[j + 1]:
                    upper_anchor2_candidates.append(j)
            upper_anchor2_candidates = sorted(
                upper_anchor2_candidates,
                key=lambda j: (-float(highs[j]), abs((end - j) - max(12, (end - uh1) // 4)), j),
            )
            active_upper_anchor2_candidates = sorted(
                upper_anchor2_candidates,
                key=lambda j: (abs(end - j), -float(highs[j]), j),
            )
            selected_upper_anchor2 = list(dict.fromkeys(upper_anchor2_candidates[:8] + active_upper_anchor2_candidates[:8]))
            upper_anchor_pairs.extend((uh1, uh2) for uh2 in selected_upper_anchor2)
        upper_anchor_pairs = sorted(
            set(upper_anchor_pairs),
            key=lambda pair: (0 if pair[0] == high_abs else 1, min(abs(end - pair[1]), 80), -float(highs[pair[0]]), -float(highs[pair[1]]), pair[1]),
        )[:24]
        if not upper_anchor_pairs:
            continue

        lower_anchor1_candidates: list[int] = [low_abs]
        lower_anchor1_latest = min(end - 8, start + int(length * 0.95))
        for j in range(start + 2, lower_anchor1_latest + 1):
            if j == low_abs:
                continue
            if lows[j] <= lows[j - 1] and lows[j] <= lows[j + 1]:
                lower_anchor1_candidates.append(j)
        lower_anchor1_candidates = sorted(
            set(lower_anchor1_candidates),
            key=lambda j: (0 if j == low_abs else 1, abs(end - j), float(lows[j])),
        )[:12]
        lower_anchor_pairs: list[tuple[int, int]] = []
        for lh1 in lower_anchor1_candidates:
            lower_anchor2_candidates: list[int] = []
            for j in range(lh1 + 5, end - 2):
                # Allow the lower wedge boundary to descend when it falls more
                # slowly than the upper boundary.  Some active falling wedges
                # (e.g. DNP.WA) compress with lower lows, so requiring the second
                # lower anchor to be higher than the first hides valid setups.
                if lows[j] <= lows[j - 1] and lows[j] <= lows[j + 1]:
                    lower_anchor2_candidates.append(j)
            active_lower_anchor2_candidates = sorted(lower_anchor2_candidates, key=lambda j: (abs(end - j), -j))
            low_lower_anchor2_candidates = sorted(lower_anchor2_candidates, key=lambda j: (float(lows[j]), abs(end - j), j))
            selected_lower_anchor2 = list(dict.fromkeys(active_lower_anchor2_candidates[:8] + low_lower_anchor2_candidates[:8]))
            lower_anchor_pairs.extend((lh1, lh2) for lh2 in selected_lower_anchor2)
        lower_anchor_pairs = sorted(
            set(lower_anchor_pairs),
            key=lambda pair: (min(abs(end - pair[1]), 80), 0 if pair[0] == low_abs else 1, float(lows[pair[1]]), pair[0]),
        )[:72]
        if not lower_anchor_pairs:
            continue

        for uh1, uh2 in upper_anchor_pairs:
            upper_a = (uh1, float(highs[uh1]))
            upper_b = (uh2, float(highs[uh2]))
            upper_slope = (upper_b[1] - upper_a[1]) / (upper_b[0] - upper_a[0])
            if upper_slope >= 0:
                continue
            for lh1, lh2 in lower_anchor_pairs:
                lower_a = (lh1, float(lows[lh1]))
                lower_b = (lh2, float(lows[lh2]))
                lower_slope = (lower_b[1] - lower_a[1]) / (lower_b[0] - lower_a[0])
                # Falling wedges must converge. The lower boundary is allowed to
                # be flat or rising when that best describes current price
                # compression (triangle-like wedges). Reject only lower lines
                # rising faster than the falling upper line can reasonably close.
                if lower_slope > abs(upper_slope) * 1.10:
                    continue
                # Upper line must fall faster than lower line so the wedge narrows.
                if upper_slope >= lower_slope:
                    continue

                tol = _touch_tolerance(start, end)

                def _anchors_uninterrupted(anchor_a: tuple[int, float], anchor_b: tuple[int, float], side: str) -> bool:
                    # The first two anchor points must define a clean extreme-to-extreme
                    # segment. No intermediate candle shadow may break beyond that
                    # segment before the second anchor is reached.
                    left, right = sorted((anchor_a[0], anchor_b[0]))
                    if right - left <= 1:
                        return True
                    eps = max(tol * 0.05, max(abs(anchor_a[1]), abs(anchor_b[1]), 1e-9) * 1e-6)
                    for k in range(left + 1, right):
                        line_value = _wedge_line_value(k, anchor_a, anchor_b)
                        if side == "upper" and highs[k] > line_value + eps:
                            return False
                        if side == "lower" and lows[k] < line_value - eps:
                            return False
                    return True

                if not _anchors_uninterrupted(upper_a, upper_b, "upper"):
                    continue
                if not _anchors_uninterrupted(lower_a, lower_b, "lower"):
                    continue

                first_validation = max(min(uh1, uh2), min(lh1, lh2))
                upper_anchor_indices = {uh1, uh2}
                lower_anchor_indices = {lh1, lh2}
                upper_exact_contacts = [uh1, uh2]
                lower_exact_contacts = [lh1, lh2]
                upper_contacts = [uh1, uh2]
                lower_contacts = [lh1, lh2]
                breakout_idx: int | None = None
                breakout_direction = "-"
                invalid = False
                width_start = _wedge_line_value(first_validation, upper_a, upper_b) - _wedge_line_value(first_validation, lower_a, lower_b)
                width_end = _wedge_line_value(end, upper_a, upper_b) - _wedge_line_value(end, lower_a, lower_b)
                if width_start <= 0 or width_end <= 0 or width_end >= width_start * 0.92:
                    continue
                close_eps = max(tol * 0.02, max(abs(float(closes[end])), 1e-9) * 1e-6)
                exact_tol = max(tol * 0.12, max(abs(float(closes[end])), 1e-9) * 1e-6)

                def _is_local_extreme(i: int, side: str, radius: int = 1) -> bool:
                    if i <= 0 or i >= n - 1:
                        return True
                    left = max(0, i - radius)
                    right = min(n, i + radius + 1)
                    if side == "upper":
                        return highs[i] >= max(highs[left:right])
                    return lows[i] <= min(lows[left:right])

                def _accept_or_reject_breakout(i: int, direction: str) -> bool:
                    nonlocal breakout_idx, breakout_direction
                    if i < end - 5:
                        return False
                    if breakout_idx is None:
                        breakout_idx = i
                        breakout_direction = direction
                        return True
                    return breakout_direction == direction

                def _breakout_stop_loss_touched(i: int) -> bool:
                    return _wedge_probable_stop_touched_after_breakout(
                        i,
                        breakout_idx,
                        breakout_direction,
                        upper_a,
                        upper_b,
                        lower_a,
                        lower_b,
                        highs,
                        lows,
                        close_eps,
                    )

                # Each boundary must remain valid from its own first anchor. If
                # price closed beyond an anchor line earlier than the latest
                # five candles, this candidate was already broken and another
                # anchor set must be found instead.
                for i in range(min(high_abs, uh2), end + 1):
                    if closes[i] > _wedge_line_value(i, upper_a, upper_b) + close_eps:
                        if i < end - 5:
                            invalid = True
                            break
                if invalid:
                    continue
                for i in range(min(lh1, lh2), end + 1):
                    if closes[i] < _wedge_line_value(i, lower_a, lower_b) - close_eps:
                        if i < end - 5:
                            invalid = True
                            break
                if invalid:
                    continue

                for i in range(first_validation, end + 1):
                    up = _wedge_line_value(i, upper_a, upper_b)
                    lo = _wedge_line_value(i, lower_a, lower_b)
                    if lo >= up:
                        invalid = True
                        break
                    # No candle may close on the other side of a still-valid wedge.
                    # The only accepted outside close is the first breakout/breakdown
                    # candle, and it must be very recent (latest candle or up to the
                    # previous 5 candles) to be treated as an absolute top-choice setup.
                    if closes[i] > up + close_eps or closes[i] < lo - close_eps:
                        direction = "long" if closes[i] > up + close_eps else "short"
                        if _accept_or_reject_breakout(i, direction):
                            continue
                        if breakout_idx is not None:
                            if breakout_direction == "long" and closes[i] >= lo - close_eps:
                                continue
                            if breakout_direction == "short" and closes[i] <= up + close_eps:
                                continue
                        invalid = True
                        break
                    if breakout_idx is not None:
                        if _breakout_stop_loss_touched(i):
                            # This breakout's probable SL was reached, so the
                            # candidate is burnt. Reject only this anchor set and
                            # keep searching so later/leaner adjusted lines can win.
                            invalid = True
                            break
                        continue
                    if i not in upper_anchor_indices and i > max(upper_anchor_indices) and closes[i] <= up + close_eps:
                        upper_touch_tol = min(tol, _post_anchor_touch_tolerance(up))
                        upper_exact_tol = min(exact_tol, upper_touch_tol)
                        if _is_local_extreme(i, "upper") and highs[i] > up + upper_exact_tol:
                            # A later local high that sits visibly above an older
                            # upper line is a new candidate anchor, not an extra
                            # tolerated touch of the stale line. Reject this
                            # candidate so anchor selection can move to that
                            # candle extreme (e.g. BMC.WA 2026-07-06).
                            invalid = True
                            break
                        if _is_local_extreme(i, "upper") and abs(highs[i] - up) <= upper_exact_tol:
                            upper_exact_contacts.append(i)
                            upper_contacts.append(i)
                        elif highs[i] >= up - upper_touch_tol:
                            upper_contacts.append(i)
                    if i not in lower_anchor_indices and i > max(lower_anchor_indices) and closes[i] >= lo - close_eps:
                        lower_touch_tol = min(tol, _post_anchor_touch_tolerance(lo))
                        lower_exact_tol = min(exact_tol, lower_touch_tol)
                        if _is_local_extreme(i, "lower") and abs(lows[i] - lo) <= lower_exact_tol:
                            lower_exact_contacts.append(i)
                            lower_contacts.append(i)
                        elif lows[i] <= lo + lower_touch_tol:
                            lower_contacts.append(i)
                if invalid:
                    continue

                def _drop_pre_breakout_touch_cluster(indices: list[int]) -> list[int]:
                    # A candle or glued group of candles that the line passes
                    # through immediately before breakout is breakout noise, not
                    # an independent touchpoint confirming the wedge.
                    if breakout_idx is None:
                        return indices
                    ordered = [idx for idx in sorted(set(indices)) if idx < breakout_idx]
                    if not ordered or breakout_idx - ordered[-1] > 1:
                        return ordered
                    cut = len(ordered) - 1
                    while cut > 0 and ordered[cut] - ordered[cut - 1] <= 1:
                        cut -= 1
                    return ordered[:cut]

                upper_contacts = _drop_pre_breakout_touch_cluster(upper_contacts)
                lower_contacts = _drop_pre_breakout_touch_cluster(lower_contacts)
                upper_exact_contacts = _drop_pre_breakout_touch_cluster(upper_exact_contacts)
                lower_exact_contacts = _drop_pre_breakout_touch_cluster(lower_exact_contacts)

                def _structural_contacts(
                    contacts: list[int],
                    exact_contacts: list[int],
                    side: str,
                ) -> list[int]:
                    # The two anchors are always real touches.  After anchors,
                    # count any candle whose wick or body reaches through the
                    # boundary and then closes back inside the wedge. Adjacent
                    # touch candles still collapse into a single visual contact.
                    return _clustered_contact_indices(sorted(set(contacts)))

                upper_structural_contacts = _structural_contacts(upper_contacts, upper_exact_contacts, "upper")
                lower_structural_contacts = _structural_contacts(lower_contacts, lower_exact_contacts, "lower")
                upper_exact_count = _clustered_contact_count(upper_exact_contacts)
                lower_exact_count = _clustered_contact_count(lower_exact_contacts)
                up_count = len(upper_structural_contacts)
                lo_count = len(lower_structural_contacts)
                if breakout_idx is not None:
                    # A valid breakout needs the broken boundary to have at
                    # least three pre-breakout touches. Both lines must still
                    # have their two anchors; having three touches on both lines
                    # is better, but not mandatory.
                    breakout_side_count = up_count if breakout_direction == "long" else lo_count
                    if min(up_count, lo_count) < 2 or breakout_side_count < 3:
                        continue
                elif up_count < 2 or lo_count < 2:
                    # Unbroken wedges are watchlist candidates once both lines
                    # have at least their two anchor points.
                    continue
                last_close = float(closes[end])
                width_start_pct = width_start / max(abs(last_close), 1e-9) * 100.0
                width_end_pct = width_end / max(abs(last_close), 1e-9) * 100.0
                width_ratio = width_start / max(width_end, 1e-9)
                slope_pct = abs(upper_slope - lower_slope) / max(abs(last_close), 1e-9) * 100.0
                formation_start = min(upper_a[0], upper_b[0], lower_a[0], lower_b[0])
                duration = end - formation_start + 1
                duration_months = duration / 21.0
                compression_pct = max(0.0, min(100.0, (1.0 - width_end / max(width_start, 1e-9)) * 100.0))

                # For active breakouts, grade wedge fit using the candles before
                # the breakout instead of the post-breakout run-up. Otherwise a
                # successful move away from the wedge makes proximity look bad
                # and can hide fresh breakouts such as PXM before the 5-day window.
                quality_end = max(first_validation, (breakout_idx - 1) if breakout_idx is not None else end)
                recent_from = max(first_validation, quality_end - 35)
                recent_widths: list[float] = []
                recent_upper_gaps: list[float] = []
                recent_lower_gaps: list[float] = []
                recent_min_gaps: list[float] = []
                for k in range(recent_from, quality_end + 1):
                    up_k = _wedge_line_value(k, upper_a, upper_b)
                    lo_k = _wedge_line_value(k, lower_a, lower_b)
                    width_k = max(up_k - lo_k, 1e-9)
                    recent_widths.append(width_k)
                    upper_gap = max(0.0, up_k - highs[k]) / width_k
                    lower_gap = max(0.0, lows[k] - lo_k) / width_k
                    recent_upper_gaps.append(upper_gap)
                    recent_lower_gaps.append(lower_gap)
                    recent_min_gaps.append(min(upper_gap, lower_gap))
                median_upper_gap = float(pd.Series(recent_upper_gaps).median()) if recent_upper_gaps else 1.0
                median_lower_gap = float(pd.Series(recent_lower_gaps).median()) if recent_lower_gaps else 1.0
                median_min_gap = float(pd.Series(recent_min_gaps).median()) if recent_min_gaps else 1.0
                current_width = max(_wedge_line_value(quality_end, upper_a, upper_b) - _wedge_line_value(quality_end, lower_a, lower_b), 1e-9)
                current_upper_gap = max(0.0, _wedge_line_value(quality_end, upper_a, upper_b) - highs[quality_end]) / current_width
                current_lower_gap = max(0.0, lows[quality_end] - _wedge_line_value(quality_end, lower_a, lower_b)) / current_width
                # Prefer wedges whose active boundaries are both close enough to
                # current price to be realistically breakable soon. A top line far
                # above price or a bottom line far below price is less actionable.
                current_worst_gap = max(current_upper_gap, current_lower_gap)
                median_worst_gap = max(median_upper_gap, median_lower_gap)
                breakout_potential_quality = max(0.0, min(1.0, 1.0 - (current_worst_gap * 0.55 + median_worst_gap * 0.25 + median_min_gap * 0.20)))
                breakout_recent_bonus = 0.0
                breakout_age = None
                if breakout_idx is not None:
                    breakout_age = end - breakout_idx
                    breakout_recent_bonus = max(0.0, 6.0 - float(breakout_age)) / 6.0
                last_upper_contact_age = (breakout_idx if breakout_idx is not None else end) - max(upper_contacts)
                last_lower_contact_age = (breakout_idx if breakout_idx is not None else end) - max(lower_contacts)
                # Reject theoretical oversized wedges whose upper boundary no longer
                # follows the active structure. A useful wedge has recent price
                # compression near both trendlines, especially the upper line.
                if (
                    median_upper_gap > (0.76 if breakout_idx is not None else 0.62)
                    or median_lower_gap > (0.68 if breakout_idx is not None else 0.50)
                    or median_min_gap > (0.50 if breakout_idx is not None else 0.42)
                    or last_upper_contact_age > (110 if breakout_idx is not None else 75)
                    or last_lower_contact_age > (85 if breakout_idx is not None else 55)
                    or (breakout_direction == "short" and last_upper_contact_age > 70)
                    or width_end_pct > (40.0 if breakout_idx is not None else 28.0)
                    or width_start_pct > (130.0 if breakout_idx is not None else 95.0)
                    or width_ratio > (8.0 if breakout_idx is not None else 5.5)
                    or (breakout_idx is None and breakout_potential_quality < 0.18)
                ):
                    continue

                touch_quality = min(1.0, (up_count + lo_count) / 7.0) * (0.75 + 0.25 * min(up_count, lo_count) / max(up_count, lo_count))
                # Prefer the larger valid wedge when a small wedge has only a
                # modest touch-count advantage. A broader/older wedge with 3
                # clean touches should beat a tiny 4-touch wedge.
                size_preference = 1.0 + min(1.25, duration_months / 5.0) + min(0.55, width_start_pct / 80.0)
                higher_high_width_ok = width_start_pct <= (105.0 if breakout_idx is not None else 82.0) and width_end_pct <= (34.0 if breakout_idx is not None else 24.0) and width_ratio <= (6.0 if breakout_idx is not None else 4.5)
                upper_anchor_height_bonus = 1.0
                if higher_high_width_ok:
                    # Prefer a higher possible top anchor only when it does not
                    # turn the setup into an economically oversized wedge.
                    upper_anchor_height_bonus += min(0.55, max(0.0, (upper_a[1] / global_high) - 0.92) * 6.0)
                if upper_a[0] != high_abs and last_upper_contact_age <= 35:
                    upper_anchor_height_bonus += 0.18
                economical_width_penalty = 1.0
                if width_start_pct > (95.0 if breakout_idx is not None else 72.0):
                    economical_width_penalty = 0.82
                lower_line_shape_bonus = 1.0
                if breakout_direction == "long":
                    if lower_slope < 0:
                        # After a long breakout, prefer an adjusted/leaner bottom
                        # boundary over a wide downward lower line that creates an
                        # economically poor stop-loss distance.
                        lower_line_shape_bonus = 0.68
                    else:
                        # A flat/rising lower boundary uses the same bottom but
                        # tightens the probable stop after a long breakout.
                        lower_line_shape_bonus = 1.18
                exact_anchor_bonus = 1.0 + min(0.18, max(0, lower_exact_count - 2) * 0.06 + max(0, upper_exact_count - 2) * 0.03)
                proximity_quality = max(0.0, 1.0 - (median_upper_gap * 0.55 + median_lower_gap * 0.30 + median_min_gap * 0.15))
                compression_quality = max(0.0, min(1.0, compression_pct / 65.0))
                fit_quality = max(0.0, min(100.0, touch_quality * exact_anchor_bonus * proximity_quality * 100.0))
                if fit_quality < 35.0 or compression_quality < 0.12:
                    continue
                if slope_pct >= 0.40:
                    slope_strength = "very strong"
                elif slope_pct >= 0.20:
                    slope_strength = "strong"
                elif slope_pct >= 0.08:
                    slope_strength = "moderate"
                else:
                    slope_strength = "mild"
                # Do not let steepness dominate anchor selection. A leaner upper
                # boundary with valid extreme anchors and wick touches is a better
                # scanner match than a steeper line that only wins because of slope.
                slope_bonus = {"mild": 1.05, "moderate": 1.00, "strong": 0.95, "very strong": 0.90}[slope_strength]
                breakout_bonus = 1.0 + breakout_recent_bonus * 4.0
                score = (duration_months * 18.0 + width_start_pct * 3.0) * touch_quality * exact_anchor_bonus * proximity_quality * (0.70 + compression_quality) * slope_bonus * breakout_bonus * (0.45 + 0.75 * breakout_potential_quality) * size_preference * upper_anchor_height_bonus * economical_width_penalty * lower_line_shape_bonus
                recent_proximity_pct = max(0.0, min(100.0, proximity_quality * 100.0))
                # The first two anchors for each line are exact candle extremes,
                # not tolerance contacts. For display/export, keep the selected
                # upper swing-high anchor (not necessarily the absolute high), and
                # start the lower line from its first chronological anchor so the
                # bottom boundary is drawn from the first visible contact rather
                # than the second.
                upper_start, upper_end = upper_a, upper_b
                lower_start, lower_end = sorted([lower_a, lower_b], key=lambda x: x[0])
                cand = WedgeScanResult(
                    ticker="",
                    start_date=_fmt_date(formation_start),
                    end_date=_fmt_date(end),
                    duration_days=duration,
                    upper_start_date=_fmt_date(upper_start[0]),
                    upper_start_price=round(float(upper_start[1]), 5),
                    upper_end_date=_fmt_date(upper_end[0]),
                    upper_end_price=round(float(upper_end[1]), 5),
                    lower_start_date=_fmt_date(lower_start[0]),
                    lower_start_price=round(float(lower_start[1]), 5),
                    lower_end_date=_fmt_date(lower_end[0]),
                    lower_end_price=round(float(lower_end[1]), 5),
                    upper_touches=up_count,
                    lower_touches=lo_count,
                    width_start_pct=round(width_start_pct, 2),
                    width_end_pct=round(width_end_pct, 2),
                    slope_pct_per_day=round(slope_pct, 4),
                    slope_strength=slope_strength,
                    fit_quality=round(fit_quality, 1),
                    recent_proximity_pct=round(recent_proximity_pct, 1),
                    compression_pct=round(compression_pct, 1),
                    score=round(score, 2),
                    current_close=last_close,
                    breakout_date=_fmt_date(breakout_idx) if breakout_idx is not None else "-",
                    breakout_direction=breakout_direction,
                )
                def _candidate_beats_best(candidate: WedgeScanResult, current: WedgeScanResult | None) -> bool:
                    if current is None:
                        return True
                    candidate_touches = candidate.upper_touches + candidate.lower_touches
                    current_touches = current.upper_touches + current.lower_touches
                    same_state = (candidate.breakout_direction or "-") == (current.breakout_direction or "-")
                    comparable_touches = candidate_touches >= current_touches - 1
                    comparable_duration = candidate.duration_days >= current.duration_days * 0.55
                    oversized_current = current.width_end_pct > 30.0 or current.width_start_pct > 95.0
                    materially_tighter = (
                        candidate.width_end_pct <= current.width_end_pct * (0.92 if oversized_current else 0.78)
                        or candidate.width_start_pct <= current.width_start_pct * (0.82 if oversized_current else 0.70)
                    )
                    if same_state and comparable_touches and comparable_duration and materially_tighter:
                        # If a valid tighter alternative exists, prefer it over an
                        # oversized wedge. Raw score only breaks ties when neither
                        # wedge is clearly oversized. If no alternative appears,
                        # the wide wedge can still remain best.
                        return oversized_current or candidate.score >= current.score * 0.86
                    much_longer_with_better_upper = (
                        same_state
                        and candidate.duration_days >= current.duration_days * 2.2
                        and candidate.upper_touches >= current.upper_touches + 2
                        and candidate.lower_touches >= current.lower_touches
                        and candidate.width_start_pct <= max(current.width_start_pct * 1.35, current.width_start_pct + 12.0)
                        and candidate.width_end_pct <= max(current.width_end_pct * 1.35, current.width_end_pct + 6.0)
                    )
                    if much_longer_with_better_upper:
                        return candidate.score >= current.score * 0.55
                    same_lower_newer_upper_anchor = (
                        same_state
                        and (candidate.breakout_direction or "-") == "-"
                        and candidate.upper_start_date == current.upper_start_date
                        and candidate.lower_start_date == current.lower_start_date
                        and candidate.lower_end_date == current.lower_end_date
                        and candidate.upper_end_date > current.upper_end_date
                        and candidate.upper_touches >= 2
                        and candidate.lower_touches >= current.lower_touches
                        and candidate.width_end_pct <= current.width_end_pct * 1.45
                        and candidate.width_start_pct <= current.width_start_pct * 1.15
                        and candidate.fit_quality >= current.fit_quality * 0.65
                    )
                    if same_lower_newer_upper_anchor:
                        # Prefer the active/recent upper swing-high anchor over an
                        # older steep upper line that later candles merely pierce
                        # within tolerance. Anchor points themselves remain candle
                        # extremes because candidates are built from local highs/lows.
                        return True

                    same_active_structure_longer_top = (
                        same_state
                        and candidate.upper_end_date == current.upper_end_date
                        and candidate.lower_start_date == current.lower_start_date
                        and candidate.lower_end_date == current.lower_end_date
                        and candidate.duration_days >= current.duration_days * 2.2
                        and candidate.upper_touches >= current.upper_touches - 1
                        and candidate.width_start_pct <= max(current.width_start_pct * 1.60, current.width_start_pct + 24.0)
                        and candidate.width_end_pct <= max(current.width_end_pct * 1.50, current.width_end_pct + 7.0)
                    )
                    if same_active_structure_longer_top:
                        # When two valid candidates share the same active lower
                        # boundary and the same recent upper anchor, prefer the
                        # one that starts from the older/higher top.  The regular
                        # fit/width filters above already reject artificial wide
                        # wedges, so do not let raw score keep the scanner pinned
                        # to a tiny late fragment of the same structure.
                        return True
                    current_same_active_structure_longer_top = (
                        same_state
                        and candidate.upper_end_date == current.upper_end_date
                        and candidate.lower_start_date == current.lower_start_date
                        and candidate.lower_end_date == current.lower_end_date
                        and current.duration_days >= candidate.duration_days * 2.2
                        and current.upper_touches >= candidate.upper_touches - 1
                        and current.width_start_pct <= max(candidate.width_start_pct * 1.60, candidate.width_start_pct + 24.0)
                        and current.width_end_pct <= max(candidate.width_end_pct * 1.50, candidate.width_end_pct + 7.0)
                    )
                    if current_same_active_structure_longer_top:
                        return False
                    return candidate.score > current.score

                if _candidate_beats_best(cand, best):
                    best = cand
    return best


def _select_fibo_long_impulse_base(
    w: pd.DataFrame,
    i_peak: int,
    min_incline_days: int,
    log: Callable[[str], None] | None = None,
    stale_cycle_mode: str = "reject",
    max_lookback: int = 140,
    reset_after_sideways: bool = True,
) -> tuple[int, float, float] | None:
    """Select the long Fibo impulse bottom using the regular formation rules."""
    def _log(msg: str) -> None:
        if log is not None:
            log(msg)

    high = pd.to_numeric(w["High"], errors="coerce")
    low = pd.to_numeric(w["Low"], errors="coerce")
    i_start = _select_impulse_start_long(
        w,
        i_peak,
        min_incline_days,
        max_lookback=max_lookback,
        reset_after_sideways=reset_after_sideways,
    )
    if i_start is None or i_peak <= i_start + min_incline_days:
        left_fallback = max(0, i_peak - max_lookback)
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
    # Guard: selected impulse peak should be the dominant high in analyzed window.
    # This prevents anchoring a newer/lower local top while an earlier higher top
    # in the same structure was never fully reset by a proper 61.8 cycle.
    win_peak = int(high.iloc[i_start:i_end + 1].idxmax())
    if win_peak != i_peak:
        _log(
            "Rejected long: selected peak is not dominant in window "
            f"(selected={i_peak}, dominant={win_peak})."
        )
        return None

    # Extend fib-base search left of the selected impulse start.
    # In strong accelerations, impulse-start selector can land on a later pullback
    # while the true swing base is a bit earlier. Widening this local back-scan
    # preserves recency while allowing nearby earlier lows to become the fib anchor.
    orig_i_start = int(i_start)
    pre_start_left = max(0, min(i_start - 15, i_peak - 40))
    fib_start_idx = int(low.iloc[pre_start_left:i_start + 1].idxmin())
    _log(
        f"Long: fib start low searched in [{pre_start_left}, {i_start}] "
        f"(peak_idx={i_peak}) -> idx={fib_start_idx}."
    )
    i_start = fib_start_idx
    fib_start = float(low.iloc[fib_start_idx])
    fib_end = float(high.iloc[i_peak])

    min_reset_impulse_days = 5

    def _reset_to_newer_lower_low(start_idx: int, start_low: float) -> tuple[int, float]:
        reset_right = i_peak - min_reset_impulse_days
        if reset_right <= start_idx:
            return start_idx, start_low
        reset_slice = low.iloc[start_idx + 1:reset_right + 1]
        if not reset_slice.empty:
            reset_idx = int(reset_slice.idxmin())
            reset_low = float(low.iloc[reset_idx])
            if reset_low < start_low:
                _log(
                    "Long: newer lower fib start reset "
                    f"idx={start_idx} low={start_low:.4f} -> "
                    f"idx={reset_idx} low={reset_low:.4f}."
                )
                return reset_idx, reset_low
        return start_idx, start_low

    i_start, fib_start = _reset_to_newer_lower_low(i_start, fib_start)

    # Guard against stale multi-cycle impulses: if a *large enough* earlier
    # formation (after the chosen start, before the chosen peak) already completed
    # a >=61.8 correction, this start is too old. Short one-month-ish cycles are
    # allowed to cross 61.8; bigger cycles must restart after the new bottom.
    min_completed_cycle_days = 32
    max_short_completed_cycle_days = 45
    min_completed_cycle_gain = 0.18

    def _stale_cycle_reset_candidate(start_idx: int, start_low: float) -> tuple[bool, tuple[int, float, int] | None]:
        latest_reset: tuple[int, float, int] | None = None
        scan_left = start_idx + min_completed_cycle_days
        scan_right = max(scan_left, i_peak - 8)
        for p in range(scan_left, scan_right):
            win_l = max(start_idx, p - 4)
            win_r = min(i_peak, p + 5)
            local_peak = float(high.iloc[p]) >= float(high.iloc[win_l:win_r].max())
            dominant_so_far = float(high.iloc[p]) >= float(high.iloc[start_idx:p + 1].max()) * 0.97
            if not (local_peak or dominant_so_far):
                continue
            p_high = float(high.iloc[p])
            p_rng = p_high - start_low
            if p_rng <= 0:
                continue
            completed_days = p - start_idx
            gain_pct = p_rng / max(abs(start_low), 1e-9)
            if completed_days <= max_short_completed_cycle_days or gain_pct < min_completed_cycle_gain:
                continue
            p_fib_618 = p_high - p_rng * 0.618
            post_slice = low.iloc[p:i_peak + 1]
            post_idx = int(post_slice.idxmin())
            post_low = float(low.iloc[post_idx])
            if post_low <= p_fib_618:
                stale_msg_prefix = "Long: stale impulse start" if stale_cycle_mode == "reset" else "Rejected long: stale impulse start"
                _log(
                    f"{stale_msg_prefix} (earlier large formation peak idx={p}, "
                    f"{completed_days}d, gain={gain_pct * 100:.2f}% already corrected below its 61.8)."
                )
                if i_peak > post_idx + min_incline_days:
                    latest_reset = (post_idx, post_low, p)
                else:
                    return True, None
        if latest_reset is not None:
            return True, latest_reset
        return False, None

    stale_cycle, stale_reset = _stale_cycle_reset_candidate(i_start, fib_start)
    if stale_cycle and stale_cycle_mode == "allow":
        _log("Long: broad candidate still rejected because a large completed formation already crossed 61.8; restart after the new bottom.")
    reset_attempts = 0
    while stale_cycle and stale_cycle_mode == "reset" and stale_reset is not None and reset_attempts < 3:
        reset_idx, reset_low, peak_idx = stale_reset
        _log(
            "Long: stale-cycle guard reset impulse start "
            f"(earlier_peak_idx={peak_idx}, idx={i_start} -> {reset_idx})."
        )
        i_start = reset_idx
        fib_start = reset_low
        reset_attempts += 1
        stale_cycle, stale_reset = _stale_cycle_reset_candidate(i_start, fib_start)
    if stale_cycle and i_start != orig_i_start:
        fallback_start = float(low.iloc[orig_i_start])
        _log(
            "Long: widened fib start triggered stale-cycle guard; "
            f"fallback to original impulse start idx={orig_i_start}."
        )
        i_start = orig_i_start
        fib_start = fallback_start
        i_start, fib_start = _reset_to_newer_lower_low(i_start, fib_start)
        stale_cycle, _stale_reset = _stale_cycle_reset_candidate(i_start, fib_start)
    if stale_cycle:
        return None

    return int(i_start), float(fib_start), float(fib_end)

def _find_fibo_3p_steep_setup(df: pd.DataFrame, direction: str = "long", explain: list[str] | None = None) -> FiboScanResult | None:
    """Find a 3P steep-incline candidate independently of 23.6/61.8 pullback rules.

    The regular Fibo scanner intentionally waits for a pullback to at least the
    23.6 retracement (or a 61.8 reversal). The first Trójpolówki Fibo column is
    an incline-quality watchlist: liquid instruments with a current, steep
    impulse, regardless of whether regular second-column pullback checks are
    already relevant.
    """
    def _log(msg: str) -> None:
        if explain is not None:
            explain.append(msg)

    if direction != "long":
        _log("Rejected 3P steep: only long direction is supported.")
        return None
    if len(df) < 80:
        _log("Rejected 3P steep: less than 80 candles.")
        return None

    w = df.tail(320).reset_index(drop=True)
    high = pd.to_numeric(w["High"], errors="coerce")
    low = pd.to_numeric(w["Low"], errors="coerce")
    close = pd.to_numeric(w["Close"], errors="coerce")
    if high.dropna().empty or low.dropna().empty or close.dropna().empty:
        _log("Rejected 3P steep: missing OHLC data.")
        return None

    min_incline_days = 21
    recent_left = max(min_incline_days, len(w) - 35)
    if recent_left >= len(w):
        _log("Rejected 3P steep: not enough recent candles.")
        return None

    global_high = float(high.max())
    i_peak = int(high.iloc[recent_left:].idxmax())
    peak_high = float(high.iloc[i_peak])
    if global_high <= 0 or peak_high < global_high * 0.97:
        _log("Rejected 3P steep: recent high is not near the dominant high.")
        return None

    base = _select_fibo_long_impulse_base(
        w,
        i_peak,
        min_incline_days,
        _log,
        stale_cycle_mode="reset",
        max_lookback=260,
        reset_after_sideways=False,
    )
    if base is None:
        return None
    i_start, fib_start, fib_end = base

    incline_days = i_peak - i_start
    if incline_days < min_incline_days:
        _log("Rejected 3P steep: incline shorter than 21 sessions.")
        return None

    early_sideways = _early_sideways_after_anchor_window(w, i_start, direction="long")
    if early_sideways is not None:
        s_idx, e_idx, hi, lo, rng_pct, progress_pct = early_sideways
        start_date = str(pd.to_datetime(w.iloc[s_idx]["Date"]).date())
        end_date = str(pd.to_datetime(w.iloc[e_idx]["Date"]).date())
        _log(
            "Rejected 3P steep: anchor is followed by a flat month instead of an immediate incline. "
            f"window={s_idx}-{e_idx} ({start_date}..{end_date}), "
            f"hi={hi:.2f}, lo={lo:.2f}, range_pct={rng_pct * 100:.2f}%, progress={progress_pct * 100:.2f}%."
        )
        return None

    # The 3P steep column is an incline-quality watchlist, not a pullback
    # scanner.  Do not reject a multi-month uptrend just because it paused in a
    # tight consolidation for a few weeks; names like PCO should remain visible
    # while they keep making current highs.  The regular Fibo scanner below still
    # applies stricter sideways/correction filters for pullback setups.
    if _has_long_sideways(w.iloc[i_start:i_peak + 1], max_days=45, band_pct=0.035):
        _log("3P steep: impulse has a very tight pause, but keeping current-high incline watchlist candidate.")

    rng = fib_end - fib_start
    if rng <= 0:
        _log("Rejected 3P steep: non-positive range.")
        return None

    fib_236 = fib_end - rng * 0.236
    fib_382 = fib_end - rng * 0.382
    fib_618 = fib_end - rng * 0.618
    current_close = float(close.iloc[-1])

    # Route to the 23.6 warning column only when the newest long close is
    # actually under 23.6 and still very close to that line. If price is still
    # above 23.6, keep it as a pure first-column steep incline.
    band_236_to_618 = max(abs(fib_236 - fib_618), 1e-9)
    progress_to_618 = (fib_236 - current_close) / band_236_to_618
    reached_618_after_peak = bool((pd.to_numeric(w["Low"].iloc[i_peak:], errors="coerce") <= fib_618).any())
    if reached_618_after_peak:
        _log("Rejected 3P steep: pullback already touched 61.8; regular pattern rules must handle it.")
        return None
    crossed_23_6 = progress_to_618 >= 0.0

    gain_pct = rng / max(abs(fib_start), 1e-9)
    avg_daily_gain = gain_pct / max(incline_days, 1)
    if gain_pct < 0.18 or avg_daily_gain < 0.003:
        _log(
            "Rejected 3P steep: incline not steep enough "
            f"(gain={gain_pct * 100:.2f}%, avg_daily={avg_daily_gain * 100:.2f}%)."
        )
        return None

    return FiboScanResult(
        ticker="",
        direction="long",
        status=("3p_steep_23_6_zone" if crossed_23_6 else "3p_steep_incline"),
        incline_start_date=str(pd.to_datetime(w.iloc[i_start]["Date"]).date()),
        incline_end_date=str(pd.to_datetime(w.iloc[i_peak]["Date"]).date()),
        incline_duration_days=incline_days,
        decline_end_date=str(pd.to_datetime(w.iloc[-1]["Date"]).date()),
        decline_duration_days=1,
        incline_decline_duration_ratio=round(gain_pct * 100.0, 2),
        fib_23_6=fib_236,
        fib_38_2=fib_382,
        fib_61_8=fib_618,
        first_61_8_touch_date="",
        reversal_pattern_name="none",
        stop_loss=fib_start,
        current_close=current_close,
    )

def _find_fibo_setup(df: pd.DataFrame, direction: str = "long", end_offset: int = 0, explain: list[str] | None = None, stale_cycle_mode: str = "reject", allow_equal_third_close: bool = False) -> FiboScanResult | None:
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
        base = _select_fibo_long_impulse_base(w, i_peak, min_incline_days, _log, stale_cycle_mode=stale_cycle_mode)
        if base is None:
            return None
        i_start, fib_start, fib_end = base
        newer_low_slice = low.iloc[i_start + 1:i_peak + 1]
        if not newer_low_slice.empty:
            newer_low_idx = int(newer_low_slice.idxmin())
            newer_low = float(low.iloc[newer_low_idx])
            if newer_low < fib_start:
                newer_days = i_peak - newer_low_idx
                newer_gain = (fib_end - newer_low) / max(abs(newer_low), 1e-9)
                if newer_days < min_incline_days and newer_gain < 0.30:
                    _log(
                        "Rejected long: newer lower low would be the correct small-Fibo anchor, "
                        f"but the resulting incline is too short/small ({newer_days}d, {newer_gain * 100:.2f}%)."
                    )
                    return None
                _log(
                    "Long: reset fib anchor to newer lower low before peak "
                    f"idx={i_start} low={fib_start:.4f} -> idx={newer_low_idx} low={newer_low:.4f}."
                )
                i_start, fib_start = newer_low_idx, newer_low
        early_sideways = _early_sideways_after_anchor_window(w, i_start, direction="long")
        if early_sideways is not None:
            s_idx, e_idx, hi, lo, rng_pct, progress_pct = early_sideways
            start_date = str(pd.to_datetime(w.iloc[s_idx]["Date"]).date())
            end_date = str(pd.to_datetime(w.iloc[e_idx]["Date"]).date())
            _log(
                "Rejected long: anchor is followed by a flat month instead of an immediate incline. "
                f"window={s_idx}-{e_idx} ({start_date}..{end_date}), "
                f"hi={hi:.2f}, lo={lo:.2f}, range_pct={rng_pct * 100:.2f}%, progress={progress_pct * 100:.2f}%."
            )
            return None
        i_end = len(w) - 1
        later_high = float(pd.to_numeric(high.iloc[i_peak + 1:i_end + 1], errors="coerce").max()) if i_peak + 1 <= i_end else float("nan")
        if pd.notna(later_high) and later_high > fib_end * 1.005:
            _log(
                "Rejected long: later high exceeded selected Fibo peak; "
                f"still an incline/new-high structure (peak={fib_end:.4f}, later_high={later_high:.4f})."
            )
            return None
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
        long_sideways_month = _latest_sideways_window(correction_seg, max_days=30, band_pct=0.20)
        if long_sideways_month is not None:
            s, e, hi, lo, rng_pct = long_sideways_month
            start_date = str(pd.to_datetime(correction_seg.iloc[s]["Date"]).date())
            end_date = str(pd.to_datetime(correction_seg.iloc[e]["Date"]).date())
            _log(
                "Rejected long: correction has a month-long sideways block. "
                f"window={s}-{e} ({start_date}..{end_date}), "
                f"hi={hi:.2f}, lo={lo:.2f}, range_pct={rng_pct * 100:.2f}% <= 20.00%."
            )
            return None
        long_sideways_multiweek = _latest_sideways_window(correction_seg, max_days=42, band_pct=0.35)
        if long_sideways_multiweek is not None:
            s, e, hi, lo, rng_pct = long_sideways_multiweek
            start_date = str(pd.to_datetime(correction_seg.iloc[s]["Date"]).date())
            end_date = str(pd.to_datetime(correction_seg.iloc[e]["Date"]).date())
            _log(
                "Rejected long: correction has a multi-week sideways block. "
                f"window={s}-{e} ({start_date}..{end_date}), "
                f"hi={hi:.2f}, lo={lo:.2f}, range_pct={rng_pct * 100:.2f}% <= 35.00%."
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
                if includes_first_touch and _is_morning_star(w.iloc[i - 2], w.iloc[i - 1], w.iloc[i], fib_618, doji_middle=False, allow_equal_third_close=allow_equal_third_close):
                    pattern = "morning_star"
                    pattern_idx = i
                    break
        if pattern == "none" and touch_idxs:
            for i in range(max(i_peak + 2, touch_idxs[0] + 2), detect_end + 1):
                includes_first_touch = touch_idxs[0] in {i - 2, i - 1, i}
                if includes_first_touch and _is_morning_star(w.iloc[i - 2], w.iloc[i - 1], w.iloc[i], fib_618, doji_middle=True, allow_equal_third_close=allow_equal_third_close):
                    pattern = "morning_doji_star"
                    pattern_idx = i
                    break
        crossed_618 = corr_low <= fib_618
        _log(f"Long pattern={pattern}, crossed_618={crossed_618}, corr_low={corr_low:.4f}, fib_618={fib_618:.4f}")
        if pattern == "none":
            if crossed_618:
                if (i_peak - i_start) <= 45:
                    _log("Long: accepting short completed cycle despite 61.8 cross without pattern.")
                else:
                    _log("Rejected long: large formation crossed 61.8 but no valid pattern; next formation must start after the new bottom.")
                    return None
            close_after_peak = pd.to_numeric(w.iloc[i_peak:i_end + 1]["Close"], errors="coerce")
            below_236_idx = [j for j, v in enumerate(close_after_peak.tolist()) if pd.notna(v) and float(v) < fib_236]
            if below_236_idx:
                after_first_below = close_after_peak.iloc[below_236_idx[0] + 1:].tolist()
                first_back_above_idx = next(
                    (j for j, v in enumerate(after_first_below) if pd.notna(v) and float(v) > fib_236),
                    None,
                )
                if first_back_above_idx is not None:
                    returned_below_again = any(
                        pd.notna(v) and float(v) < fib_236
                        for v in after_first_below[first_back_above_idx + 1:]
                    )
                    if not returned_below_again:
                        _log("Rejected long: price closed back above 23.6 after first close below 23.6 and did not return below again.")
                        return None
            if float(close.iloc[-1]) > fib_236:
                _log("Rejected long: current close is above 23.6, so not waiting-for-61.8 anymore.")
                return None
            status = "reached_23_6_waiting_for_61_8" if not crossed_618 else "touched_61_8_no_pattern"
        pattern_start_idx = pattern_idx
        if pattern in {"bullish_engulfing", "bullish_piercing_line", "bullish_harami"}:
            pattern_start_idx = max(i_peak, pattern_idx - 1)
        elif pattern in {"morning_star", "morning_doji_star"}:
            pattern_start_idx = max(i_peak, pattern_idx - 2)
        stop_loss = float(pd.to_numeric(low.iloc[pattern_start_idx:pattern_idx + 1], errors="coerce").min())
        future = w.iloc[pattern_idx + 1:]
        if pattern != "none" and not future.empty and (pd.to_numeric(future["Close"], errors="coerce") < stop_loss).any():
            _log("Rejected long: valid 61.8 pattern was invalidated by a later close below the pattern low.")
            return None
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
    # Anchor short Fibo on the candle with the highest wick, not on the highest close.
    # This keeps scanner anchors on the real visible peak candle (including commodity spikes).
    i_start = int(high.iloc[:-60].idxmax())
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
    short_correction_seg = w.iloc[i_bottom:i_end + 1].reset_index(drop=True)
    if _has_long_sideways(short_correction_seg, max_days=22, band_pct=0.12):
        _log("Rejected short: correction is sideways/flat.")
        return None
    short_sideways_month = _latest_sideways_window(short_correction_seg, max_days=30, band_pct=0.20)
    if short_sideways_month is not None:
        s, e, hi, lo, rng_pct = short_sideways_month
        start_date = str(pd.to_datetime(short_correction_seg.iloc[s]["Date"]).date())
        end_date = str(pd.to_datetime(short_correction_seg.iloc[e]["Date"]).date())
        _log(
            "Rejected short: correction has a month-long sideways block. "
            f"window={s}-{e} ({start_date}..{end_date}), "
            f"hi={hi:.2f}, lo={lo:.2f}, range_pct={rng_pct * 100:.2f}% <= 20.00%."
        )
        return None
    short_sideways_multiweek = _latest_sideways_window(short_correction_seg, max_days=42, band_pct=0.35)
    if short_sideways_multiweek is not None:
        s, e, hi, lo, rng_pct = short_sideways_multiweek
        start_date = str(pd.to_datetime(short_correction_seg.iloc[s]["Date"]).date())
        end_date = str(pd.to_datetime(short_correction_seg.iloc[e]["Date"]).date())
        _log(
            "Rejected short: correction has a multi-week sideways block. "
            f"window={s}-{e} ({start_date}..{end_date}), "
            f"hi={hi:.2f}, lo={lo:.2f}, range_pct={rng_pct * 100:.2f}% <= 35.00%."
        )
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
            if includes_first_touch and _is_evening_star(w.iloc[i - 2], w.iloc[i - 1], w.iloc[i], fib_618, doji_middle=False, allow_equal_third_close=allow_equal_third_close):
                pattern = "evening_star"
                pattern_idx = i
                break
    if pattern == "none" and touch_idxs:
        for i in range(max(i_bottom + 2, touch_idxs[0] + 2), detect_end + 1):
            includes_first_touch = touch_idxs[0] in {i - 2, i - 1, i}
            if includes_first_touch and _is_evening_star(w.iloc[i - 2], w.iloc[i - 1], w.iloc[i], fib_618, doji_middle=True, allow_equal_third_close=allow_equal_third_close):
                pattern = "evening_doji_star"
                pattern_idx = i
                break
    crossed_618 = corr_high >= fib_618
    _log(f"Short pattern={pattern}, crossed_618={crossed_618}, corr_high={corr_high:.4f}, fib_618={fib_618:.4f}")
    if pattern == "none":
        if crossed_618:
            _log("Rejected short: 61.8 crossed but no valid pattern.")
            return None
        close_after_bottom = pd.to_numeric(w.iloc[i_bottom:i_end + 1]["Close"], errors="coerce")
        above_236_idx = [j for j, v in enumerate(close_after_bottom.tolist()) if pd.notna(v) and float(v) > fib_236]
        if above_236_idx:
            after_first_above = close_after_bottom.iloc[above_236_idx[0] + 1:].tolist()
            first_back_below_idx = next(
                (j for j, v in enumerate(after_first_above) if pd.notna(v) and float(v) < fib_236),
                None,
            )
            if first_back_below_idx is not None:
                returned_above_again = any(
                    pd.notna(v) and float(v) > fib_236
                    for v in after_first_above[first_back_below_idx + 1:]
                )
                if not returned_above_again:
                    _log("Rejected short: price closed back below 23.6 after first close above 23.6 and did not return above again.")
                    return None
        if float(close.iloc[-1]) < fib_236:
            _log("Rejected short: current close is below 23.6, so not waiting-for-61.8 anymore.")
            return None
        status = "reached_23_6_waiting_for_61_8" if not crossed_618 else "touched_61_8_no_pattern"
    pattern_start_idx = pattern_idx
    if pattern in {"bearish_engulfing", "bearish_harami", "dark_cloud_cover"}:
        pattern_start_idx = max(i_bottom, pattern_idx - 1)
    elif pattern in {"evening_star", "evening_doji_star"}:
        pattern_start_idx = max(i_bottom, pattern_idx - 2)
    stop_loss = float(pd.to_numeric(high.iloc[pattern_start_idx:pattern_idx + 1], errors="coerce").max())
    future = w.iloc[pattern_idx + 1:]
    if pattern != "none" and not future.empty and (pd.to_numeric(future["Close"], errors="coerce") > stop_loss).any():
        _log("Rejected short: valid 61.8 pattern was invalidated by a later close above the pattern high.")
        return None
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
    ichimoku_retest_by_key: dict[tuple[str, str, str, str], str] | None = None,
) -> list[str]:
    print(f"\n{ANSI_BOLD}{ANSI_GREEN}WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns):{ANSI_RESET}")
    if not rows1:
        print("Brak wyników.")
        links = []
    else:
        print(f"{'Ticker':<10} {'Dir':<6} {'Status':<30} {'Pattern':<22} {'Incline':<23} {'Ratio(d)':>16} {'Touched_61.8_date':<16} {'Avg10Turn':>12} {'Near61.8':>10} {'Link':<0}")
        print("-" * 184)
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
            progress_pct = _fibo_retracement_progress_pct(r)
            near_txt = _format_fibo_progress_pct(r)
            near_col = ANSI_GREEN if progress_pct >= 70.0 else (ANSI_YELLOW if progress_pct >= 35.0 else "\033[31m")
        except Exception:
            pass
        print(f"{ANSI_CYAN}{r.ticker:<10}{ANSI_RESET} {r.direction:<6} {color}{r.status:<30}{ANSI_RESET} {r.reversal_pattern_name:<22} {incline:<23} {ratio_txt:>16} {(r.first_61_8_touch_date or '-'): <16} {avg_col}{avg_turn:>12}{ANSI_RESET} {near_col}{near_txt:>10}{ANSI_RESET} {ANSI_CYAN}{link}{ANSI_RESET}")
    print(f"\n{ANSI_BOLD}{ANSI_YELLOW}WYNIKI FIBO #2 (valid pattern up to 2 weeks):{ANSI_RESET}")
    if not rows2:
        print("Brak wyników.")
        return links
    print(f"{'Ticker':<10} {'Dir':<6} {'Pattern':<22} {'Incline':<23} {'Ratio(d)':>16} {'Touched_61.8_date':<16} {'Avg10Turn':>12} {'Link':<0}")
    print("-" * 144)
    for r in rows2:
        link = _stooq_chart_url(r.ticker)
        if link not in links:
            links.append(link)
        incline = f"{r.incline_start_date}->{r.incline_end_date}"
        ratio_txt = f"{r.incline_duration_days}/{max(r.decline_duration_days,1)} ({r.incline_decline_duration_ratio:.2f}:1)"
        row_key = (r.ticker, r.direction, r.incline_start_date, r.incline_end_date)
        avg_turn = "-"
        if avg_turnover_10d_by_key is not None and row_key in avg_turnover_10d_by_key:
            avg_turn = f"{avg_turnover_10d_by_key[row_key]:,.0f}"
        print(f"{ANSI_CYAN}{r.ticker:<10}{ANSI_RESET} {r.direction:<6} {ANSI_GREEN}{r.reversal_pattern_name:<22}{ANSI_RESET} {incline:<23} {ratio_txt:>16} {(r.first_61_8_touch_date or '-'): <16} {avg_turn:>12} {ANSI_CYAN}{link}{ANSI_RESET}")
    return links


def run_fibo_search(target: str) -> int:
    group_name, members, source, exchange_suffix = _get_members(target)
    _should_refresh_group_data(group_name, members, exchange_suffix)
    print(f"[fibo] grupa={group_name}, liczba instrumentów={len(members)}, źródło={source}")
    current_datetime = datetime.now(UTC)
    commodity_refresh_targets = _commodity_refresh_targets_from_env() if group_name == "commodities" else set()
    rows: list[FiboScanResult] = []
    rows3p_steep: list[FiboScanResult] = []
    wedge_rows: list[WedgeScanResult] = []
    data_source_by_ticker: dict[str, str] = {}
    def _is_valid_reversal_invalidated(df_full: pd.DataFrame, cand: FiboScanResult) -> bool:
        if cand.status != "valid_reversal" or not cand.first_61_8_touch_date:
            return False
        dts = pd.to_datetime(df_full["Date"], errors="coerce")
        try:
            touch_ts = pd.to_datetime(cand.first_61_8_touch_date)
        except Exception:
            return False
        after = df_full.loc[dts > touch_ts]
        if after.empty:
            return False
        close_after = pd.to_numeric(after["Close"], errors="coerce")
        if cand.direction == "long":
            return bool((close_after < float(cand.stop_loss)).any())
        return bool((close_after > float(cand.stop_loss)).any())

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

    def _scan_fibo_one(idx_ticker: tuple[int, str]) -> tuple[int, str, list[FiboScanResult], str | None, str]:
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
        if instrument == "commodity" and group_name != "indexes" and ticker.upper() not in API_METAL_COMMODITIES:
            fetch_symbol = COMMODITY_STOOQ_MAP.get(ticker.upper(), fetch_symbol).upper()
        out_rows: list[FiboScanResult] = []
        try:
            prev_cache_only = os.environ.get("STOCKHELPER_CACHE_ONLY")
            prev_force_refresh = os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH")
            scoped_env = group_name == "commodities" and bool(commodity_refresh_targets)
            if scoped_env:
                if _commodity_refresh_target_matches(ticker, fetch_symbol, commodity_refresh_targets):
                    os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
                    os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
                else:
                    os.environ["STOCKHELPER_CACHE_ONLY"] = "1"
                    os.environ.pop("STOCKHELPER_FORCE_REMOTE_REFRESH", None)
            try:
                df, _, meta = _load_daily_data_with_retries(symbol=fetch_symbol, instrument_type=instrument, persist=True, fetch_older_data=False)
            finally:
                if scoped_env:
                    if prev_cache_only is None:
                        os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
                    else:
                        os.environ["STOCKHELPER_CACHE_ONLY"] = prev_cache_only
                    if prev_force_refresh is None:
                        os.environ.pop("STOCKHELPER_FORCE_REMOTE_REFRESH", None)
                    else:
                        os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = prev_force_refresh
            latest_candle_date = _latest_candle_date_from_df(df)
            expected_latest_session_date = get_expected_latest_session_date(instrument, group_name, current_datetime, fetch_symbol)
            latest_close = float(pd.to_numeric(df["Close"], errors="coerce").dropna().iloc[-1]) if "Close" in df.columns else float("nan")
            wedge = _find_manual_unbroken_wedge_setup(df, ticker) or _find_falling_wedge_setup(df)
            if wedge:
                wedge.ticker = ticker
                wedge.latest_candle_date = latest_candle_date
                wedge.expected_latest_session_date = expected_latest_session_date
                if pd.notna(latest_close):
                    wedge.current_close = latest_close
                out_rows.append(wedge)
            steep_3p = _find_fibo_3p_steep_setup(df, "long")
            if steep_3p:
                steep_3p.ticker = ticker
                if pd.notna(latest_close):
                    steep_3p.current_close = latest_close
                steep_3p.latest_candle_date = latest_candle_date
                steep_3p.expected_latest_session_date = expected_latest_session_date
                out_rows.append(steep_3p)
            # Try multiple end offsets so older (but still recent) valid formations are not missed.
            long_candidates: list[FiboScanResult] = []
            long_offset0 = _find_fibo_setup(df, "long", end_offset=0, allow_equal_third_close=(instrument == "forex"))
            for off in [0, 5, 10, 15, 20, 30, 40]:
                cand = _find_fibo_setup(df, "long", end_offset=off, allow_equal_third_close=(instrument == "forex"))
                if cand:
                    long_candidates.append(cand)
                broad_cand = _find_fibo_setup(df, "long", end_offset=off, stale_cycle_mode="allow", allow_equal_third_close=(instrument == "forex"))
                if broad_cand:
                    long_candidates.append(broad_cand)
            if long_candidates:
                long_candidates = [c for c in long_candidates if not _is_waiting_candidate_stale(df, c) and not _is_valid_reversal_invalidated(df, c)]
                # Keep at most three distinct formations, preferring:
                # 1) valid setups over waiting ones,
                # 2) broader setups (earlier incline start),
                # 3) newer setup ends.
                # Do not collapse same-end candidates to only one broad leg: nested
                # formations are useful and should be visible when they differ.
                long_candidates = sorted(
                    long_candidates,
                    key=lambda r: (
                        r.status == "valid_reversal",
                        r.incline_duration_days,
                        r.incline_end_date,
                        r.first_61_8_touch_date,
                    ),
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
                    if len(picked_long) >= 3:
                        break
                for c in picked_long:
                    c.ticker = ticker
                    if pd.notna(latest_close):
                        c.current_close = latest_close
                    c.latest_candle_date = latest_candle_date
                    c.expected_latest_session_date = expected_latest_session_date
                    out_rows.append(c)
            if instrument in {"commodity", "forex"}:
                short_candidates: list[FiboScanResult] = []
                short_offset0 = _find_fibo_setup(df, "short", end_offset=0, allow_equal_third_close=(instrument == "forex"))
                for off in [0, 5, 10, 15, 20, 30, 40]:
                    cand = _find_fibo_setup(df, "short", end_offset=off, allow_equal_third_close=(instrument == "forex"))
                    if cand:
                        short_candidates.append(cand)
                if short_candidates:
                    short_candidates = [c for c in short_candidates if not _is_waiting_candidate_stale(df, c) and not _is_valid_reversal_invalidated(df, c)]
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
                        if len(picked_short) >= 3:
                            break
                    for c in picked_short:
                        c.ticker = ticker
                        if pd.notna(latest_close):
                            c.current_close = latest_close
                        c.latest_candle_date = latest_candle_date
                        c.expected_latest_session_date = expected_latest_session_date
                        out_rows.append(c)
            return idx, ticker, out_rows, None, str((meta or {}).get("source", "unknown"))
        except Exception as exc:
            return idx, ticker, [], _compact_error(str(exc)), "error"

    workers_override = _scan_workers_override()
    if workers_override is not None:
        max_workers = min(max(1, workers_override), len(members))
    elif group_name == "commodities":
        try:
            max_workers = min(max(1, int(os.getenv("STOCKHELPER_COMMODITIES_WORKERS", "1"))), len(members))
        except ValueError:
            max_workers = 1
    else:
        cpu = os.cpu_count() or 4
        auto_workers = max(4, min(cpu * 3, 32))
        max_workers = min(auto_workers, len(members))
    mode = "sequential" if max_workers == 1 else "parallel"
    print(f"[fibo] {mode} mode ({max_workers} workers, bounded queue).")
    indexed_members = list(enumerate(members, start=1))
    next_pos = 0
    pending: dict = {}
    queue_limit = max_workers * 2
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        def _submit_more() -> None:
            nonlocal next_pos
            while next_pos < len(indexed_members) and len(pending) < queue_limit and not STOP_SCAN_EVENT.is_set() and not PAUSE_SCAN_EVENT.is_set():
                idx, ticker = indexed_members[next_pos]
                pending[ex.submit(_scan_fibo_one, (idx, ticker))] = (idx, ticker)
                next_pos += 1
        _submit_more()
        while pending:
            done, _not_done = wait(list(pending.keys()), timeout=0.5, return_when=FIRST_COMPLETED)
            if not done:
                if STOP_SCAN_EVENT.is_set():
                    return 1
                if not PAUSE_SCAN_EVENT.is_set():
                    _submit_more()
                continue
            for fut in done:
                idx, ticker = pending.pop(fut)
                _, _, found, err, data_source = fut.result()
                data_source_by_ticker[ticker] = data_source
                print(f"[{idx}/{len(members)}] fibo {ticker}...", flush=True)
                if err:
                    print(f"  pominięto ({err})", flush=True)
                    if _rate_limit_detected(err) and _should_prompt_rate_limit(group_name):
                        print("[fibo] Network/rate-limit issue detected. Pausing scan for VPN change.", flush=True)
                        PAUSE_SCAN_EVENT.set()
                        if not _prompt_vpn_continue_or_stop():
                            print("[fibo] Scan stopped by user after rate-limit detection.", flush=True)
                            return 1
                for item in found:
                    if isinstance(item, WedgeScanResult):
                        wedge_rows.append(item)
                    elif item.status.startswith("3p_steep"):
                        rows3p_steep.append(item)
                    else:
                        rows.append(item)
            _submit_more()
        if STOP_SCAN_EVENT.is_set():
            return 1
    FIBO_SEARCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_md = _daily_report_path("fibo_search", group_name)
    today_ts = pd.Timestamp(datetime.now(UTC).date())
    valid_recent_cutoff = today_ts - pd.Timedelta(days=14)
    rows0 = [r for r in rows3p_steep if r.status == "3p_steep_incline"]
    rows2 = []
    rows1 = [r for r in rows3p_steep if r.status == "3p_steep_23_6_zone"]
    for r in rows:
        touch_ts = pd.to_datetime(r.first_61_8_touch_date, errors="coerce") if r.first_61_8_touch_date else pd.NaT
        if r.status == "valid_reversal" and r.reversal_pattern_name != "none" and pd.notna(touch_ts):
            if touch_ts >= valid_recent_cutoff:
                rows2.append(r)
            continue
        if r.status == "touched_61_8_no_pattern":
            continue
        if r.direction == "long" and r.status == "reached_23_6_waiting_for_61_8" and r.fib_61_8 <= r.current_close < r.fib_23_6:
            rows1.append(r)
            continue
        if r.direction == "short" and r.status == "reached_23_6_waiting_for_61_8" and r.fib_23_6 <= r.current_close <= r.fib_61_8:
            rows1.append(r)
            continue
    avg_turnover_10d_by_key: dict[tuple[str, str, str, str], float] = {}

    def _fx_to_pln_for_turnover(symbol: str, instrument_type: str) -> float:
        if instrument_type in {"commodity", "forex"}:
            return 1.0
        try:
            cc = _country_code_from_ticker(symbol)
            country_to_currency = {"PL": "PLN", "US": "USD", "DE": "EUR", "FR": "EUR", "CN": "CNY"}
            currency = country_to_currency.get(cc, "USD")
            _, fx_to_pln = get_fx_to_pln_rate_yahoo(currency)
            return float(fx_to_pln) if fx_to_pln and fx_to_pln > 0 else 1.0
        except Exception:
            return 1.0

    def _avg10d_turnover_pln_for_symbol(symbol: str, instrument_type: str) -> float | None:
        try:
            df_l, _, _ = load_or_update_daily_data(symbol=symbol, instrument_type=instrument_type, persist=True)
        except Exception:
            return None
        if "Close" not in df_l.columns or "Volume" not in df_l.columns or len(df_l) < 10:
            return None
        turnover_native = pd.to_numeric(df_l["Close"], errors="coerce") * pd.to_numeric(df_l["Volume"], errors="coerce")
        turnover_native = turnover_native.dropna()
        if len(turnover_native) < 10:
            return None
        fx_to_pln = _fx_to_pln_for_turnover(symbol, instrument_type)
        return float((turnover_native.tail(10) * fx_to_pln).mean())

    def _passes_fibo_liquidity(r: FiboScanResult) -> bool:
        row = rows_by_key.get((r.ticker, r.direction, r.incline_start_date, r.incline_end_date))
        if row is None:
            return False
        symbol, instrument_type = row
        avg_10d_pln = _avg10d_turnover_pln_for_symbol(symbol, instrument_type)
        # Spot metals and several commodity feeds legitimately publish zero or
        # unavailable volume. Do not discard a price-valid technical setup merely
        # because that feed cannot provide a meaningful turnover figure.
        min_avg = 500000.0 * _gdp_multiplier_for_ticker(symbol)
        if not _passes_scanner_liquidity(avg_10d_pln, instrument_type, min_avg):
            return False
        if avg_10d_pln is not None:
            avg_turnover_10d_by_key[(r.ticker, r.direction, r.incline_start_date, r.incline_end_date)] = avg_10d_pln
        return True

    def _passes_wedge_liquidity(r: WedgeScanResult) -> bool:
        row = wedge_source_by_ticker.get(r.ticker)
        if row is None:
            return False
        symbol, instrument_type = row
        avg_10d_pln = _avg10d_turnover_pln_for_symbol(symbol, instrument_type)
        min_avg = 500000.0 * _gdp_multiplier_for_ticker(symbol)
        if not _passes_scanner_liquidity(avg_10d_pln, instrument_type, min_avg):
            return False
        r.avg_turnover_10d_pln = avg_10d_pln
        return True

    rows_by_key: dict[tuple[str, str, str, str], tuple[str, str]] = {}
    wedge_source_by_ticker: dict[str, tuple[str, str]] = {}
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
        if instrument == "commodity" and group_name != "indexes" and ticker.upper() not in API_METAL_COMMODITIES:
            fetch_symbol = COMMODITY_STOOQ_MAP.get(ticker.upper(), fetch_symbol).upper()
        if any(w.ticker == ticker for w in wedge_rows):
            wedge_source_by_ticker[ticker] = (fetch_symbol, instrument)
        for r in rows + rows0:
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
            avg_10d_pln = _avg10d_turnover_pln_for_symbol(symbol, instrument_type)
            if avg_10d_pln is None:
                continue
            avg_turnover_10d_by_key[k] = avg_10d_pln
        except Exception:
            continue

    wedge_rows = [r for r in wedge_rows if _passes_wedge_liquidity(r)]
    rows0_liquid = [r for r in rows0 if _passes_fibo_liquidity(r)]
    rows1_liquid = [r for r in rows1 if _passes_fibo_liquidity(r)]
    rows2_liquid = [r for r in rows2 if _passes_fibo_liquidity(r)]
    rows2_ids = {id(r) for r in rows2_liquid}
    deduped_fibo_rows = _limit_fibo_formations_per_ticker(_dedupe_same_scale_fibo_formations(rows0_liquid + rows1_liquid + rows2_liquid))
    rows0 = [r for r in deduped_fibo_rows if r.status.startswith("3p_steep")]
    rows2 = [r for r in deduped_fibo_rows if id(r) in rows2_ids and not r.status.startswith("3p_steep")]
    rows1 = [r for r in deduped_fibo_rows if not r.status.startswith("3p_steep") and id(r) not in rows2_ids]
    rows0 = sorted(
        rows0,
        key=lambda r: (
            _country_code_from_ticker(r.ticker),
            -float(r.incline_decline_duration_ratio),
            r.ticker,
        ),
        reverse=False,
    )
    rows1 = sorted(
        rows1,
        key=lambda r: (
            -_fibo_retracement_progress_pct(r),
            r.status != "valid_reversal",
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
    rows2_keys = {(r.ticker, r.direction, r.incline_start_date, r.incline_end_date) for r in rows2}
    rows1 = [
        r
        for r in rows1
        if (r.ticker, r.direction, r.incline_start_date, r.incline_end_date) not in rows2_keys
    ]

    ichimoku_retest_by_ticker: dict[tuple[str, str], str] = {}
    ichimoku_retest_by_key: dict[tuple[str, str, str, str], str] = {}
    for r in rows1:
        side = 'long' if r.direction == 'long' else 'short'
        tk = (r.ticker, side)
        if tk not in ichimoku_retest_by_ticker:
            try:
                _, _, flip, _, _ = _scan_one(r.ticker, group_name, exchange_suffix, current_datetime)
                target_side = 'above' if side == 'long' else 'below'
                if flip and flip.current_side == target_side:
                    if flip.valid_retests_count > 0:
                        ichimoku_retest_by_ticker[tk] = f"{flip.retest_status} ({flip.valid_retests_count})"
                    else:
                        ichimoku_retest_by_ticker[tk] = flip.retest_status
                else:
                    ichimoku_retest_by_ticker[tk] = 'no_flip_for_side'
            except Exception:
                ichimoku_retest_by_ticker[tk] = '-'
        ichimoku_retest_by_key[(r.ticker, r.direction, r.incline_start_date, r.incline_end_date)] = ichimoku_retest_by_ticker[tk]

    # Persist terminal-equivalent filtered outputs so external reporters (allsearch)
    # can render exactly the same instrument sets as terminal WYNIKI #0/#1/#2.
    top3_ratio_keys: set[tuple[str, str, str, str]] = {
        (r.ticker, r.direction, r.incline_start_date, r.incline_end_date)
        for r in sorted(rows1 + rows2, key=lambda x: float(x.incline_decline_duration_ratio), reverse=True)[:3]
    }
    rows0_md=[[r.ticker,r.direction,"🚀 3p_steep_incline",f"{r.incline_start_date}->{r.incline_end_date}",f"{r.incline_duration_days}/1 ({r.incline_decline_duration_ratio:.2f}:1)","-",(f"{avg_turnover_10d_by_key.get((r.ticker, r.direction, r.incline_start_date, r.incline_end_date), 0.0):.0f}" if avg_turnover_10d_by_key and avg_turnover_10d_by_key.get((r.ticker, r.direction, r.incline_start_date, r.incline_end_date)) is not None else "-"),_stooq_chart_url(r.ticker),_build_chart_command(r.ticker, 'fibo', r.incline_start_date, r.incline_end_date),_latest_data_marker(r.latest_candle_date, r.expected_latest_session_date),_fmt_optional_date(r.latest_candle_date),_fmt_optional_date(r.expected_latest_session_date)] for r in rows0]
    rows1_md=[[r.ticker,r.direction,("🟢 valid_reversal" if r.status=="valid_reversal" else ("🟡 touched_61_8_no_pattern" if r.status=="touched_61_8_no_pattern" else r.status)),r.reversal_pattern_name,f"{r.incline_start_date}->{r.incline_end_date}",f"{r.incline_duration_days}/{max(r.decline_duration_days,1)} ({r.incline_decline_duration_ratio:.2f}:1)",r.first_61_8_touch_date,(f"{avg_turnover_10d_by_key.get((r.ticker, r.direction, r.incline_start_date, r.incline_end_date), 0.0):.0f}" if avg_turnover_10d_by_key and avg_turnover_10d_by_key.get((r.ticker, r.direction, r.incline_start_date, r.incline_end_date)) is not None else "-"),(_format_fibo_progress_pct(r) if r.status == "reached_23_6_waiting_for_61_8" else "-"),_stooq_chart_url(r.ticker),_build_chart_command(r.ticker, 'fibo', r.incline_start_date, r.incline_end_date),_latest_data_marker(r.latest_candle_date, r.expected_latest_session_date),_fmt_optional_date(r.latest_candle_date),_fmt_optional_date(r.expected_latest_session_date)] for r in rows1]
    rows2_md=[[r.ticker,r.direction,r.reversal_pattern_name,f"{r.incline_start_date}->{r.incline_end_date}",f"{r.incline_duration_days}/{max(r.decline_duration_days,1)} ({r.incline_decline_duration_ratio:.2f}:1)",r.first_61_8_touch_date,(f"{avg_turnover_10d_by_key.get((r.ticker, r.direction, r.incline_start_date, r.incline_end_date), 0.0):.0f}" if avg_turnover_10d_by_key and avg_turnover_10d_by_key.get((r.ticker, r.direction, r.incline_start_date, r.incline_end_date)) is not None else "-"),_stooq_chart_url(r.ticker),_build_chart_command(r.ticker, 'fibo', r.incline_start_date, r.incline_end_date),_latest_data_marker(r.latest_candle_date, r.expected_latest_session_date),_fmt_optional_date(r.latest_candle_date),_fmt_optional_date(r.expected_latest_session_date)] for r in rows2]
    wedge_rows = sorted(wedge_rows, key=lambda r: (float(r.score), float(r.width_start_pct), float(r.slope_pct_per_day)), reverse=True)
    rows_wedge_md=[[r.ticker,("🚀 breakout" if r.breakout_direction in {"long", "short"} else "⏳ unbroken"),f"{r.start_date}->{r.end_date}",r.duration_days,f"{(r.duration_days / 21.0):.1f}",f"{r.upper_start_date}@{r.upper_start_price}->{r.upper_end_date}@{r.upper_end_price}",f"{r.lower_start_date}@{r.lower_start_price}->{r.lower_end_date}@{r.lower_end_price}",r.upper_touches,r.lower_touches,f"{r.width_start_pct:.2f}%",f"{r.width_end_pct:.2f}%",r.slope_strength,(r.breakout_date or "-"),(r.breakout_direction or "-"),f"{r.score:.2f}",(f"{r.avg_turnover_10d_pln:.0f}" if r.avg_turnover_10d_pln is not None else "-"),_stooq_chart_url(r.ticker),_build_chart_command(r.ticker, 'wedge', wedge=r),_latest_data_marker(r.latest_candle_date, r.expected_latest_session_date),_fmt_optional_date(r.latest_candle_date),_fmt_optional_date(r.expected_latest_session_date)] for r in wedge_rows]
    _write_md_table(out_md,"WYNIKI FIBO #0 (3P steep incline)",["Ticker","Dir","Status","Incline","Ratio(d)","Near61.8","Avg10d PLN","Link","Python command","Latest data?","Latest date","Expected date"],rows0_md)
    _write_md_table(out_md,"WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)",["Ticker","Dir","Status","Pattern","Incline","Ratio(d)","Touched_61.8_date","Avg10d PLN","Near61.8","Link","Python command","Latest data?","Latest date","Expected date"],rows1_md, append=True)
    _write_md_table(out_md,"WYNIKI FIBO #2 (valid pattern up to 2 weeks)",["Ticker","Dir","Pattern","Incline","Ratio(d)","Touched_61.8_date","Avg10d PLN","Link","Python command","Latest data?","Latest date","Expected date"],rows2_md, append=True)
    _write_md_table(out_md,"WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)",["Ticker","Status","Wedge","Days","Months","Upper line","Lower line","Upper touches","Lower touches","Start width","End width","Slope","Breakout date","Breakout direction","Score","Avg10d PLN","Link","Python command","Latest data?","Latest date","Expected date"],rows_wedge_md, append=True)

    links = _print_fibo_results(rows1, rows2, avg_turnover_10d_by_key=avg_turnover_10d_by_key, ichimoku_retest_by_key=ichimoku_retest_by_key)
    print(f"\n[fibo] znaleziono: {len(rows) + len(rows3p_steep)}; kliny: {len(wedge_rows)}")
    print(f"[fibo] md: {out_md}")
    if group_name == "forex":
        _print_forex_source_summary("fibo", members, data_source_by_ticker)
        _forex_csv_health_check(members, data_source_by_ticker)
    if links and os.environ.get("STOCKHELPER_DEFER_OPEN_LINKS") != "1":
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
    if instrument == "commodity" and group_name != "indexes" and ticker.upper() not in API_METAL_COMMODITIES:
        fetch_symbol = COMMODITY_STOOQ_MAP.get(ticker.upper(), fetch_symbol).upper()
    print(f"[fibo-explain] ticker={ticker}, fetch_symbol={fetch_symbol}, instrument={instrument}")
    df, _, _ = _load_daily_data_with_retries(symbol=fetch_symbol, instrument_type=instrument, persist=True, fetch_older_data=False)
    steep_steps: list[str] = []
    steep = _find_fibo_3p_steep_setup(df, "long", explain=steep_steps)
    print(f"\n=== 3P steep incline ===")
    print(f"- {'MATCH' if steep else 'NO MATCH'}")
    if steep:
        print(
            "  "
            f"status={steep.status}, incline={steep.incline_start_date}->{steep.incline_end_date}, "
            f"ratio={steep.incline_decline_duration_ratio:.2f}, close={steep.current_close:.4f}, "
            f"fib23.6={steep.fib_23_6:.4f}, fib61.8={steep.fib_61_8:.4f}"
        )
    for s in steep_steps:
        print(f"    • {s}")
    for direction in (["long", "short"] if instrument in {"commodity", "forex"} else ["long"]):
        print(f"\n=== Direction: {direction} ===")
        for off in [0, 5, 10, 15, 20, 30, 40]:
            steps: list[str] = []
            res = _find_fibo_setup(df, direction, end_offset=off, explain=steps, allow_equal_third_close=(instrument == "forex"))
            print(f"- offset={off}: {'MATCH' if res else 'NO MATCH'}")
            if res:
                print(f"  status={res.status}, pattern={res.reversal_pattern_name}, touch_date={res.first_61_8_touch_date}, close={res.current_close:.4f}")
            for s in steps:
                print(f"    • {s}")
            if direction == "long":
                broad_steps: list[str] = []
                broad = _find_fibo_setup(df, direction, end_offset=off, explain=broad_steps, stale_cycle_mode="allow", allow_equal_third_close=(instrument == "forex"))
                if broad and (not res or broad.incline_start_date != res.incline_start_date or broad.incline_end_date != res.incline_end_date):
                    print(f"- offset={off} broad: MATCH")
                    print(f"  status={broad.status}, pattern={broad.reversal_pattern_name}, touch_date={broad.first_61_8_touch_date}, close={broad.current_close:.4f}, incline={broad.incline_start_date}->{broad.incline_end_date}")
                    for s in broad_steps:
                        print(f"    • {s}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skaner ichimoku cloud search")
    parser.add_argument("target", help="Nazwa indeksu albo: commodities / forex")
    args = parser.parse_args()
    return run_ichimoku_search(args.target)

ANSI_BOLD = "\033[1m"
ANSI_GREEN = "\033[32m"
ANSI_CYAN = "\033[36m"
ANSI_YELLOW = "\033[33m"
ANSI_RESET = "\033[0m"

if __name__ == "__main__":
    raise SystemExit(main())
