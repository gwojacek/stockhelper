from __future__ import annotations

import argparse
import csv
import json
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
    "SG20CASH", "AU200.CASH", "CHN.CASH", "JP225", "NKX", "W20", "WIG20",
    "UK100", "ITA40", "DE40", "DAX", "FRA40", "CAC", "NED25", "AEX",
    "SUI20", "SMI", "SPA35", "IBEX", "EU50",
]


@dataclass
class ScanResult:
    ticker: str
    side: str
    respect_days: int
    close: float
    start_date: str
    respect_months: float




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


def run_search(target: str) -> int:
    group_name, members, source, exchange_suffix = _get_members(target)
    print(f"[search] grupa={group_name}, liczba instrumentów={len(members)}, źródło={source}")
    results: list[ScanResult] = []

    for idx, ticker in enumerate(members, start=1):
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
        if instrument == "stock" and exchange_suffix and not ticker.endswith(exchange_suffix.upper()):
            fetch_symbol = f"{ticker}{exchange_suffix}"
        if instrument == "commodity":
            mapped = COMMODITY_STOOQ_MAP.get(ticker.upper())
            if mapped:
                fetch_symbol = mapped.upper()
        print(f"[{idx}/{len(members)}] skanuję {ticker} ({fetch_symbol})...")
        try:
            df, _, _ = load_or_update_daily_data(symbol=fetch_symbol, instrument_type=instrument, persist=True)
            enriched = _ichimoku(df)
            result = _qualifies(enriched)
            if result:
                result.ticker = ticker
                results.append(result)
        except Exception as exc:
            print(f"  pominięto ({exc})")

    SEARCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = SEARCH_OUTPUT_DIR / f"search_{group_name.lower()}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ticker", "side", "respect_days", "respect_months", "start_date", "close"])
        for row in sorted(results, key=lambda r: r.respect_days, reverse=True):
            writer.writerow([row.ticker, row.side, row.respect_days, f"{row.respect_months:.1f}", row.start_date, f"{row.close:.4f}"])

    print("\nWYNIKI (instrumenty spełniające warunki):")
    if not results:
        print("Brak wyników.")
    else:
        print(f"{'Ticker':<10} {'Pozycja':<8} {'Świece':<8} {'Mies.':<6} {'Start':<12} {'Close':>10}")
        print("-" * 68)
        for row in sorted(results, key=lambda r: r.respect_days, reverse=True):
            print(f"{row.ticker:<10} {row.side:<8} {row.respect_days:<8} {row.respect_months:<6.1f} {row.start_date:<12} {row.close:>10.4f}")
    print(f"\nZapisano CSV: {out_csv}")
    print(f"Źródło danych CSV instrumentów: {UNIFIED_DATA_DIR}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skaner ichimoku cloud search")
    parser.add_argument("target", help="Nazwa indeksu albo: commodities / forex")
    args = parser.parse_args()
    return run_search(args.target)


if __name__ == "__main__":
    raise SystemExit(main())
