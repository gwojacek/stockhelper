from __future__ import annotations

from pathlib import Path

import pytest


pd = pytest.importorskip("pandas")

import scanner_search as scanner
from chart_program.level_selector import _snap_fibo_second_anchor_to_extreme


def _fixture(path: str):
    frame = pd.read_csv(Path(path))
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    return frame.reset_index(drop=True)


def test_cri_fibo_second_anchor_snaps_to_true_low_inside_requested_leg():
    frame = _fixture("data/csv/stocks/CRI_WA.csv")
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    start_idx = int(frame.index[dates == "2026-05-29"][0])
    requested_end_idx = int(frame.index[dates == "2026-09-04"][0])

    end_idx = _snap_fibo_second_anchor_to_extreme(
        frame, start_idx, requested_end_idx, is_short=True,
    )

    assert frame.iloc[end_idx]["Date"] == pd.Timestamp("2026-07-30")
    assert float(frame.iloc[end_idx]["Low"]) == pytest.approx(635.0)


def test_single_symbol_reports_use_symbol_scope_instead_of_shared_single_file():
    assert scanner._report_scope_name("single", ["ENA.WA"]) == "ena.wa"
    assert scanner._report_scope_name("wig", ["ENA.WA"]) == "wig"


def test_selected_silver_provider_alias_uses_canonical_xagusd_history():
    group, members, _source, _suffix = scanner._get_members(
        "selected__INSM.US__SI.F__PUR.WA"
    )

    assert group == "selected__insm.us__si.f__pur.wa"
    assert members == ["INSM.US", "SILVER", "PUR.WA"]
    assert scanner._search_fetch_symbol("SILVER", group, None) == (
        "XAGUSD", "commodity",
    )


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
    ("path", "peak_date", "expected_date", "expected_low"),
    [
        ("data/csv/stocks/SNT_WA.csv", "2026-07-15", "2026-06-01", 262.0),
        ("data/csv/commodities/XAGUSD.csv", "2026-08-28", "2026-07-17", 54.778),
    ],
)
def test_base_followed_by_breakout_keeps_lowest_structural_launch(
    path, peak_date, expected_date, expected_low
):
    frame = _fixture(path).tail(220).reset_index(drop=True)
    peak_idx = int(frame.index[frame["Date"].dt.strftime("%Y-%m-%d") == peak_date][0])

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=10,
        stale_cycle_mode="reject",
        max_lookback=140,
        reset_after_sideways=True,
        reset_after_extended_sideways=True,
        allow_independent_peak=True,
    )

    assert base is not None
    start_idx, start_low, _peak = base
    assert frame.iloc[start_idx]["Date"].strftime("%Y-%m-%d") == expected_date
    assert start_low == pytest.approx(expected_low, abs=0.01)


@pytest.mark.parametrize(
    ("path", "old_anchors", "expected_start", "expected_low"),
    [
        (
            "data/csv/stocks/INSM_US.csv",
            ("2026-07-16", "2026-08-06"),
            "2026-08-03",
            96.42,
        ),
        (
            "data/csv/commodities/XAGUSD.csv",
            ("2026-07-08", "2026-08-28"),
            "2026-07-17",
            54.778,
        ),
    ],
)
def test_carried_long_anchor_cannot_skip_a_lower_pre_peak_low(
    path, old_anchors, expected_start, expected_low
):
    frame = _fixture(path)
    explain: list[str] = []

    carried = scanner._find_fibo_setup(
        frame, "long", forced_anchor_dates=old_anchors, explain=explain
    )
    automatic = scanner._find_fibo_setup(frame, "long")

    assert carried is None
    assert any("a lower low occurred after the first anchor" in item for item in explain)
    assert automatic is not None
    assert automatic.incline_start_date == expected_start
    assert float(automatic.stop_loss) == pytest.approx(expected_low, abs=0.01)


def test_pur_anchor_at_start_of_month_range_is_not_preserved_as_launch():
    frame = _fixture("data/csv/stocks/PUR_WA.csv").tail(220).reset_index(drop=True)
    peak_idx = int(frame.index[frame["Date"].dt.strftime("%Y-%m-%d") == "2026-08-10"][0])
    explain: list[str] = []

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=10,
        stale_cycle_mode="reject",
        max_lookback=200,
        reset_after_sideways=True,
        reset_after_extended_sideways=True,
        log=explain.append,
    )

    # The July range starts at the old 2.06 low; that candle is not the launch
    # of August's incline. Until the post-range impulse matures, dropping the
    # candidate is preferable to drawing a false Fibo across the whole range.
    assert base is None


