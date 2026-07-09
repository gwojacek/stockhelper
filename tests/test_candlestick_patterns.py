from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault("pandas", types.SimpleNamespace(Series=dict, DataFrame=object))

chart_program = types.ModuleType("chart_program")
instrument_detector = types.ModuleType("chart_program.instrument_detector")
instrument_detector.detect_instrument_type = lambda ticker, default=None: default or "stock"
chart_loader = types.ModuleType("chart_program.chart_loader")
chart_loader.CSV_DATA_DIR = Path("data")
chart_loader.STATE_DATA_DIR = Path("data")
chart_loader.COMMODITY_STOOQ_MAP = {}
chart_loader.COMMODITY_YAHOO_MAP = {}
chart_loader.load_or_update_daily_data = lambda *args, **kwargs: None
chart_loader.has_new_remote_data = lambda *args, **kwargs: False
chart_loader.local_csv_path_for_symbol = lambda *args, **kwargs: Path("data/fake.csv")
chart_loader._yahoo_download = lambda *args, **kwargs: None
chart_loader._yahoo_download_window = lambda *args, **kwargs: None
yahoo_finance = types.ModuleType("utilities.yahoo_finance")
yahoo_finance.get_fx_to_pln_rate_yahoo = lambda *args, **kwargs: 1.0
output_silence = types.ModuleType("utilities.output_silence")
output_silence.call_silenced = lambda fn, *args, **kwargs: fn(*args, **kwargs)
sys.modules.setdefault("chart_program", chart_program)
sys.modules.setdefault("chart_program.instrument_detector", instrument_detector)
sys.modules.setdefault("chart_program.chart_loader", chart_loader)
sys.modules.setdefault("utilities.yahoo_finance", yahoo_finance)
sys.modules.setdefault("utilities.output_silence", output_silence)

from scanner_search import (
    _is_bearish_shooting_star,
    _is_bullish_hammer,
    _is_evening_star,
    _is_morning_star,
)


def candle(open_: float, high: float, low: float, close: float) -> dict[str, float]:
    return {"Open": open_, "High": high, "Low": low, "Close": close}


def test_bullish_hammer_requires_lower_shadow_at_least_twice_body_and_allows_upper_shadow_up_to_twice_body():
    assert _is_bullish_hammer(candle(10.0, 12.0, 6.0, 11.0))
    assert not _is_bullish_hammer(candle(10.0, 13.1, 6.0, 11.0))
    assert not _is_bullish_hammer(candle(10.0, 12.0, 8.1, 11.0))


def test_bullish_hammer_allows_doji_hammer_shape():
    assert _is_bullish_hammer(candle(10.0, 10.5, 8.0, 10.0))


def test_bearish_hammer_mirrors_shadow_rules_and_allows_doji_shape():
    assert _is_bearish_shooting_star(candle(10.0, 14.0, 8.0, 11.0))
    assert not _is_bearish_shooting_star(candle(10.0, 14.0, 7.9, 11.0))
    assert not _is_bearish_shooting_star(candle(10.0, 13.0, 8.2, 10.5))
    assert _is_bearish_shooting_star(candle(10.0, 12.0, 9.5, 10.0))


def test_morning_star_requires_middle_body_below_first_and_third_body():
    first = candle(12.0, 12.5, 9.5, 10.0)
    middle = candle(9.0, 9.4, 8.8, 9.2)
    third = candle(9.2, 12.2, 9.0, 11.5)

    assert not _is_morning_star(first, middle, third, 9.0)
    assert _is_morning_star(first, middle, third, 9.0, allow_equal_third_close=True)


def test_evening_star_requires_middle_body_above_first_and_third_body():
    first = candle(10.0, 12.5, 9.8, 12.0)
    middle = candle(13.0, 13.2, 12.8, 12.8)
    third = candle(12.8, 13.0, 9.8, 10.5)

    assert not _is_evening_star(first, middle, third, 13.0)
    assert _is_evening_star(first, middle, third, 13.0, allow_equal_third_close=True)


def test_limit_fibo_formations_keeps_one_small_and_one_big_per_ticker_direction():
    from scanner_search import FiboScanResult, _limit_fibo_formations_per_ticker

    def result(start: str, days: int, stop: float = 100.0, fib_23_6: float = 130.0, fib_38_2: float = 150.0, fib_61_8: float = 180.0) -> FiboScanResult:
        return FiboScanResult(
            ticker="COCOA",
            direction="short",
            status="reached_23_6_waiting_for_61_8",
            incline_start_date=start,
            incline_end_date="2026-03-02",
            incline_duration_days=days,
            decline_end_date="2026-07-08",
            decline_duration_days=80,
            incline_decline_duration_ratio=1.0,
            fib_23_6=fib_23_6,
            fib_38_2=fib_38_2,
            fib_61_8=fib_61_8,
            first_61_8_touch_date="",
            reversal_pattern_name="none",
            stop_loss=stop,
            current_close=160.0,
        )

    small = result("2025-08-25", 129)
    middle = result("2025-08-13", 137)
    big = result("2025-08-12", 138)

    tiny_fast = result("2026-02-20", 8, fib_23_6=110.0, fib_38_2=114.0, fib_61_8=118.0)

    limited = _limit_fibo_formations_per_ticker([small, middle, big, tiny_fast])

    assert limited == [small, big]
