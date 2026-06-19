from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

pd = pytest.importorskip("pandas")
scanner = pytest.importorskip("scanner_search")


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "csv" / "stocks"


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