@pytest.mark.parametrize("path", ["data/csv/stocks/1AT_WA.csv", "data/csv/stocks/BHW_WA.csv"])
def test_month_long_post_peak_range_is_not_a_steep_3p_candidate(path):
    frame = _fixture(path)
    explain: list[str] = []

    result = scanner._find_fibo_3p_steep_setup(frame, "long", explain)

    assert result is None


@pytest.mark.parametrize(
    ("path", "peak_date", "expected_stale"),
    [
        ("data/csv/stocks/SNT_WA.csv", "2026-07-15", False),
        ("data/csv/commodities/XAGUSD.csv", "2026-08-28", False),
        ("data/csv/stocks/BHW_WA.csv", "2026-06-24", True),
        ("data/csv/stocks/1AT_WA.csv", "2026-07-14", True),
    ],
)
def test_waiting_staleness_distinguishes_directional_pullback_from_full_range(
    path, peak_date, expected_stale
):
    frame = _fixture(path)
    correction = frame.loc[frame["Date"] > pd.Timestamp(peak_date)]

    assert scanner._waiting_correction_is_stale(correction, "long") is expected_stale


def test_silver_recent_cycle_replaces_obsolete_dominant_high():
    frame = _fixture("data/csv/commodities/XAGUSD.csv").tail(320).reset_index(drop=True)
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    recent_peak = int(frame.index[dates == "2026-08-28"][0])
    old_peak = int(frame.loc[:recent_peak - 1, "High"].idxmax())

    start = scanner._independent_recent_long_base(
        frame, recent_peak, old_peak, min_incline_days=10,
    )
    result = scanner._find_fibo_setup(frame, "long")

    assert start is not None
    assert dates.iloc[start] == "2026-07-17"
    assert float(frame.iloc[start]["Low"]) == pytest.approx(54.778, abs=0.01)
    assert result is not None
    assert result.incline_start_date == "2026-07-17"
    assert result.incline_end_date == "2026-08-28"
    assert result.status == "reached_23_6_waiting_for_61_8"


def test_bdx_sideways_shelf_before_marginal_top_invalidates_harami_fibo():
    frame = _fixture("data/csv/stocks/BDX_WA.csv")
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    start = int(frame.index[dates == "2026-06-11"][0])
    peak = int(frame.index[dates == "2026-08-11"][0])
    impulse = frame.iloc[start:peak + 1]
    explain: list[str] = []

    result = scanner._find_fibo_setup(
        frame,
        "long",
        forced_anchor_dates=("2026-06-11", "2026-08-11"),
        explain=explain,
    )

    assert scanner._impulse_stalls_before_peak(impulse) is True
    assert result is None
    assert any("stalled in a completed month-long side trend" in item for item in explain)


def test_cdr_mature_post_base_leg_is_not_bdx_style_terminal_stall():
    frame = _fixture("data/csv/stocks/CDR_WA.csv")
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    start = int(frame.index[dates == "2026-06-26"][0])
    peak = int(frame.index[dates == "2026-08-13"][0])

    assert scanner._impulse_stalls_before_peak(frame.iloc[start:peak + 1]) is False


@pytest.mark.parametrize(
    ("path", "anchors", "expected_status", "expected_pattern"),
    [
        (
            "data/csv/stocks/TXT_WA.csv",
            ("2026-06-08", "2026-08-12"),
            "touched_61_8_no_pattern",
            "none",
        ),
    ],
)
def test_live_first_touch_and_harami_keep_their_structural_anchors(
    path, anchors, expected_status, expected_pattern
):
    frame = _fixture(path)

    result = scanner._find_fibo_setup(frame, "long", forced_anchor_dates=anchors)

    assert result is not None
    assert result.incline_start_date == anchors[0]
    assert result.incline_end_date == anchors[1]
    assert result.status == expected_status
    assert result.reversal_pattern_name == expected_pattern


def test_cdr_harami_is_dropped_after_later_wick_breaks_pattern_stop():
    frame = _fixture("data/csv/stocks/CDR_WA.csv")
    explain: list[str] = []

    result = scanner._find_fibo_setup(
        frame,
        "long",
        forced_anchor_dates=("2026-06-26", "2026-08-13"),
        explain=explain,
    )

    assert result is None
    assert any("later low below the pattern stop" in item for item in explain)


def test_reversal_stop_uses_candle_extreme_instead_of_close():
    frame = pd.DataFrame(
        [
            {"Date": "2026-08-28", "High": 236.6, "Low": 233.4, "Close": 236.5},
            {"Date": "2026-09-04", "High": 235.5, "Low": 226.0, "Close": 232.0},
        ]
    )

    assert scanner._fibo_reversal_stop_broken(
        frame, "long", "2026-08-28", 230.27
    ) is True


