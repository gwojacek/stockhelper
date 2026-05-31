from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
scanner_search = pytest.importorskip("scanner_search")


def test_tk_cross_from_month_before_cloud_entry_is_kept():
    rows = []
    for idx in range(35):
        # Current cloud interaction starts at idx=30. The bullish TK cross at
        # idx=18 is not today's cross, but it is within roughly one trading
        # month before cloud entry and should still be reported.
        in_cloud_touch = idx >= 30
        rows.append(
            {
                "Open": 105.0 if not in_cloud_touch else 101.0,
                "High": 106.0 if not in_cloud_touch else 103.0,
                "Low": 104.0 if not in_cloud_touch else 99.0,
                "Close": 105.0 if not in_cloud_touch else 101.0,
                "tenkan": 99.0 if idx < 18 else 102.0,
                "kijun": 100.0,
                "cloud_top": 102.0,
                "cloud_bottom": 100.0,
                "span_a": 101.0,
                "span_b": 100.0,
            }
        )
    df = pd.DataFrame(rows)

    metrics = scanner_search._ichimoku_extra_metrics(df, "above", "Touched the cloud")

    assert metrics["tk_cross"] == "bullish TK cross"
