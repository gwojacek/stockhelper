from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
scanner_search = pytest.importorskip("scanner_search")


def test_ichimoku_builds_cloud_without_row_wise_nan_reductions(monkeypatch):
    rows = 120
    prices = pd.Series(range(rows), dtype=float) + 100.0
    df = pd.DataFrame(
        {
            "Open": prices,
            "High": prices + 2.0,
            "Low": prices - 2.0,
            "Close": prices + 1.0,
        }
    )

    def fail_row_reduction(*args, **kwargs):
        raise AssertionError("Ichimoku cloud must not use DataFrame row reductions")

    monkeypatch.setattr(pd.DataFrame, "max", fail_row_reduction)
    monkeypatch.setattr(pd.DataFrame, "min", fail_row_reduction)

    enriched = scanner_search._ichimoku(df)

    assert len(enriched) == rows - 77
    assert (enriched["cloud_top"] >= enriched["cloud_bottom"]).all()


def test_candle_body_bounds_avoid_arg_reductions_and_tolerate_missing_values(monkeypatch):
    df = pd.DataFrame(
        {
            "Open": [10.0, None, 12.0, None],
            "Close": [11.0, 9.0, None, None],
        }
    )

    def fail_row_reduction(*args, **kwargs):
        raise AssertionError("scanner candle bodies must not use DataFrame row reductions")

    monkeypatch.setattr(pd.DataFrame, "max", fail_row_reduction)
    monkeypatch.setattr(pd.DataFrame, "min", fail_row_reduction)

    body_high, body_low = scanner_search._candle_body_bounds(df)

    assert body_high.iloc[:3].tolist() == [11.0, 9.0, 12.0]
    assert body_low.iloc[:3].tolist() == [10.0, 9.0, 12.0]
    assert pd.isna(body_high.iloc[3])
    assert pd.isna(body_low.iloc[3])


def test_finite_extreme_does_not_call_pandas_reductions(monkeypatch):
    values = pd.Series([None, 4.0, 2.0, float("nan"), 7.0])

    def fail_reduction(*_args, **_kwargs):
        raise AssertionError("scanner extremes must not use pandas min/max reductions")

    monkeypatch.setattr(pd.Series, "min", fail_reduction)
    monkeypatch.setattr(pd.Series, "max", fail_reduction)

    assert scanner_search._finite_extreme(values, highest=False) == 2.0
    assert scanner_search._finite_extreme(values, highest=True) == 7.0
    assert scanner_search._finite_extreme(pd.Series([None, float("nan")]), highest=False) is None


def test_flip_date_is_first_close_outside_cloud_not_first_full_body():
    dates = pd.date_range("2026-07-29", periods=8, freq="D")
    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": [8.0, 8.0, 8.0, 8.0, 9.5, 9.8, 10.2, 10.8],
            "High": [8.5, 8.5, 8.5, 8.5, 10.0, 10.6, 10.5, 11.2],
            "Low": [7.5, 7.5, 7.5, 7.5, 9.0, 9.4, 9.4, 10.4],
            # First close above the cloud is followed by an inside-cloud close
            # and then a re-break. The re-break must not replace the flip date.
            "Close": [8.0, 8.0, 8.0, 8.0, 9.5, 10.4, 9.8, 11.0],
            "cloud_top": [10.0] * 8,
            "cloud_bottom": [9.0] * 8,
        }
    )

    flip = scanner_search._flip_after_long_respect(df, min_days=3)

    assert flip is not None
    assert flip.flip_date == "2026-08-03"