@pytest.mark.parametrize(
    ("path", "peak_date", "expected_start"),
    [
        ("data/csv/stocks/CSCO_US.csv", "2026-06-04", "2026-04-02"),
        ("data/csv/stocks/PZU_WA.csv", "2026-09-04", "2026-06-08"),
    ],
)
def test_post_range_anchor_is_not_left_in_middle_of_incline(
    path, peak_date, expected_start
):
    frame = _fixture(path).tail(320).reset_index(drop=True)
    peak_idx = int(
        frame.index[frame["Date"].dt.strftime("%Y-%m-%d") == peak_date][0]
    )

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=21,
        stale_cycle_mode="reset",
        max_lookback=260,
        reset_after_sideways=False,
        reset_after_extended_sideways=True,
    )

    assert base is not None
    start_idx, _start_low, _peak = base
    assert frame.iloc[start_idx]["Date"] == pd.Timestamp(expected_start)


def test_sbux_sideways_range_spanning_marginal_peak_drops_fibo():
    frame = _fixture("data/csv/stocks/SBUX_US.csv").tail(320).reset_index(drop=True)
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    peak_idx = int(frame.index[dates == "2026-08-13"][0])

    assert scanner._sideways_range_spans_impulse_end(frame, peak_idx) is True

    explain: list[str] = []
    result = scanner._find_fibo_setup(
        frame,
        "long",
        forced_anchor_dates=("2026-06-05", "2026-08-13"),
        explain=explain,
    )
    assert result is None
    assert any("selected high is inside" in item for item in explain)


@pytest.mark.parametrize(
    ("path", "peak_date", "expected_start"),
    [
        ("data/csv/stocks/ADBE_US.csv", "2026-08-28", "2026-06-18"),
        ("data/csv/stocks/SHOP_US.csv", "2026-08-14", "2026-05-14"),
    ],
)
def test_internal_pauses_do_not_replace_coherent_impulse_launch(
    path, peak_date, expected_start
):
    frame = _fixture(path).tail(320).reset_index(drop=True)
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    peak_idx = int(frame.index[dates == peak_date][0])
    explain: list[str] = []

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=21,
        log=explain.append,
        stale_cycle_mode="reset",
        max_lookback=260,
        reset_after_sideways=False,
        reset_after_extended_sideways=True,
    )

    assert base is not None
    assert frame.iloc[base[0]]["Date"] == pd.Timestamp(expected_start)
    assert any("retained coherent structural launch" in item for item in explain)


def test_repeated_monthly_ranges_reset_xtb_to_latest_acceleration_low():
    frame = _fixture("data/csv/stocks/XTB_WA.csv")
    explain: list[str] = []

    result = scanner._find_fibo_3p_steep_setup(frame, "long", explain)

    assert result is not None, "\n".join(explain)
    assert result.incline_start_date == "2026-05-28"
    assert result.incline_end_date == "2026-08-28"
    assert float(result.stop_loss) == pytest.approx(95.45, abs=0.01)
    assert any("confirmed structural launch" in item for item in explain)


def test_regular_fibo_uses_xtb_post_range_structural_launch():
    frame = _fixture("data/csv/stocks/XTB_WA.csv").tail(220).reset_index(drop=True)
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    peak_idx = int(frame.index[dates == "2026-08-28"][0])
    explain: list[str] = []

    base = scanner._select_fibo_long_impulse_base(
        frame,
        peak_idx,
        min_incline_days=10,
        log=explain.append,
        stale_cycle_mode="reset",
        max_lookback=200,
        reset_after_sideways=True,
        sideways_band_pct=0.08,
        reset_after_extended_sideways=True,
    )

    assert base is not None, "\n".join(explain)
    assert frame.iloc[base[0]]["Date"] == pd.Timestamp("2026-05-28")
    assert base[1] == pytest.approx(95.45, abs=0.01)
    assert any("confirmed structural launch" in item for item in explain)


def test_xtb_extended_range_does_not_keep_april_pre_range_anchor():
    frame = _fixture("data/csv/stocks/XTB_WA.csv")
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    start_idx = int(frame.index[dates == "2026-04-07"][0])
    peak_idx = int(frame.index[dates == "2026-08-28"][0])

    launch_idx = scanner._repeated_range_acceleration_launch_long(
        frame,
        start_idx,
        peak_idx,
        min_impulse_days=10,
    )

    assert launch_idx is not None
    assert frame.iloc[launch_idx]["Date"] == pd.Timestamp("2026-05-28")
    assert float(frame.iloc[launch_idx]["Low"]) == pytest.approx(95.45, abs=0.01)


