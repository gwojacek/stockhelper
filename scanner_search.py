from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import util
from pathlib import Path

import pandas as pd

from chart_program.chart_loader import load_or_update_daily_data

PROJECT_ROOT = Path(__file__).resolve().parent
INDEX_MEMBERS_FILE = PROJECT_ROOT / "data" / "indices" / "memberships.json"
SEARCH_OUTPUT_DIR = PROJECT_ROOT / "chart_program" / "data" / "search"


@dataclass
class ScanResult:
    ticker: str
    side: str
    respect_days: int
    close: float


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
        return "commodities", _members_from_configs("commodities"), "configs", None
    if normalized in {"forex", "fx"}:
        return "forex", _members_from_configs("forex"), "configs", None

    if INDEX_MEMBERS_FILE.exists():
        payload = json.loads(INDEX_MEMBERS_FILE.read_text(encoding="utf-8"))
        indices = payload.get("indices", {})
        for key, data in indices.items():
            if key.lower() == normalized:
                return key, [x.upper() for x in data.get("tickers", [])], payload.get("source", "local file"), data.get("exchange_suffix")
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

    side_series = pd.Series("inside", index=df.index)
    side_series = side_series.mask(body_high < bottom, "below")
    side_series = side_series.mask(body_low > top, "above")

    last_side = side_series.iloc[-1]
    if last_side not in {"below", "above"}:
        return None

    run = 0
    for value in reversed(side_series.tolist()):
        if value == last_side:
            run += 1
        else:
            break
    if run < min_days:
        return None

    last = df.iloc[-1]
    if last_side == "below":
        if not (last["High"] >= last["cloud_bottom"] and body_high.iloc[-1] <= last["cloud_bottom"]):
            return None
    else:
        if not (last["Low"] <= last["cloud_top"] and body_low.iloc[-1] >= last["cloud_top"]):
            return None

    return ScanResult(ticker="", side=last_side, respect_days=run, close=float(last["Close"]))


def run_search(target: str) -> int:
    group_name, members, source, exchange_suffix = _get_members(target)
    print(f"[search] grupa={group_name}, liczba instrumentów={len(members)}, źródło={source}")
    results: list[ScanResult] = []

    for idx, ticker in enumerate(members, start=1):
        instrument = "forex" if group_name == "forex" else ("commodity" if group_name == "commodities" else "stock")
        fetch_symbol = ticker
        if instrument == "stock" and exchange_suffix and not ticker.endswith(exchange_suffix.upper()):
            fetch_symbol = f"{ticker}{exchange_suffix}"
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
        writer.writerow(["ticker", "side", "respect_days", "close"])
        for row in sorted(results, key=lambda r: r.respect_days, reverse=True):
            writer.writerow([row.ticker, row.side, row.respect_days, f"{row.close:.4f}"])

    print("\nWYNIKI (instrumenty spełniające warunki):")
    if not results:
        print("Brak wyników.")
    else:
        print(f"{'Ticker':<12} {'Pozycja':<8} {'Dni respektu':<14} {'Close':>10}")
        print("-" * 48)
        for row in sorted(results, key=lambda r: r.respect_days, reverse=True):
            print(f"{row.ticker:<12} {row.side:<8} {row.respect_days:<14} {row.close:>10.4f}")
    print(f"\nZapisano CSV: {out_csv}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Skaner ichimoku cloud search")
    parser.add_argument("target", help="Nazwa indeksu albo: commodities / forex")
    args = parser.parse_args()
    return run_search(args.target)


if __name__ == "__main__":
    raise SystemExit(main())