def test_gpp_cloud_entry_is_not_reported_as_breakout():
    # GPP's 15-Apr candle entered the cloud. The first actual far-edge close is
    # 21-Apr and must be the date shared by scanner reports and chart metadata.
    dates = pd.to_datetime(
        ["2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17", "2026-04-20", "2026-04-21", "2026-04-22"]
    )
    prefix = 80
    df = pd.DataFrame(
        {
            "Date": list(pd.date_range("2025-12-01", periods=prefix, freq="D")) + list(dates),
            "Open": [35.0] * prefix + [39.19, 40.36, 40.97, 42.10, 42.29, 43.23, 43.84, 44.17],
            "High": [36.0] * prefix + [39.61, 40.88, 41.53, 42.57, 43.55, 43.65, 44.17, 44.17],
            "Low": [34.0] * prefix + [38.53, 39.47, 40.69, 41.91, 41.68, 42.62, 43.41, 42.85],
            "Close": [35.0] * prefix + [39.28, 40.55, 41.53, 42.38, 43.23, 43.23, 43.70, 43.32],
            "cloud_top": [44.0] * prefix + [44.26, 44.26, 44.12, 43.34, 43.34, 43.34, 43.34, 43.25],
            "cloud_bottom": [40.0] * prefix + [40.97, 40.90, 40.60, 39.67, 39.63, 39.23, 38.72, 38.43],
        }
    )

    flip = scanner_search._flip_after_long_respect(df, min_days=70)

    assert flip is not None
    assert flip.flip_date == "2026-04-21"


def test_cloud_retest_exit_does_not_replace_original_breakout_date():
    dates = pd.date_range("2025-09-22", periods=100, freq="B")
    df = pd.DataFrame(
        {
            "Date": dates,
            "Close": [12.0, 11.0] + [8.0] * 98,
            "cloud_top": [11.0] * 100,
            "cloud_bottom": [9.0] * 100,
        }
    )
    # The trend began with the 24-Sep close below the far edge.  Much later it
    # enters the cloud for a retest and exits below again; that exit is not a
    # second breakout.
    df.loc[40, "Close"] = 10.0
    df.loc[41, "Close"] = 8.0

    breakout_idx = scanner_search._find_latest_breakout_idx(df, "below", min_age_days=20)

    assert breakout_idx == 2
    assert df.loc[breakout_idx, "Date"].strftime("%Y-%m-%d") == "2025-09-24"


def test_early_breakout_becomes_standard_after_previous_breakout_anniversary(monkeypatch):
    dates = pd.date_range("2026-01-02", periods=101, freq="B")
    flip_idx = 81
    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": [10.5] + [8.0] * 80 + [11.0] * 20,
            "High": [11.0] + [8.5] * 80 + [11.5] * 20,
            "Low": [10.2] + [7.5] * 80 + [10.5] * 20,
            "Close": [10.5] + [8.0] * 80 + [11.0] * 20,
            "cloud_top": [10.0] * len(dates),
            "cloud_bottom": [9.0] * len(dates),
        }
    )
    anniversary = dates[1] + pd.DateOffset(months=4)
    event_dates = dates[dates >= anniversary][:2]
    monkeypatch.setattr(
        scanner_search,
        "_detect_ichimoku_retest",
        lambda *_args, **_kwargs: (
            "shallow_retest_pattern", "shallow", 2, event_dates[0].strftime("%Y-%m-%d"),
            [(d.strftime("%Y-%m-%d"), "hammer", "shallow") for d in event_dates],
        ),
    )

    flip = scanner_search._flip_after_long_respect(df)

    assert flip is not None
    assert flip.qualification_status == "standard_4m_breakout"
    assert flip.valid_retests_from_date == "-"
    assert flip.valid_retests_count == 2
    assert flip.retest_status == "shallow_retest_pattern"


def test_early_breakout_before_anniversary_keeps_retests_but_is_not_playable(monkeypatch):
    dates = pd.date_range("2026-01-02", periods=86, freq="B")
    flip_idx = 81
    df = pd.DataFrame({
        "Date": dates,
        "Open": [10.5] + [8.0] * 80 + [11.0] * 5,
        "High": [11.0] + [8.5] * 80 + [11.5] * 5,
        "Low": [10.2] + [7.5] * 80 + [10.5] * 5,
        "Close": [10.5] + [8.0] * 80 + [11.0] * 5,
        "cloud_top": [10.0] * 86,
        "cloud_bottom": [9.0] * 86,
    })
    event_date = dates[-1].strftime("%Y-%m-%d")
    monkeypatch.setattr(
        scanner_search, "_detect_ichimoku_retest",
        lambda *_args, **_kwargs: ("shallow_retest_pattern", "shallow", 1, event_date, [(event_date, "bullish_piercing_line", "shallow")]),
    )

    flip = scanner_search._flip_after_long_respect(df)

    assert flip is not None
    assert flip.valid_retests_count == 1
    assert flip.qualification_status == "early_breakout_waiting_until_4m"
    assert flip.valid_retests_from_date == (dates[1] + pd.DateOffset(months=4)).strftime("%Y-%m-%d")
    assert flip.retest_status == "shallow_retest_pattern"


