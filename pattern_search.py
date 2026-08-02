from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from chart_program.chart_loader import CSV_DATA_DIR, load_or_update_daily_data
from scanner_search import (
    _get_members,
    _is_bearish_engulfing,
    _is_bearish_harami,
    _is_bearish_shooting_star,
    _is_bullish_engulfing,
    _is_bullish_hammer,
    _is_bullish_harami,
    _is_bullish_piercing_line,
    _is_dark_cloud_cover,
    _is_evening_star,
    _is_morning_star,
    _search_fetch_symbol,
    _stooq_chart_url,
)


PATTERN_OUTPUT_DIR = Path(__file__).resolve().parent / "chart_program" / "data" / "search" / "patterns"


@dataclass(frozen=True)
class PatternDefinition:
    name: str
    icon: str
    candles: int
    direction: str
    detector: Callable[[Sequence[pd.Series]], bool]


@dataclass(frozen=True)
class PatternHit:
    ticker: str
    date: str
    pattern: str
    icon: str
    direction: str
    close: float


def _low(rows: Sequence[pd.Series]) -> float:
    return min(float(row["Low"]) for row in rows)


def _high(rows: Sequence[pd.Series]) -> float:
    return max(float(row["High"]) for row in rows)


# The level-aware predicates are the same predicates used by Fibo/Ichimoku.  A
# boundary level makes their level-touch clause neutral, leaving the candlestick
# geometry unchanged.  This keeps one definition of every named pattern.
PATTERN_CATALOGUE: tuple[PatternDefinition, ...] = (
    PatternDefinition("bullish_hammer", "🔨🟢", 1, "bullish", lambda r: _is_bullish_hammer(r[-1])),
    PatternDefinition("shooting_star", "🌠🔴", 1, "bearish", lambda r: _is_bearish_shooting_star(r[-1])),
    PatternDefinition("bullish_engulfing", "🫂🟢", 2, "bullish", lambda r: _is_bullish_engulfing(r[-2], r[-1], _low(r))),
    PatternDefinition("bearish_engulfing", "🫂🔴", 2, "bearish", lambda r: _is_bearish_engulfing(r[-2], r[-1], _high(r))),
    PatternDefinition("piercing_line", "🗡️🟢", 2, "bullish", lambda r: _is_bullish_piercing_line(r[-2], r[-1], _low(r))),
    PatternDefinition("dark_cloud_cover", "🌑🔴", 2, "bearish", lambda r: _is_dark_cloud_cover(r[-2], r[-1], _high(r))),
    PatternDefinition("bullish_harami", "🤰🟢", 2, "bullish", lambda r: _is_bullish_harami(r[-2], r[-1], _low(r))),
    PatternDefinition("bearish_harami", "🤰🔴", 2, "bearish", lambda r: _is_bearish_harami(r[-2], r[-1], _high(r))),
    PatternDefinition("morning_star", "🌅🟢", 3, "bullish", lambda r: _is_morning_star(r[-3], r[-2], r[-1], _low(r))),
    PatternDefinition("morning_doji_star", "🌅✚🟢", 3, "bullish", lambda r: _is_morning_star(r[-3], r[-2], r[-1], _low(r), doji_middle=True)),
    PatternDefinition("evening_star", "🌇🔴", 3, "bearish", lambda r: _is_evening_star(r[-3], r[-2], r[-1], _high(r))),
    PatternDefinition("evening_doji_star", "🌇✚🔴", 3, "bearish", lambda r: _is_evening_star(r[-3], r[-2], r[-1], _high(r), doji_middle=True)),
)
PATTERN_NAMES = tuple(definition.name for definition in PATTERN_CATALOGUE)


