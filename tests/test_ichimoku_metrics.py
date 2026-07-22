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