def test_quick_second_breakout_ignores_retests_until_four_months_from_first():
    dates = pd.to_datetime([
        "2026-04-27", "2026-04-28", "2026-05-20", "2026-05-21",
        "2026-08-20", "2026-08-28",
    ])
    df = pd.DataFrame({
        "Date": dates,
        # The first breakout is in the opposite direction, as with CBF:
        # breakdown on April 28, then breakout above on May 21.
        "Close": [10.5, 8.5, 9.5, 10.5, 10.4, 10.4],
        "cloud_top": [10.0] * len(dates),
        "cloud_bottom": [9.0] * len(dates),
    })
    events = [
        ("2026-08-20", "bullish_harami", "shallow"),
        ("2026-08-28", "hammer", "shallow"),
    ]

    qualified, status, valid_from = scanner_search._qualify_retests_after_early_rebreakout(
        df, 3, "above", events
    )

    assert valid_from == "-"
    assert [event[0] for event in qualified] == ["2026-08-20", "2026-08-28"]
    assert status == "standard_4m_breakout"


def test_quick_second_breakout_has_no_valid_retest_before_anniversary():
    dates = pd.to_datetime(["2026-04-27", "2026-04-28", "2026-05-20", "2026-05-21", "2026-08-20"])
    df = pd.DataFrame({
        "Date": dates,
        "Close": [10.5, 8.5, 9.5, 10.5, 10.4],
        "cloud_top": [10.0] * len(dates),
        "cloud_bottom": [9.0] * len(dates),
    })

    qualified, status, valid_from = scanner_search._qualify_retests_after_early_rebreakout(
        df, 3, "above", [("2026-08-20", "bullish_harami", "shallow")]
    )

    assert qualified == [("2026-08-20", "bullish_harami", "shallow")]
    assert valid_from == "2026-08-28"
    assert status == "early_breakout_waiting_until_4m"


def test_previous_breakout_uses_actual_cross_not_later_respect_window_start():
    dates = pd.to_datetime(["2026-02-16", "2026-02-17", "2026-02-26", "2026-06-24", "2026-06-25"])
    df = pd.DataFrame({
        "Date": dates,
        "Close": [10.5, 8.5, 8.4, 9.5, 10.5],
        "cloud_top": [10.0] * len(dates),
        "cloud_bottom": [9.0] * len(dates),
    })

    previous_idx = scanner_search._find_previous_ichimoku_breakout_idx(df, 4, "above")

    assert previous_idx == 1
    assert df.iloc[previous_idx]["Date"].strftime("%Y-%m-%d") == "2026-02-17"
    assert dates[4] >= dates[1] + pd.DateOffset(months=4)


def test_previous_breakout_ignores_later_same_regime_far_edge_recross():
    dates = pd.to_datetime([
        "2026-02-16", "2026-02-17", "2026-05-01", "2026-06-05",
        "2026-06-24", "2026-06-25",
    ])
    df = pd.DataFrame({
        "Date": dates,
        # February 17 establishes the below regime. June 5 only exits the
        # cloud below again after an inside-cloud retest.
        "Close": [10.5, 8.5, 9.5, 8.5, 9.5, 10.5],
        "cloud_top": [10.0] * len(dates),
        "cloud_bottom": [9.0] * len(dates),
    })

    previous_idx = scanner_search._find_previous_ichimoku_breakout_idx(df, 5, "above")

    assert previous_idx == 1
    assert df.iloc[previous_idx]["Date"].strftime("%Y-%m-%d") == "2026-02-17"


