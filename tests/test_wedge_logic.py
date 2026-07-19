from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

pd = pytest.importorskip("pandas")
scanner = pytest.importorskip("scanner_search")


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "csv" / "stocks"


def test_price_only_markets_are_not_rejected_for_unusable_turnover():
    assert scanner._passes_scanner_liquidity(0.0, "commodity", 500_000.0)
    assert scanner._passes_scanner_liquidity(None, "commodity", 500_000.0)
    assert scanner._passes_scanner_liquidity(0.0, "forex", 500_000.0)
    assert scanner._passes_scanner_liquidity(None, "forex", 500_000.0)
    assert scanner._passes_scanner_liquidity(1.0, "forex", 500_000.0)
    assert not scanner._passes_scanner_liquidity(0.0, "stock", 500_000.0)


def test_wedge_midpoint_stop_touch_burns_long_breakout():
    upper_a = (0, 100.0)
    upper_b = (10, 90.0)
    lower_a = (0, 70.0)
    lower_b = (10, 70.0)
    # On breakout index 10, midpoint stop is (90 + 70) / 2 = 80.
    highs = [0.0] * 12
    lows = [100.0] * 12
    lows[11] = 80.0

    assert scanner._wedge_probable_stop_touched_after_breakout(
        11, 10, "long", upper_a, upper_b, lower_a, lower_b, highs, lows
    )


def test_wedge_midpoint_stop_touch_burns_short_breakout():
    upper_a = (0, 100.0)
    upper_b = (10, 90.0)
    lower_a = (0, 70.0)
    lower_b = (10, 70.0)
    # On breakdown index 10, midpoint stop is (90 + 70) / 2 = 80.
    highs = [0.0] * 12
    lows = [100.0] * 12
    highs[11] = 80.0

    assert scanner._wedge_probable_stop_touched_after_breakout(
        11, 10, "short", upper_a, upper_b, lower_a, lower_b, highs, lows
    )


def test_wedge_midpoint_stop_ignores_breakout_candle_and_non_touches():
    upper_a = (0, 100.0)
    upper_b = (10, 90.0)
    lower_a = (0, 70.0)
    lower_b = (10, 70.0)
    highs = [0.0] * 12
    lows = [100.0] * 12
    lows[10] = 80.0
    lows[11] = 80.01

    assert not scanner._wedge_probable_stop_touched_after_breakout(
        10, 10, "long", upper_a, upper_b, lower_a, lower_b, highs, lows
    )
    assert not scanner._wedge_probable_stop_touched_after_breakout(
        11, 10, "long", upper_a, upper_b, lower_a, lower_b, highs, lows
    )


def test_dat_wa_falling_wedge_uses_adjusted_anchors_after_burnt_line():
    df = pd.read_csv(DATA_DIR / "DAT_WA.csv")
    latest_rows = pd.read_csv(StringIO(
        "Date,Open,High,Low,Close,Volume\n"
        "2026-06-15,118.4,119.4,114.6,115.0,8496\n"
        "2026-06-16,114.8,127.2,114.6,125.8,20444\n"
        "2026-06-17,129.8,130.0,124.0,124.4,9012\n"
        "2026-06-18,126.0,126.4,119.4,121.8,3250\n"
        "2026-06-19,121.8000030517578,124.0,118.5999984741211,120.0,4306\n"
    ))
    df = pd.concat([df, latest_rows], ignore_index=True)

    setup = scanner._find_falling_wedge_setup(df)

    assert setup is not None
    assert setup.upper_start_date == "2026-03-11"
    assert setup.upper_end_date == "2026-06-02"
    assert setup.lower_end_date == "2026-06-10"
    assert setup.lower_end_date != "2026-05-20"


