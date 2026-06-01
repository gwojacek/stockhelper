from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
scanner_search = pytest.importorskip("scanner_search")


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
    assert short_metrics["ichimoku_risk"] == "2%"

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