def test_retest_ignores_pattern_ending_on_lead_in_candle(monkeypatch):
    dates = pd.date_range("2026-08-01", periods=7, freq="D")
    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": [8.0, 10.5, 10.6, 10.7, 10.8, 10.7, 10.8],
            "High": [8.5, 11.0, 11.1, 11.2, 11.3, 11.1, 11.2],
            "Low": [7.5, 10.2, 10.3, 10.4, 9.8, 10.2, 10.4],
            "Close": [8.0, 10.6, 10.7, 10.8, 10.5, 10.8, 11.0],
            "cloud_top": [10.0] * 7,
            "cloud_bottom": [9.0] * 7,
        }
    )
    lead_in_date = dates[2]
    monkeypatch.setattr(
        scanner_search,
        "_is_bullish_hammer",
        lambda row: pd.Timestamp(row["Date"]) == lead_in_date,
    )
    monkeypatch.setattr(scanner_search, "_is_bullish_engulfing", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_harami", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_piercing_line", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_morning_star", lambda *_args, **_kwargs: False)

    status, _depth, count, _first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="above"
    )

    assert status == "returned_to_cloud_waiting_for_pattern"
    assert count == 0
    assert events == []


def test_outside_confirmation_candle_is_not_counted_as_a_second_retest(monkeypatch):
    dates = pd.date_range("2026-08-01", periods=7, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [8.0, 10.4, 10.6, 10.7, 10.4, 10.3, 10.8],
        "High": [8.5, 10.8, 11.0, 11.1, 10.9, 11.0, 11.2],
        "Low": [7.5, 10.2, 10.3, 10.4, 9.8, 9.9, 10.5],
        "Close": [8.0, 10.6, 10.8, 10.9, 10.4, 10.8, 11.0],
        "cloud_top": [10.0] * 7,
        "cloud_bottom": [9.0] * 7,
    })
    confirmation_date = dates[5]
    monkeypatch.setattr(scanner_search, "_is_bullish_hammer", lambda *_args: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_engulfing", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_harami", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        scanner_search,
        "_is_bullish_piercing_line",
        lambda _previous, current, _level, **_kwargs: pd.Timestamp(current["Date"]) == confirmation_date,
    )
    monkeypatch.setattr(scanner_search, "_is_morning_star", lambda *_args, **_kwargs: False)

    status, _depth, count, _first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="above"
    )

    assert status == "shallow_retest_pattern"
    assert count == 1
    assert events == [(confirmation_date.strftime("%Y-%m-%d"), "bullish_piercing_line", "shallow")]


def test_hammer_after_breakout_is_valid_retest_only_when_hammer_touches_cloud(monkeypatch):
    dates = pd.date_range("2026-08-01", periods=7, freq="D")
    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": [8.0, 10.5, 10.6, 10.7, 10.8, 10.7, 10.8],
            "High": [8.5, 11.0, 11.1, 11.2, 11.3, 11.1, 11.2],
            "Low": [7.5, 10.2, 10.3, 10.4, 9.8, 10.2, 10.4],
            "Close": [8.0, 10.6, 10.7, 10.8, 10.5, 10.8, 11.0],
            "cloud_top": [10.0] * 7,
            "cloud_bottom": [9.0] * 7,
        }
    )
    outside_confirmation_date = dates[5]
    monkeypatch.setattr(
        scanner_search,
        "_is_bullish_hammer",
        lambda row: pd.Timestamp(row["Date"]) == outside_confirmation_date,
    )
    monkeypatch.setattr(scanner_search, "_is_bullish_engulfing", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_harami", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_piercing_line", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_morning_star", lambda *_args, **_kwargs: False)

    status, _depth, count, _first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="above"
    )

    assert status == "returned_to_cloud_waiting_for_pattern"
    assert count == 0
    assert events == []


def test_retest_pattern_must_contain_local_low_since_cloud_entry(monkeypatch):
    dates = pd.date_range("2026-08-14", periods=6, freq="D")
    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": [10.4, 10.5, 10.4, 9.8, 10.2, 10.6],
            "High": [10.8, 10.9, 10.7, 10.2, 10.5, 10.9],
            "Low": [10.2, 10.3, 10.1, 9.2, 9.6, 10.3],
            "Close": [10.5, 10.6, 10.3, 9.7, 10.3, 10.7],
            "cloud_top": [10.0] * 6,
            "cloud_bottom": [9.0] * 6,
        }
    )
    hammer_date = dates[4]
    monkeypatch.setattr(
        scanner_search,
        "_is_bullish_hammer",
        lambda row: pd.Timestamp(row["Date"]) == hammer_date,
    )
    monkeypatch.setattr(scanner_search, "_is_bullish_engulfing", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_harami", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_piercing_line", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_morning_star", lambda *_args, **_kwargs: False)

    status, _depth, count, _first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="above"
    )

    assert status == "invalid_pattern_too_late"
    assert count == 0
    assert events == []