def test_bmc_wa_falling_wedge_prefers_recent_extreme_upper_anchor():
    df = pd.read_csv(StringIO(
        "Date,Open,High,Low,Close,Volume\n"
        "2026-04-07,22.70,29.40,22.40,28.52,\n"
        "2026-04-08,26.50,27.00,23.40,24.36,\n"
        "2026-04-09,24.80,25.22,24.32,24.76,\n"
        "2026-04-10,24.86,25.00,22.62,24.00,\n"
        "2026-04-13,24.82,25.30,24.04,24.46,\n"
        "2026-04-14,24.44,24.44,23.80,23.92,\n"
        "2026-04-15,23.90,24.30,23.72,24.10,\n"
        "2026-04-16,24.10,24.10,22.82,22.86,\n"
        "2026-04-17,22.86,23.28,21.68,22.38,\n"
        "2026-04-20,22.68,22.98,22.04,22.88,\n"
        "2026-04-21,22.66,22.68,21.70,21.72,\n"
        "2026-04-22,22.00,22.32,21.40,22.00,\n"
        "2026-04-23,21.82,22.64,21.52,21.68,\n"
        "2026-04-24,22.10,22.10,20.80,21.40,\n"
        "2026-04-27,21.42,21.70,19.82,20.50,\n"
        "2026-04-28,20.32,20.88,19.55,20.40,\n"
        "2026-04-29,20.10,20.48,19.86,20.00,\n"
        "2026-04-30,20.20,20.58,20.20,20.48,\n"
        "2026-05-04,20.48,21.58,20.48,20.80,\n"
        "2026-05-05,21.12,23.76,21.12,22.70,\n"
        "2026-05-06,22.74,22.98,20.80,21.40,\n"
        "2026-05-07,21.80,21.86,20.84,21.00,\n"
        "2026-05-08,21.46,21.58,20.10,20.80,\n"
        "2026-05-11,20.98,21.60,20.82,21.20,\n"
        "2026-05-12,21.00,21.00,19.50,20.06,\n"
        "2026-05-13,20.10,20.48,19.60,19.76,\n"
        "2026-05-14,19.90,20.20,19.70,19.90,\n"
        "2026-05-15,19.69,20.00,19.21,19.80,\n"
        "2026-05-18,19.75,19.75,19.04,19.20,\n"
        "2026-05-19,19.28,19.78,19.10,19.28,\n"
        "2026-05-20,19.59,19.59,19.20,19.50,\n"
        "2026-05-21,19.54,19.98,19.20,19.80,\n"
        "2026-05-22,19.85,19.85,19.01,19.15,\n"
        "2026-05-25,19.15,19.45,18.50,18.99,\n"
        "2026-05-26,19.14,19.44,18.80,19.10,\n"
        "2026-05-27,19.20,19.20,18.61,18.90,\n"
        "2026-05-28,18.90,19.51,18.51,18.80,\n"
        "2026-05-29,19.02,19.20,18.50,18.62,\n"
        "2026-06-01,19.00,20.36,18.96,19.45,\n"
        "2026-06-02,19.83,20.60,19.00,19.57,\n"
        "2026-06-03,19.70,19.70,19.14,19.28,\n"
        "2026-06-05,19.28,19.40,18.80,18.82,\n"
        "2026-06-08,18.80,19.10,18.30,18.44,\n"
        "2026-06-09,18.66,18.67,17.60,17.80,\n"
        "2026-06-10,17.80,17.84,16.02,17.46,\n"
        "2026-06-11,17.40,17.68,16.74,17.10,\n"
        "2026-06-12,17.10,17.40,16.83,17.00,\n"
        "2026-06-15,17.00,20.20,16.85,18.10,\n"
        "2026-06-16,18.40,18.40,17.21,17.55,\n"
        "2026-06-17,17.54,18.55,17.00,17.95,\n"
        "2026-06-18,18.34,18.34,17.00,17.82,\n"
        "2026-06-19,17.79,18.30,17.57,17.82,\n"
        "2026-06-22,18.12,18.23,17.02,17.70,\n"
        "2026-06-23,17.48,17.78,17.00,17.49,\n"
        "2026-06-24,17.49,17.49,16.85,16.90,\n"
        "2026-06-25,16.90,17.09,16.51,16.71,\n"
        "2026-06-26,16.89,16.89,15.34,16.23,\n"
        "2026-06-29,16.25,17.50,16.25,16.90,\n"
        "2026-06-30,16.51,17.26,15.97,16.35,\n"
        "2026-07-01,16.21,16.39,15.30,15.86,\n"
        "2026-07-02,15.86,16.40,15.55,16.25,\n"
        "2026-07-03,16.50,16.50,15.92,16.19,\n"
        "2026-07-06,16.19,18.00,16.05,17.21,\n"
        "2026-07-07,17.45,17.45,16.00,16.07,\n"
        "2026-07-08,16.13,16.24,14.98,15.70,\n"
        "2026-07-09,15.79,16.20,15.00,15.52,\n"
        "2026-07-10,15.44,15.85,15.00,15.70,\n"
        "2026-07-13,15.50,16.35,15.45,16.00,\n"
        "2026-07-14,16.24,16.25,15.50,15.85,\n"
        "2026-07-15,15.98,16.26,15.50,15.71,\n"
        "2026-07-16,15.64,16.10,15.24,15.86,\n"
        "2026-07-17,15.85,15.99,15.66,15.68,\n"
    ))

    setup = scanner._find_falling_wedge_setup(df)

    assert setup is not None
    assert setup.upper_start_date == "2026-04-07"
    assert setup.upper_start_price == pytest.approx(29.40)
    assert setup.upper_end_date == "2026-07-06"
    assert setup.upper_end_price == pytest.approx(18.00)
    assert setup.lower_start_date == "2026-06-10"
    assert setup.lower_start_price == pytest.approx(16.02)
    assert setup.lower_end_date == "2026-06-26"
    assert setup.lower_end_price == pytest.approx(15.34)
