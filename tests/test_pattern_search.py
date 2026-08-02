from __future__ import annotations

import pandas as pd

from pattern_search import PATTERN_CATALOGUE, scan_patterns


def _frame(rows):
    return pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close"])


def test_catalogue_enumerates_existing_named_patterns():
    assert [pattern.name for pattern in PATTERN_CATALOGUE] == [
        "bullish_hammer", "shooting_star", "bullish_engulfing", "bearish_engulfing",
        "piercing_line", "dark_cloud_cover", "bullish_harami", "bearish_harami",
        "morning_star", "morning_doji_star", "evening_star", "evening_doji_star",
    ]


def test_standalone_scanner_finds_morning_star_and_audits_it():
    df = _frame([
        ("2026-07-28", 12.0, 12.5, 9.5, 10.0),
        ("2026-07-29", 9.0, 9.4, 8.8, 9.2),
        ("2026-07-30", 9.5, 12.2, 9.0, 11.5),
    ])
    hits, checked = scan_patterns(df, lookback=3)
    assert any(date == "2026-07-30" and pattern.name == "morning_star" for date, pattern, _close in hits)
    assert checked["morning_star"] == 1


def test_scanner_reports_zero_hits_but_nonzero_checks():
    df = _frame([
        ("2026-07-28", 10.0, 10.5, 9.5, 10.2),
        ("2026-07-29", 10.2, 10.7, 9.9, 10.4),
        ("2026-07-30", 10.4, 10.8, 10.1, 10.5),
    ])
    hits, checked = scan_patterns(df, lookback=3)
    assert not any(pattern.name == "morning_star" for _date, pattern, _close in hits)
    assert checked["morning_star"] == 1


def test_scanner_can_check_only_one_requested_pattern():
    df = _frame([
        ("2026-07-28", 12.0, 12.5, 9.5, 10.0),
        ("2026-07-29", 9.0, 9.4, 8.8, 9.2),
        ("2026-07-30", 9.5, 12.2, 9.0, 11.5),
    ])
    hits, checked = scan_patterns(df, lookback=3, pattern_names=["morning_star"])
    assert [pattern.name for _date, pattern, _close in hits] == ["morning_star"]
    assert checked == {"morning_star": 1}


def test_scanner_rejects_an_unknown_requested_pattern():
    df = _frame([("2026-07-30", 10.0, 11.0, 9.0, 10.5)])
    try:
        scan_patterns(df, pattern_names=["not_a_pattern"])
    except ValueError as exc:
        assert "not_a_pattern" in str(exc)
    else:
        raise AssertionError("unknown pattern should be rejected")