def test_local_low_resets_after_price_exits_and_returns_to_cloud(monkeypatch):
    dates = pd.date_range("2026-08-13", periods=7, freq="D")
    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": [10.4, 10.5, 9.8, 10.5, 10.4, 10.1, 10.6],
            "High": [10.8, 10.9, 10.2, 10.9, 10.8, 10.5, 10.9],
            "Low": [10.2, 10.3, 9.1, 10.3, 10.1, 9.7, 10.3],
            "Close": [10.5, 10.6, 9.8, 10.6, 10.5, 10.3, 10.7],
            "cloud_top": [10.0] * 7,
            "cloud_bottom": [9.0] * 7,
        }
    )
    hammer_date = dates[5]
    monkeypatch.setattr(
        scanner_search,
        "_is_bullish_hammer",
        lambda row: pd.Timestamp(row["Date"]) == hammer_date,
    )
    monkeypatch.setattr(scanner_search, "_is_bullish_engulfing", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_harami", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_piercing_line", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_morning_star", lambda *_args, **_kwargs: False)

    status, depth, count, first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="above"
    )

    assert status == "medium_retest_pattern"
    assert depth == "medium"
    assert count == 1
    assert first_date == hammer_date.strftime("%Y-%m-%d")
    assert events == [(hammer_date.strftime("%Y-%m-%d"), "hammer", "medium")]


def test_mdv_piercing_line_inside_cloud_is_latest_local_low_retest():
    df = pd.DataFrame(
        [
            {"Date": "2026-06-17", "Open": 92.50, "High": 92.50, "Low": 89.00, "Close": 91.00},
            # The flip and an earlier cloud visit are followed by a close back
            # above the cloud, which resets the local-low cycle.
            {"Date": "2026-08-10", "Open": 91.50, "High": 93.64, "Low": 90.62, "Close": 91.84},
            {"Date": "2026-08-11", "Open": 92.50, "High": 94.10, "Low": 91.80, "Close": 93.50},
            {"Date": "2026-08-12", "Open": 93.46, "High": 97.10, "Low": 92.84, "Close": 97.00},
            {"Date": "2026-08-13", "Open": 97.00, "High": 98.38, "Low": 93.02, "Close": 93.60},
            {"Date": "2026-08-14", "Open": 93.60, "High": 93.90, "Low": 92.56, "Close": 92.70},
            {"Date": "2026-08-17", "Open": 93.50, "High": 93.50, "Low": 90.60, "Close": 90.92},
            {"Date": "2026-08-18", "Open": 90.60, "High": 92.82, "Low": 90.56, "Close": 92.50},
            {"Date": "2026-08-19", "Open": 92.40, "High": 92.40, "Low": 90.70, "Close": 92.18},
            {"Date": "2026-08-20", "Open": 92.18, "High": 92.26, "Low": 89.78, "Close": 89.78},
            {"Date": "2026-08-21", "Open": 90.16, "High": 91.50, "Low": 90.16, "Close": 90.56},
        ]
    )
    # On August 18 the piercing close remains inside the Kumo. It need not
    # reclaim cloud_top; closing above cloud_bottom is sufficient for a valid
    # in-cloud retest pattern.
    df["cloud_top"] = [93.0] * len(df)
    df["cloud_bottom"] = [90.0] * len(df)

    status, depth, count, first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="above"
    )

    assert status == "deep_retest_pattern"
    assert depth == "deep"
    assert count == 2
    assert first_date == "2026-08-18"
    assert events == [
        ("2026-08-18", "bullish_piercing_line", "deep"),
        ("2026-08-21", "bullish_harami", "deep"),
    ]


