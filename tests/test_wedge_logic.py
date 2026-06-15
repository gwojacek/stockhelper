from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

pytest.importorskip("pandas")
scanner = pytest.importorskip("scanner_search")


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
