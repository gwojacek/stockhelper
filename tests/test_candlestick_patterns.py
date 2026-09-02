from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault("numpy", types.SimpleNamespace())
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
chart_loader._merge_yahoo_fresh_candle = lambda *args, **kwargs: None
chart_loader._recent_high_precision_candle_count = lambda *args, **kwargs: 0
chart_loader.YAHOO_RECENT_CANDLE_REBASE_THRESHOLD = 2
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
    _is_bullish_harami,
    _is_bullish_piercing_line,
    _is_bearish_harami,
    _is_bearish_shooting_star,
    _is_bullish_hammer,
    _is_dark_cloud_cover,
    _is_evening_star,
    _is_morning_star,
)


def candle(open_: float, high: float, low: float, close: float) -> dict[str, float]:
    return {"Open": open_, "High": high, "Low": low, "Close": close}


def test_bullish_hammer_requires_long_lower_shadow_and_only_small_upper_wick():
    assert _is_bullish_hammer(candle(10.0, 12.0, 6.0, 11.0))
    assert not _is_bullish_hammer(candle(10.0, 12.1, 6.0, 11.0))
    assert not _is_bullish_hammer(candle(10.0, 12.0, 8.1, 11.0))
    assert _is_bullish_hammer(candle(424.89, 428.05, 402.00, 423.40))


def test_bullish_hammer_allows_doji_hammer_shape():
    assert _is_bullish_hammer(candle(10.0, 10.2, 8.0, 10.0))
    assert not _is_bullish_hammer(candle(10.0, 11.0, 8.0, 10.0))
    assert not _is_bullish_hammer(candle(56.8, 57.7, 55.0, 56.8))


def test_bearish_hammer_mirrors_shadow_rules_and_allows_doji_shape():
    assert _is_bearish_shooting_star(candle(10.0, 14.0, 9.0, 11.0))
    assert not _is_bearish_shooting_star(candle(10.0, 14.0, 8.9, 11.0))
    assert not _is_bearish_shooting_star(candle(10.0, 13.0, 8.2, 10.5))
    assert _is_bearish_shooting_star(candle(10.0, 12.0, 9.8, 10.0))
    assert not _is_bearish_shooting_star(candle(10.0, 12.0, 9.0, 10.0))


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


def test_oil_two_candle_reversal_allows_tiny_futures_open_difference():
    first = candle(95.36, 102.00, 94.89, 100.69)
    second = candle(100.67, 101.19, 95.13, 96.78)

    assert _is_dark_cloud_cover(first, second, 98.05)

    axis = 200.0
    mirrored_first = candle(axis - first["Open"], axis - first["Low"], axis - first["High"], axis - first["Close"])
    mirrored_second = candle(axis - second["Open"], axis - second["Low"], axis - second["High"], axis - second["Close"])
    assert _is_bullish_piercing_line(mirrored_first, mirrored_second, axis - 98.05)


def test_piercing_line_close_must_remain_inside_first_real_body():
    first = candle(10.0, 10.2, 7.8, 8.0)
    valid = candle(7.9, 9.8, 7.7, 9.2)
    closes_above_first_open = candle(7.9, 10.8, 7.7, 10.5)

    assert _is_bullish_piercing_line(first, valid, 8.5)
    assert not _is_bullish_piercing_line(first, closes_above_first_open, 8.5)


def test_usdpln_contained_bullish_body_is_harami_not_piercing_line():
    august_7 = candle(3.734, 3.736, 3.707, 3.717)
    august_10 = candle(3.718, 3.729, 3.716, 3.727)

    assert _is_bullish_harami(august_7, august_10, 3.710)
    assert not _is_bullish_piercing_line(august_7, august_10, 3.710)


def test_dark_cloud_close_must_remain_inside_first_real_body():
    first = candle(8.0, 10.2, 7.8, 10.0)
    valid = candle(10.0, 10.3, 8.2, 8.8)
    closes_below_first_open = candle(10.0, 10.3, 7.2, 7.5)

    assert _is_dark_cloud_cover(first, valid, 9.5)
    assert not _is_dark_cloud_cover(first, closes_below_first_open, 9.5)


def test_intc_dark_cloud_cover_uses_first_candles_cloud_touch():
    first = candle(101.51, 107.57, 100.33, 104.56)
    second = candle(104.48, 106.87, 102.05, 102.50)

    assert _is_dark_cloud_cover(first, second, 103.89, zone_ceiling=121.86)


