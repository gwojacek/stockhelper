from __future__ import annotations

import argparse
import csv
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
import math
from importlib import util
from pathlib import Path

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
    "MRB","MSP","MSW","MSZ","NEU","3RG","NTT","NVA","ODL","OTM","PAT","PCE","PEP","PHN","PJP","PLZ","FHB","PRM","PPS","PRC",
    "PRT","QRS","NVG","RBW","RLP","RMK","RNK","RPC","SEL","SFS","SGN","SKA","ONO","SNK","SON","STF","STP","STX","SWG","TOA",
    "TPE","TRN","TSG","AAT","ULM","UNI","VIN","VOT","VOX","VRG","WAS","WIK","WLT","WWL","WXF","ZEP","MGT","ZMT","PGV","ZUE",
    "ZUK","DIG","GVT","OPM","OPN","PGM","SEK","DEL","FEE","CPI","NTC","MAB","MAK","OTS","TLX","TAR","PEN","APE","MFO","BMX",
    "BLO","SVE","CLD","CPR","EAH","GRN","IMS","JRI","MDG","PHR","DAT","SAR","RVU","SNT","VVD","ALL","11B","CSR","TXT","NWG",
    "MRC","ALI","TOR","PWX","BCM","CLC","DGA","MLG","MOJ","MZA","PCR","IFR","EQU","SNX","UNT","UNF","YAN","ZRE","SKH","VGO",
    "CDL","AWM","DEK","WPR","OML","XPL","ECB","ERG","BIP","WP","1AT","PBX","WTN","LKD","ENT","XTB","ARH","APR","KMP","ASM",
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
        currency = "PLN" if cc == "PL" else cc
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


def _scan_one(ticker: str, group_name: str, exchange_suffix: str | None) -> tuple[str, ScanResult | None, FlipResult | None, str | None]:
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
        mapped = COMMODITY_STOOQ_MAP.get(ticker.upper())
        if mapped:
            fetch_symbol = mapped.upper()
            display_symbol = fetch_symbol
        elif group_name == "single":
            canonical = _reverse_stooq_symbol(ticker)
            if canonical:
                display_symbol = canonical

    try:
        df, _, _ = load_or_update_daily_data(symbol=fetch_symbol, instrument_type=instrument, persist=True)
        enriched = _ichimoku(df)
        result = _qualifies(enriched)
        flip = _flip_after_long_respect(enriched)
        if result:
            result.ticker = ticker
            if instrument == "stock":
                metrics = _compute_stock_liquidity_metrics(df, fetch_symbol)
                if metrics is None:
                    return display_symbol, None, flip, "insufficient turnover data"
                avg_10d, below_20d, threshold_10d, threshold_20d = metrics
                result.avg_turnover_10d_pln = avg_10d
                result.low_turnover_days_20d = below_20d
                result.liquidity_threshold_10d_pln = threshold_10d
                result.liquidity_threshold_20d_pln = threshold_20d
                if avg_10d < threshold_10d or below_20d > 2:
                    return display_symbol, None, flip, (
                        f"liquidity filter failed (avg10={avg_10d:.0f} < {threshold_10d:.0f} or below20d={below_20d} > 2)"
                    )
        if flip:
            flip.ticker = ticker
        return display_symbol, result, flip, None
    except Exception as exc:
        return display_symbol, None, None, str(exc)


def _rate_limit_detected(err: str | None) -> bool:
    text = (err or "").lower()
    return "rate limit" in text or "captcha" in text or "przekroczony dzienny limit" in text


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

    return FlipResult("", previous_side, current_side, flip_ts.strftime("%Y-%m-%d"), round(months, 1), float(close.iloc[-1]))


def run_ichimoku_search(target: str) -> int:
    group_name, members, source, exchange_suffix = _get_members(target)
    print(f"[search] grupa={group_name}, liczba instrumentów={len(members)}, źródło={source}")
    results: list[ScanResult] = []
    flip_results: list[FlipResult] = []

    # Probe first symbol for rate limits/captcha; if present use sequential mode, otherwise parallel mode.
    first = members[0]
    print(f"[1/{len(members)}] skanuję {first}...")
    display_symbol, first_result, first_flip, first_err = _scan_one(first, group_name, exchange_suffix)
    print(f"[1/{len(members)}] skanuję {first} ({display_symbol})...")
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
            display_symbol, result, flip, err = _scan_one(ticker, group_name, exchange_suffix)
            print(f"[{offset}/{len(members)}] skanuję {ticker} ({display_symbol})...")
            if err:
                print(f"  pominięto ({err})")
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
                display_symbol, result, flip, err = fut.result()
                print(f"[{idx}/{len(members)}] skanuję {ticker} ({display_symbol})...")
                if err:
                    print(f"  pominięto ({err})")
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

    print("\nWYNIKI (instrumenty spełniające warunki):")
    if not results:
        print("Brak wyników.")
    else:
        print(f"{'Ticker':<10} {'Pozycja':<8} {'Świece':<8} {'Mies.':<6} {'Start':<12} {'Close':>10} {'Avg10d PLN':>14} {'Low<Th20':>10}")
        print("-" * 98)
        for row in sorted(results, key=lambda r: r.respect_days, reverse=True):
            avg_10d = f"{row.avg_turnover_10d_pln:,.0f}" if row.avg_turnover_10d_pln is not None else "-"
            low_20 = str(row.low_turnover_days_20d) if row.low_turnover_days_20d is not None else "-"
            print(f"{row.ticker:<10} {row.side:<8} {row.respect_days:<8} {row.respect_months:<6.1f} {row.start_date:<12} {row.close:>10.4f} {avg_10d:>14} {low_20:>10}")
    print(f"\nZapisano CSV: {out_csv}")
    print(f"Źródło danych CSV instrumentów: {UNIFIED_DATA_DIR}")

    print("\nWYNIKI 2 (po >=4 mies. po jednej stronie, potem wybicie i utrzymanie po drugiej):")
    if not flip_results:
        print("Brak wyników.")
    else:
        print(f"{'Ticker':<10} {'Było':<8} {'Jest':<8} {'Data wybicia':<12} {'Mies. od wybicia':<16} {'Close':>10}")
        print("-" * 78)
        for row in sorted(flip_results, key=lambda r: r.months_since_flip, reverse=True):
            print(f"{row.ticker:<10} {row.previous_side:<8} {row.current_side:<8} {row.flip_date:<12} {row.months_since_flip:<16.1f} {row.close:>10.4f}")

    out_csv_flip = SEARCH_OUTPUT_DIR / f"search_{group_name.lower()}_{datetime.now(UTC).strftime('%Y%m%d')}_flips.csv"
    with out_csv_flip.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ticker", "previous_side", "current_side", "flip_date", "months_since_flip", "close"])
        for row in sorted(flip_results, key=lambda r: r.months_since_flip, reverse=True):
            writer.writerow([row.ticker, row.previous_side, row.current_side, row.flip_date, f"{row.months_since_flip:.1f}", f"{row.close:.4f}"])
    print(f"Zapisano CSV #2: {out_csv_flip}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skaner ichimoku cloud search")
    parser.add_argument("target", help="Nazwa indeksu albo: commodities / forex")
    args = parser.parse_args()
    return run_ichimoku_search(args.target)


if __name__ == "__main__":
    raise SystemExit(main())