def test_short_retest_prefers_newer_higher_dark_cloud_cover(monkeypatch):
    dates = pd.to_datetime([
        "2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10",
        "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14",
    ])
    df = pd.DataFrame({
        "Date": dates,
        "Open": [94.0, 98.22, 102.33, 98.26, 96.78, 101.33, 101.51, 104.48],
        "High": [96.0, 103.38, 103.66, 100.03, 98.35, 103.16, 107.57, 106.87],
        "Low": [93.0, 95.60, 98.03, 96.30, 95.35, 100.12, 100.33, 102.05],
        "Close": [95.0, 99.81, 101.65, 97.52, 97.71, 100.95, 104.56, 102.50],
        "cloud_top": [108.0] * len(dates),
        "cloud_bottom": [96.0] * len(dates),
    })
    monkeypatch.setattr(scanner_search, "_is_bearish_shooting_star", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bearish_engulfing", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bearish_harami", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        scanner_search, "_is_evening_star",
        lambda _a, _b, current, *_args, **_kwargs: pd.Timestamp(current["Date"]) == dates[3],
    )
    monkeypatch.setattr(
        scanner_search, "_is_dark_cloud_cover",
        lambda _previous, current, *_args, **_kwargs: pd.Timestamp(current["Date"]) == dates[7],
    )

    status, _depth, count, _first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="below"
    )

    assert status.endswith("_retest_pattern")
    assert count == 1
    assert events[-1][0:2] == ("2026-08-14", "dark_cloud_cover")


def test_intc_moving_cloud_detects_later_dark_cloud_cover():
    raw = [
        ("2026-08-03",88.40,91.68,85.62,91.00,101.77,124.14),
        ("2026-08-04",95.24,101.39,94.32,100.86,101.77,124.31),
        ("2026-08-05",99.30,102.83,97.90,101.06,102.16,124.31),
        ("2026-08-06",98.22,103.38,95.60,99.81,103.31,125.27),
        ("2026-08-07",102.33,103.66,98.03,101.65,103.41,125.38),
        ("2026-08-10",98.26,100.03,96.30,97.52,103.41,125.17),
        ("2026-08-11",96.78,98.35,95.35,97.71,103.67,125.17),
        ("2026-08-12",101.33,103.16,100.12,100.95,103.67,122.83),
        ("2026-08-13",101.51,107.57,100.33,104.56,103.89,121.86),
        ("2026-08-14",104.48,106.87,102.05,102.50,110.99,121.86),
    ]
    df = pd.DataFrame(
        raw, columns=["Date", "Open", "High", "Low", "Close", "cloud_bottom", "cloud_top"]
    )
    df["Date"] = pd.to_datetime(df["Date"])

    _status, _depth, count, _first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="below"
    )

    assert count >= 1
    assert events[-1][0:2] == ("2026-08-14", "dark_cloud_cover")