def test_xtb_launch_can_be_inside_last_overlapping_tight_phase(monkeypatch):
    frame = _fixture("data/csv/stocks/XTB_WA.csv")
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    start_idx = int(frame.index[dates == "2026-04-07"][0])
    peak_idx = int(frame.index[dates == "2026-08-28"][0])
    monkeypatch.setattr(
        scanner,
        "_completed_month_side_trend_phases",
        lambda *_args, **_kwargs: [(0, 24), (20, 55)],
    )

    launch_idx = scanner._repeated_range_acceleration_launch_long(
        frame, start_idx, peak_idx, min_impulse_days=10,
    )

    assert launch_idx is not None
    assert frame.iloc[launch_idx]["Date"] == pd.Timestamp("2026-05-28")


def test_hon_current_short_impulse_uses_newest_confirmed_low():
    frame = _fixture("data/csv/stocks/HON_US.csv")

    result = scanner._find_fibo_3p_steep_setup(frame, "short")

    assert result is not None
    assert result.status == "3p_steep_incline"
    assert result.incline_start_date == "2026-07-28"
    assert result.incline_end_date == "2026-09-02"


def test_crj_short_drops_obsolete_bottom_inside_completed_sideways_cycle(monkeypatch):
    frame = _fixture("data/csv/stocks/CRJ_WA.csv")
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    obsolete_bottom = int(frame.index[dates == "2026-06-15"][0])
    monkeypatch.setattr(
        scanner,
        "_select_bottom_short",
        lambda *_args, **_kwargs: obsolete_bottom,
    )
    explain: list[str] = []

    result = scanner._find_fibo_3p_steep_setup(frame, "short", explain)

    assert result is None
    assert any("moved obsolete second anchor to later lower low" in item for item in explain)
    assert any("pullback already reached 61.8" in item for item in explain)


@pytest.mark.parametrize(
    ("path", "expected_start", "expected_end"),
    [
        ("data/csv/stocks/HFG_DE.csv", "2026-07-01", "2026-09-02"),
        ("data/csv/stocks/IFX_DE.csv", "2026-06-22", "2026-08-24"),
    ],
)
def test_short_impulse_keeps_dominant_top_across_lower_highs(
    path, expected_start, expected_end
):
    frame = _fixture(path)

    result = scanner._find_fibo_3p_steep_setup(frame, "short")

    assert result is not None
    assert result.incline_start_date == expected_start
    assert result.incline_end_date == expected_end


def test_hfg_reanchors_after_repeated_short_sideways_shelves():
    frame = _fixture("data/csv/stocks/HFG_DE.csv")
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    bottom_idx = int(frame.index[dates == "2026-09-02"][0])

    start_idx = scanner._select_impulse_start_short(
        frame, bottom_idx, min_days=21, max_lookback=260,
    )

    assert start_idx is not None
    assert frame.iloc[start_idx]["Date"] == pd.Timestamp("2026-07-01")
    assert float(frame.iloc[start_idx]["High"]) == pytest.approx(4.33, abs=0.01)


@pytest.mark.parametrize(
    ("path", "start_date", "bottom_date"),
    [
        ("data/csv/stocks/ENA_WA.csv", "2026-04-08", "2026-07-30"),
        ("data/csv/stocks/LWB_WA.csv", "2026-04-07", "2026-06-24"),
    ],
)
def test_short_bottom_inside_month_sideways_is_not_an_impulse_end(
    path, start_date, bottom_date
):
    frame = _fixture(path)
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    start_idx = int(frame.index[dates == start_date][0])
    bottom_idx = int(frame.index[dates == bottom_date][0])

    assert scanner._short_bottom_is_inside_month_side_trend(
        frame, start_idx, bottom_idx,
    )


def test_hfg_decisive_breakdown_after_old_shelves_keeps_current_bottom():
    frame = _fixture("data/csv/stocks/HFG_DE.csv")
    dates = frame["Date"].dt.strftime("%Y-%m-%d")
    start_idx = int(frame.index[dates == "2026-07-01"][0])
    bottom_idx = int(frame.index[dates == "2026-09-02"][0])

    assert not scanner._short_bottom_is_inside_month_side_trend(
        frame, start_idx, bottom_idx,
    )


@pytest.mark.parametrize(
    "path",
    ["data/csv/stocks/ENA_WA.csv", "data/csv/stocks/LWB_WA.csv"],
)
def test_short_3p_rejects_bottom_inside_month_sideways(path):
    frame = _fixture(path)
    explain: list[str] = []

    result = scanner._find_fibo_3p_steep_setup(frame, "short", explain)

    assert result is None
    assert any("selected bottom is inside" in item for item in explain)


def test_fibo_chart_does_not_forward_pattern_from_before_second_anchor():
    command = scanner._build_chart_command(
        "ADBE.US",
        "fibo",
        "2026-06-18",
        "2026-08-28",
        pattern_date="2026-07-07",
        pattern_name="shooting_star",
    )

    assert "--scanner-pattern-date" not in command
