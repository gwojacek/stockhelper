from __future__ import annotations

from pathlib import Path

import pytest


pd = pytest.importorskip("pandas")

import scanner_search as scanner


def _fixture(path: str):
    frame = pd.read_csv(Path(path))
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    return frame.reset_index(drop=True)


@pytest.mark.parametrize(
    ("path", "peak_date", "expected_date", "expected_low"),
    [
        ("data/csv/stocks/TXT_WA.csv", "2026-08-12", "2026-06-08", 37.74),
        ("data/csv/indexes/US30.csv", "2026-08-05", "2026-03-30", 45057.28),
        ("data/csv/stocks/TXN_US.csv", "2026-06-22", "2026-03-30", 184.95),
        ("data/csv/stocks/PCO_WA.csv", "2026-08-05", "2026-03-23", 23.62),
    ],
)
def test_long_anchor_retains_genuine_broad_incline_launch(path, peak_date, expected_date, expected_low):
    frame = _fixture(path).tail(320).reset_index(drop=True)
    peak_idx = int(frame.index[frame["Date"].dt.strftime("%Y-%m-%d") == peak_date][0])

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=10,
        stale_cycle_mode="reject",
        max_lookback=260,
        reset_after_sideways=True,
        reset_after_extended_sideways=True,
    )

    assert base is not None
    start_idx, start_low, _peak = base
    assert frame.iloc[start_idx]["Date"].strftime("%Y-%m-%d") == expected_date
    assert start_low == pytest.approx(expected_low, abs=0.01)


def test_pur_completed_channel_drops_immature_post_channel_impulse():
    frame = _fixture("data/csv/stocks/PUR_WA.csv").tail(320).reset_index(drop=True)
    peak_idx = int(frame.index[frame["Date"].dt.strftime("%Y-%m-%d") == "2026-08-10"][0])

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=10,
        stale_cycle_mode="reject",
        max_lookback=260,
        reset_after_sideways=True,
    )

    assert base is None


def test_lin_sustained_side_trend_removes_pre_channel_anchor():
    frame = _fixture("data/csv/stocks/LIN_DE.csv").tail(320).reset_index(drop=True)
    peak_idx = int(frame.index[frame["Date"].dt.strftime("%Y-%m-%d") == "2026-07-07"][0])

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=10,
        stale_cycle_mode="reject",
        max_lookback=260,
        reset_after_sideways=True,
        reset_after_extended_sideways=True,
    )

    if base is not None:
        start_idx, _start_low, _peak = base
        assert frame.iloc[start_idx]["Date"].strftime("%Y-%m-%d") > "2026-06-03"


def test_regular_and_3p_share_completed_channel_reset_helper():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    base = source[source.index("def _select_fibo_long_impulse_base"):source.index("def _find_fibo_3p_steep_setup")]
    steep = source[source.index("def _find_fibo_3p_steep_setup"):source.index("def _find_fibo_setup")]
    assert "_completed_sideways_reset_long" in base
    assert "_completed_sideways_reset_long" in steep