def test_opl_tiny_bullish_body_is_not_dark_cloud_and_later_harami_is_valid():
    july_15 = candle(14.48, 14.54, 14.38, 14.50)
    july_16 = candle(14.50, 14.50, 14.29, 14.29)
    july_21 = candle(14.62, 14.77, 14.53, 14.77)
    july_22 = candle(14.76, 14.81, 14.53, 14.70)

    assert not _is_dark_cloud_cover(july_15, july_16, 14.40)
    assert _is_bearish_harami(july_21, july_22, 14.60)


def test_cdr_long_lower_wick_bullish_harami_confirms_first_618_touch():
    august_27 = candle(238.00, 238.10, 230.30, 234.00)
    august_28 = candle(236.00, 236.60, 233.40, 236.50)

    assert _is_bullish_harami(august_27, august_28, 233.34)


def test_bullish_harami_rejects_second_body_extending_below_first_body():
    september_1 = candle(98.25, 98.95, 94.00, 95.60)
    september_2 = candle(95.50, 96.85, 94.15, 96.20)

    assert not _is_bullish_harami(september_1, september_2, 95.00)


def test_limit_fibo_formations_keeps_one_small_and_one_big_per_ticker_direction():
    from scanner_search import FiboScanResult, _limit_fibo_formations_per_ticker

    def result(
        start: str,
        days: int,
        stop: float = 100.0,
        fib_23_6: float = 130.0,
        fib_38_2: float = 150.0,
        fib_61_8: float = 180.0,
        status: str = "reached_23_6_waiting_for_61_8",
        direction: str = "short",
    ) -> FiboScanResult:
        return FiboScanResult(
            ticker="COCOA",
            direction=direction,
            status=status,
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

    current_wheat = result("2026-06-15", 29, stop=571.0, fib_23_6=678.151, fib_61_8=624.5755, status="3p_steep_incline")
    limited_with_current_match = _limit_fibo_formations_per_ticker([small, middle, big, current_wheat])

    assert current_wheat in limited_with_current_match
    assert len(limited_with_current_match) == 2

    opposite_direction = result("2026-05-13", 45, direction="long")
    limited_both_directions = _limit_fibo_formations_per_ticker(
        [small, middle, big, current_wheat, opposite_direction]
    )

    assert opposite_direction in limited_both_directions
    assert len(limited_both_directions) == 3


def test_commodities_and_forex_are_not_liquidity_filtered():
    from scanner_search import _passes_scanner_liquidity

    assert _passes_scanner_liquidity(None, "commodity", 1_000_000_000.0)
    assert _passes_scanner_liquidity(0.0, "forex", 1_000_000_000.0)
    assert not _passes_scanner_liquidity(None, "stock", 500000.0)
    assert not _passes_scanner_liquidity(499999.0, "stock", 500000.0)
    assert _passes_scanner_liquidity(500000.0, "stock", 500000.0)


def test_steep_pruning_ignores_wedge_rows():
    from scanner_search import FiboScanResult, WedgeScanResult, _prune_superseded_steep_fibo_rows

    wedge = WedgeScanResult(
        ticker="ABE", start_date="2026-01-01", end_date="2026-07-01", duration_days=120,
        upper_start_date="2026-01-01", upper_start_price=10.0, upper_end_date="2026-07-01", upper_end_price=8.0,
        lower_start_date="2026-01-01", lower_start_price=5.0, lower_end_date="2026-07-01", lower_end_price=6.0,
        upper_touches=2, lower_touches=2, width_start_pct=50.0, width_end_pct=20.0,
        slope_pct_per_day=-0.1, slope_strength="moderate", fit_quality=1.0, recent_proximity_pct=1.0,
        compression_pct=60.0, score=10.0, current_close=7.0,
    )

    assert _prune_superseded_steep_fibo_rows([wedge]) == [wedge]

    def fibo(direction: str, status: str, days: int, sideways: bool) -> FiboScanResult:
        return FiboScanResult(
            ticker="FX", direction=direction, status=status,
            incline_start_date="2026-01-01", incline_end_date="2026-06-01",
            incline_duration_days=days, decline_end_date="2026-07-20",
            decline_duration_days=20, incline_decline_duration_ratio=1.0,
            fib_23_6=1.1, fib_38_2=1.2, fib_61_8=1.3,
            first_61_8_touch_date="", reversal_pattern_name="none",
            stop_loss=1.0, current_close=1.15, has_monthly_sideways=sideways,
        )

    regular_long = fibo("long", "reached_23_6_waiting_for_61_8", 20, False)
    steep_short = fibo("short", "3p_steep_incline", 80, True)
    # A regular formation in the opposite direction must never remove the
    # forming short setup for the same forex ticker.
    assert _prune_superseded_steep_fibo_rows([regular_long, steep_short]) == [regular_long, steep_short]
