from __future__ import annotations

from pathlib import Path

import pytest


pd = pytest.importorskip("pandas")

import scanner_search as scanner


def _fixture(path: str):
    frame = pd.read_csv(Path(path))
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    return frame.reset_index(drop=True)


def test_mstr_broad_short_is_rejected_by_month_side_trends():
    frame = _fixture("data/csv/stocks/MSTR_US.csv")
    explain: list[str] = []

    result = scanner._find_fibo_3p_steep_setup(frame, "short", explain)

    assert result is None
    assert any("completed month-long side trend" in message for message in explain)


def test_ftnt_exceptional_post_base_impulse_survives_loose_month_window():
    frame = _fixture("data/csv/stocks/FTNT_US.csv")
    explain: list[str] = []

    result = scanner._find_fibo_3p_steep_setup(frame, "long", explain)

    assert result is not None
    assert result.incline_start_date == "2026-04-13"
    assert result.incline_end_date == "2026-08-05"
    assert result.status == "3p_steep_incline"
    assert any("monthly pause absorbed" in message for message in explain)


@pytest.mark.parametrize(
    ("path", "direction"),
    [
        ("data/csv/commodities/ZC_F.csv", "long"),
        ("data/csv/forex/USDCAD.csv", "short"),
        ("data/csv/stocks/REGN_US.csv", "long"),
    ],
)
def test_current_steep_moves_survive_an_internal_monthly_pause(path, direction):
    frame = _fixture(path)
    explain: list[str] = []

    result = scanner._find_fibo_3p_steep_setup(frame, direction, explain)

    assert result is not None, "\n".join(explain)
    assert result.direction == direction
    assert result.status in {"3p_steep_incline", "3p_steep_23_6_zone"}


def test_corn_continuation_moves_second_anchor_to_latest_higher_high():
    frame = _fixture("data/csv/commodities/ZC_F.csv")

    result = scanner._find_fibo_setup(frame, "long", end_offset=0)

    assert result is not None
    assert result.status == "3p_steep_incline"
    assert result.incline_end_date == "2026-08-21"
    implied_second_anchor = (float(result.fib_23_6) - 0.236 * float(result.stop_loss)) / 0.764
    assert implied_second_anchor == pytest.approx(509.0)
    assert float(result.fib_23_6) > float(result.fib_61_8)


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


def test_bft_stair_step_shelves_do_not_replace_march_launch_bottom():
    frame = _fixture("data/csv/stocks/BFT_WA.csv").tail(220).reset_index(drop=True)
    peak_idx = int(frame.index[frame["Date"].dt.strftime("%Y-%m-%d") == "2026-08-14"][0])

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=10,
        stale_cycle_mode="reset",
        reset_after_sideways=True,
        reset_after_extended_sideways=True,
    )

    assert base is not None
    start_idx, start_low, peak = base
    assert frame.iloc[start_idx]["Date"].strftime("%Y-%m-%d") == "2026-03-23"
    assert start_low == pytest.approx(3265.00, abs=0.01)
    assert peak == pytest.approx(5695.00, abs=0.01)


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


@pytest.mark.parametrize(
    ("path", "anchors", "expected_status", "expected_pattern"),
    [
        (
            "data/csv/stocks/CDR_WA.csv",
            ("2026-06-26", "2026-08-13"),
            "valid_reversal",
            "bullish_harami",
        ),
        (
            "data/csv/stocks/TXT_WA.csv",
            ("2026-06-08", "2026-08-12"),
            "touched_61_8_no_pattern",
            "none",
        ),
        (
            "data/csv/commodities/XAGUSD.csv",
            ("2026-07-17", "2026-08-28"),
            "reached_23_6_waiting_for_61_8",
            "none",
        ),
    ],
)
def test_fresh_618_watchlist_events_remain_active(path, anchors, expected_status, expected_pattern):
    frame = _fixture(path)

    result = scanner._find_fibo_setup(frame, "long", forced_anchor_dates=anchors)

    assert result is not None
    assert result.status == expected_status
    assert result.reversal_pattern_name == expected_pattern


def test_asb_completed_base_moves_anchor_to_march_local_bottom():
    frame = _fixture("data/csv/stocks/ASB_WA.csv").tail(220).reset_index(drop=True)
    peak_idx = int(frame.index[frame["Date"].dt.strftime("%Y-%m-%d") == "2026-08-13"][0])

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=10,
        stale_cycle_mode="reject",
        max_lookback=200,
        reset_after_sideways=True,
        reset_after_extended_sideways=True,
    )

    assert base is not None
    start_idx, start_low, _peak = base
    assert frame.iloc[start_idx]["Date"].strftime("%Y-%m-%d") == "2026-03-23"
    assert start_low == pytest.approx(38.00, abs=0.01)


def test_waiting_candidate_uses_the_full_three_candle_confirmation_window():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    stale = source[source.index("def _is_waiting_candidate_stale"):source.index("def _scan_fibo_one")]

    assert 'int((dts > first_touch_ts).sum()) > 2' in stale
    assert 'int((dts > first_touch_ts).sum()) >= 2' not in stale


@pytest.mark.parametrize(
    ("path", "expected_start", "expected_end"),
    [
        ("data/csv/commodities/XAGUSD.csv", "2026-07-17", "2026-08-28"),
        ("data/csv/stocks/TXT_WA.csv", "2026-06-08", "2026-08-12"),
        ("data/csv/stocks/CDR_WA.csv", "2026-06-26", "2026-08-13"),
    ],
)
def test_recent_local_anchor_recovery_survives_old_dominant_cycle(path, expected_start, expected_end):
    frame = _fixture(path)

    recovered = scanner._find_recent_fibo_anchor_recoveries(frame)

    assert any(
        row.incline_start_date == expected_start and row.incline_end_date == expected_end
        for row in recovered
    )


def test_one_bar_silver_pullback_is_kept_after_decisively_reaching_23_6():
    frame = _fixture("data/csv/commodities/XAGUSD.csv")

    result = scanner._find_fibo_setup(
        frame,
        "long",
        forced_anchor_dates=("2026-07-17", "2026-08-28"),
    )

    assert result is not None
    assert result.status == "reached_23_6_waiting_for_61_8"