def scan_patterns(
    df: pd.DataFrame,
    lookback: int = 10,
    pattern_names: Sequence[str] | None = None,
) -> tuple[list[tuple[str, PatternDefinition, float]], Counter[str]]:
    required = {"Date", "Open", "High", "Low", "Close"}
    if df is None or df.empty or not required.issubset(df.columns):
        return [], Counter()
    clean = df.copy()
    clean["Date"] = pd.to_datetime(clean["Date"], errors="coerce")
    clean = clean.dropna(subset=list(required)).sort_values("Date").reset_index(drop=True)
    selected = set(pattern_names or PATTERN_NAMES)
    unknown = selected.difference(PATTERN_NAMES)
    if unknown:
        raise ValueError(f"Unknown candlestick pattern(s): {', '.join(sorted(unknown))}")
    catalogue = tuple(definition for definition in PATTERN_CATALOGUE if definition.name in selected)
    hits: list[tuple[str, PatternDefinition, float]] = []
    checked: Counter[str] = Counter()
    start = max(0, len(clean) - max(1, lookback))
    for end in range(start, len(clean)):
        for definition in catalogue:
            if end + 1 < definition.candles:
                continue
            checked[definition.name] += 1
            rows = [clean.iloc[index] for index in range(end + 1 - definition.candles, end + 1)]
            if definition.detector(rows):
                hits.append((clean.iloc[end]["Date"].date().isoformat(), definition, float(clean.iloc[end]["Close"])))
    return hits, checked


def run_pattern_search(target: str, lookback: int = 10, pattern_name: str | None = None) -> int:
    group, members, source, exchange_suffix = _get_members(target)
    selected_catalogue = tuple(
        definition for definition in PATTERN_CATALOGUE
        if pattern_name is None or definition.name == pattern_name
    )
    if not selected_catalogue:
        raise ValueError(f"Unknown candlestick pattern: {pattern_name}. Available: {', '.join(PATTERN_NAMES)}")
    selected_names = tuple(definition.name for definition in selected_catalogue)
    selection_label = pattern_name or "all"
    print(
        f"[patterns] group={group}, instruments={len(members)}, source={source}, "
        f"lookback={lookback}, pattern={selection_label}"
    )
    all_hits: list[PatternHit] = []
    totals: Counter[str] = Counter()
    errors = 0
    for index, ticker in enumerate(members, 1):
        symbol, instrument = _search_fetch_symbol(ticker, group, exchange_suffix)
        try:
            df, _path, _meta = load_or_update_daily_data(symbol, instrument, persist=True)
            hits, checked = scan_patterns(df, lookback, selected_names)
            totals.update(checked)
            for hit_date, definition, close in hits:
                all_hits.append(PatternHit(ticker, hit_date, definition.name, definition.icon, definition.direction, close))
            icons = " ".join(f"{definition.icon} {definition.name}@{hit_date}" for hit_date, definition, _close in hits)
            print(f"[{index}/{len(members)}] {ticker}: {icons or '— no pattern'}")
        except Exception as exc:
            errors += 1
            print(f"[{index}/{len(members)}] {ticker}: ERROR {exc}")

    print("\n[patterns] enumerated detector audit (checks / hits):")
    hit_counts = Counter(hit.pattern for hit in all_hits)
    for definition in selected_catalogue:
        print(f"  {definition.icon} {definition.name}: {totals[definition.name]} / {hit_counts[definition.name]}")

    PATTERN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pattern_stem = f"_{pattern_name}" if pattern_name else ""
    output = PATTERN_OUTPUT_DIR / f"patterns_{group.lower()}{pattern_stem}_{datetime.now().date().isoformat().replace('-', '')}.md"
    lines = [
        f"# Candlestick patterns — {group}", "",
        f"Lookback: last {lookback} completed daily candles. Pattern selection: {selection_label}. Independent of Fibo and Ichimoku.", "",
        "| Icon | Ticker | Completion date | Pattern | Direction | Close | Stooq |",
        "|---|---|---|---|---|---:|---|",
    ]
    for hit in sorted(all_hits, key=lambda item: (item.date, item.ticker, item.pattern), reverse=True):
        lines.append(f"| {hit.icon} | {hit.ticker} | {hit.date} | {hit.pattern} | {hit.direction} | {hit.close:.6g} | {_stooq_chart_url(hit.ticker)} |")
    if not all_hits:
        lines.append("| — | — | — | No patterns found | — | — | — |")
    lines.extend(["", "## Detector audit", "", "| Icon | Pattern | Windows checked | Hits |", "|---|---|---:|---:|"])
    for definition in selected_catalogue:
        lines.append(f"| {definition.icon} | {definition.name} | {totals[definition.name]} | {hit_counts[definition.name]} |")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[patterns] found={len(all_hits)}, errors={errors}, report={output}")
    print(f"[patterns] CSV source={CSV_DATA_DIR}")
    return 0 if errors < len(members) else 1