def test_axon_local_low_hammer_is_tagged_as_retest(monkeypatch):
    raw = [
        ("2026-06-09",467.61,479.47,436.36,452.51), ("2026-06-10",448.66,462.99,437.98,447.59),
        ("2026-06-11",444.77,453.15,423.04,446.20), ("2026-06-12",446.89,450.00,427.00,441.73),
        ("2026-06-15",448.72,457.57,434.53,443.21), ("2026-06-16",441.64,448.10,427.00,435.39),
        ("2026-06-17",431.80,442.81,422.11,423.01), ("2026-06-18",424.89,428.05,402.00,423.40),
        ("2026-06-22",417.05,419.03,403.79,410.03), ("2026-06-23",414.44,441.11,414.44,433.04),
        ("2026-06-24",432.27,468.04,429.84,456.73), ("2026-06-25",454.50,466.63,443.00,444.73),
        ("2026-06-26",445.04,477.17,440.00,464.83),
    ]
    df = pd.DataFrame(raw, columns=["Date", "Open", "High", "Low", "Close"])
    df["Date"] = pd.to_datetime(df["Date"])
    df["cloud_top"] = 460.0
    df["cloud_bottom"] = 390.0
    monkeypatch.setattr(scanner_search, "_is_bullish_engulfing", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_harami", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_bullish_piercing_line", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(scanner_search, "_is_morning_star", lambda *_args, **_kwargs: False)

    _status, _depth, count, _first_date, events = scanner_search._detect_ichimoku_retest(
        df, flip_idx=1, current_side="above"
    )

    assert count == 1
    assert events == [("2026-06-18", "hammer", "deep")]


def test_ndx100_members_include_spcx():
    assert "SPCX.US" in scanner_search.NDX100_SEARCH_TICKERS


def test_tk_cross_around_cloud_entry_uses_newest_cross():
    rows = []
    for idx in range(35):
        # Current cloud interaction starts at idx=30. A bullish TK cross at
        # idx=18 is still inside the one-month pre-entry window, but a newer
        # bearish cross at idx=32 should win because the report needs the
        # newest cross around the cloud-entry/retest period.
        in_cloud_touch = idx >= 30
        tenkan = 99.0
        if 18 <= idx < 32:
            tenkan = 102.0
        elif idx >= 32:
            tenkan = 98.0
        rows.append(
            {
                "Open": 105.0 if not in_cloud_touch else 101.0,
                "High": 106.0 if not in_cloud_touch else 103.0,
                "Low": 104.0 if not in_cloud_touch else 99.0,
                "Close": 105.0 if not in_cloud_touch else 101.0,
                "tenkan": tenkan,
                "kijun": 100.0,
                "cloud_top": 102.0,
                "cloud_bottom": 100.0,
                "span_a": 101.0,
                "span_b": 100.0,
            }
        )
    df = pd.DataFrame(rows)

    metrics = scanner_search._ichimoku_extra_metrics(df, "above", "Touched the cloud")

    assert metrics["tk_cross"] == "bearish TK cross"


def test_tk_metric_falls_back_to_current_tenkan_kijun_alignment():
    rows = []
    for idx in range(35):
        rows.append(
            {
                "Open": 27.0,
                "High": 27.3,
                "Low": 26.8,
                "Close": 27.0,
                "tenkan": 27.15,
                "kijun": 27.05,
                "cloud_top": 27.2,
                "cloud_bottom": 26.9,
                "span_a": 27.0,
                "span_b": 27.1,
            }
        )
    df = pd.DataFrame(rows)

    metrics = scanner_search._ichimoku_extra_metrics(df, "below", "shallow_retest_pattern")

    assert metrics["tk_cross"] == "bullish TK cross"

def test_risk_is_missing_without_valid_breakout_or_retest_pattern():
    rows = []
    for _idx in range(35):
        rows.append(
            {
                "Open": 105.0,
                "High": 106.0,
                "Low": 104.0,
                "Close": 105.0,
                "tenkan": 102.0,
                "kijun": 100.0,
                "cloud_top": 102.0,
                "cloud_bottom": 100.0,
                "span_a": 101.0,
                "span_b": 100.0,
            }
        )
    df = pd.DataFrame(rows)

    metrics = scanner_search._ichimoku_extra_metrics(df, "above", "Touched the cloud")

    assert metrics["ichimoku_risk"] == "-"


def test_chikou_metric_uses_direction_arrow_and_contextual_risk():
    base_rows = []
    for idx in range(60):
        base_rows.append(
            {
                "Open": 100.0,
                "High": 106.0,
                "Low": 94.0,
                "Close": 100.0,
                "tenkan": 102.0,
                "kijun": 100.0,
                "cloud_top": 99.0,
                "cloud_bottom": 95.0,
                "span_a": 101.0,
                "span_b": 100.0,
            }
        )
    df_over = pd.DataFrame(base_rows)
    df_over.loc[len(df_over) - 27, "Close"] = 90.0
    df_over.loc[len(df_over) - 1, "Close"] = 110.0

    long_metrics = scanner_search._ichimoku_extra_metrics(df_over, "above", "breakout_confirmed")

    assert long_metrics["chikou_confirmation"] == "↑ over"
    assert long_metrics["ichimoku_risk"] == "3%"

    df_under = pd.DataFrame(base_rows)
    df_under.loc[len(df_under) - 27, "Close"] = 110.0
    df_under.loc[len(df_under) - 1, "Close"] = 90.0

    short_metrics = scanner_search._ichimoku_extra_metrics(df_under, "below", "deep_retest_pattern")

    assert short_metrics["chikou_confirmation"] == "↓ under"
    assert short_metrics["ichimoku_risk"] == "3%"


def test_retest_pattern_adds_one_risk_without_green_kumo_bonus():
    rows = []
    for idx in range(60):
        rows.append(
            {
                "Open": 100.0,
                "High": 106.0,
                "Low": 94.0,
                "Close": 100.0,
                "tenkan": 96.0,
                "kijun": 100.0,
                "cloud_top": 125.0,
                "cloud_bottom": 115.0,
                "span_a": 100.0,
                "span_b": 101.0,
            }
        )
    df = pd.DataFrame(rows)
    df.loc[len(df) - 27, "Close"] = 90.0
    df.loc[len(df) - 1, "Close"] = 120.0

    metrics = scanner_search._ichimoku_extra_metrics(df, "above", "medium_retest_pattern")

    assert metrics["chikou_confirmation"] == "↑ over"
    assert metrics["kumo_twist"] == "red"
    assert metrics["ichimoku_risk"] == "2%"

def test_ichimoku_status_distinguishes_over_from_kijun_touch():
    df_over = pd.DataFrame([
        {
            "Open": 105.0, "High": 106.0, "Low": 104.0, "Close": 105.0,
            "kijun": 100.0, "cloud_top": 102.0, "cloud_bottom": 99.0,
        }
    ])
    df_touch = pd.DataFrame([
        {
            "Open": 105.0, "High": 106.0, "Low": 99.5, "Close": 105.0,
            "kijun": 100.0, "cloud_top": 98.0, "cloud_bottom": 96.0,
        }
    ])

    assert scanner_search._ichimoku_status(df_over, "above") == "Over Kijun-sen"
    assert scanner_search._ichimoku_status(df_touch, "above") == "Touched Kijun-sen"


def test_young_flip_over_kijun_is_not_actionable_until_retest():
    row = scanner_search.FlipResult(
        ticker="RWE.DE", previous_side="below", current_side="above",
        flip_date="2026-05-29", months_since_flip=0.1, close=100.0,
        ichimoku_status="Over Kijun-sen",
    )
    touched = scanner_search.FlipResult(
        ticker="RWE.DE", previous_side="below", current_side="above",
        flip_date="2026-05-29", months_since_flip=0.1, close=100.0,
        ichimoku_status="Touched Kijun-sen",
    )

    assert not scanner_search._flip_still_actionable(row)
    assert scanner_search._flip_still_actionable(touched)


def test_ichimoku_retest_reports_bullish_engulfing_before_piercing_line():
    rows = [
        {
            "Date": "2026-06-05",
            "Open": 69.0,
            "High": 69.5,
            "Low": 68.5,
            "Close": 69.2,
            "cloud_top": 68.0,
            "cloud_bottom": 65.0,
        },
        {
            "Date": "2026-06-08",
            "Open": 68.8,
            "High": 69.1,
            "Low": 68.0,
            "Close": 68.5,
            "cloud_top": 68.0,
            "cloud_bottom": 65.0,
        },
        {
            "Date": "2026-06-09",
            "Open": 67.4,
            "High": 67.5,
            "Low": 65.5,
            "Close": 66.6,
            "cloud_top": 68.0,
            "cloud_bottom": 65.0,
        },
        {
            "Date": "2026-06-10",
            "Open": 66.0,
            "High": 67.9,
            "Low": 65.5,
            "Close": 67.9,
            "cloud_top": 68.0,
            "cloud_bottom": 65.0,
        },
        {
            "Date": "2026-06-11",
            "Open": 67.5,
            "High": 68.0,
            "Low": 66.6,
            "Close": 66.6,
            "cloud_top": 68.0,
            "cloud_bottom": 65.0,
        },
    ]
    df = pd.DataFrame(rows)

    status, depth, count, first_date, events = scanner_search._detect_ichimoku_retest(df, 1, "above")

    assert status == "deep_retest_pattern"
    assert depth == "deep"
    assert count == 1
    assert first_date == "2026-06-10"
    assert events == [("2026-06-10", "bullish_engulfing", "deep")]
