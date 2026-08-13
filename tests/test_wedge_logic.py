from __future__ import annotations

import sys
import json
import os
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

pd = pytest.importorskip("pandas")
scanner = pytest.importorskip("scanner_search")


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "csv" / "stocks"
COMMODITY_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "csv" / "commodities"


def test_manual_wedge_anchor_uses_real_candle_anchors_not_future_display_extension():
    obj = {
        "x": ["2026-06-05", "2026-08-11", "2026-12-01"],
        "y": [3793.5, 3539.73, 3100.0],
        "x0": "2026-06-05",
        "y0": 3793.5,
        "x1": "2026-12-01",
        "y1": 3100.0,
        # Original automatic anchors are deliberately stale after the edit.
        "anchor_x": ["2026-06-05", "2026-08-11"],
        "anchor_y": [3793.5, 3548.25],
    }

    assert scanner._manual_wedge_anchor(obj) == (
        ("2026-06-05", 3793.5),
        ("2026-08-11", 3548.25),
    )
    assert scanner._manual_wedge_line_geometry(obj) == (
        ("2026-06-05", 3793.5),
        ("2026-12-01", 3100.0),
    )


def test_saved_drawing_kinds_recognizes_manual_scanner_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "KLIN.json").write_text(json.dumps({
        "drawn_objects": [
            {"type": "wedge", "group_id": "auto-wedge"},
            {"type": "fib", "group_id": "edited-fibo"},
        ]
    }), encoding="utf-8")

    assert scanner._saved_drawing_kinds_for_ticker("KLIN.WA") == {"wedge", "fibo"}


def test_saved_fibo_anchors_are_read_from_boundary_group(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    objects = [
        {"type": "fib", "group_id": "edited", "direction": "long", "ratio": 0.618},
        {"type": "fib-boundary", "group_id": "edited", "x0": "2026-02-02", "x1": "2026-06-05"},
    ]
    (sessions / "KLIN.json").write_text(json.dumps({"drawn_objects": objects}), encoding="utf-8")

    assert scanner._saved_fibo_anchors_for_ticker("KLIN") == [
        ("long", "2026-02-02", "2026-06-05")
    ]


def test_saved_drawing_kinds_resolves_commodity_provider_session(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    # Path.stem removes only the final .py from AL.F.py, so the chart saves
    # the session as AL.F.json and not AL.json.
    (sessions / "AL.F.json").write_text(json.dumps({
        "drawn_objects": [{"type": "wedge", "group_id": "auto-wedge"}]
    }), encoding="utf-8")

    assert scanner._scanner_session_path_for_ticker("ALUMINIUM") == sessions / "AL.F.json"
    assert scanner._saved_drawing_kinds_for_ticker("ALUMINIUM") == {"wedge"}


def test_commodity_session_resolution_keeps_legacy_short_stem_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "AL.json").write_text("{}", encoding="utf-8")

    assert scanner._scanner_session_path_for_ticker("ALUMINIUM") == sessions / "AL.json"


def test_commodity_session_resolution_uses_newest_directional_chart_save(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    old = sessions / "AL.F.json"
    old.write_text("{}", encoding="utf-8")
    new = sessions / "aluminium_long.json"
    new.write_text(json.dumps({"drawn_objects": [{"type": "wedge"}]}), encoding="utf-8")
    os.utime(old, ns=(1_000_000_000, 1_000_000_000))
    os.utime(new, ns=(2_000_000_000, 2_000_000_000))

    assert scanner._scanner_session_path_for_ticker("ALUMINIUM") == new
    assert scanner._saved_drawing_kinds_for_ticker("ALUMINIUM") == {"wedge"}


def test_commodity_session_resolution_finds_report_launched_provider_config(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    # AllSearch opens `python run -c AL.F`; resolve_config_path converts the
    # resulting al.f_long target into al_f_long.py / al_f_long.json.
    saved = sessions / "al_f_long.json"
    saved.write_text(json.dumps({
        "drawn_objects": [
            {"type": "wedge", "label": "upper"},
            {"type": "wedge", "label": "lower"},
        ]
    }), encoding="utf-8")

    assert scanner._scanner_session_path_for_ticker("ALUMINIUM") == saved
    assert scanner._saved_drawing_kinds_for_ticker("ALUMINIUM") == {"wedge"}


def test_manual_wedge_breakout_is_checked_only_after_all_saved_anchors(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    dates = pd.date_range("2026-01-01", periods=8, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [9.0] * 8,
        "High": [10.0, 9.8, 9.6, 9.4, 9.2, 9.0, 8.8, 8.6],
        "Low": [6.0, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7],
        # The early closes are outside the eventual saved lower line. They are
        # not breakdowns because that line's second anchor is candle five.
        "Close": [5.0, 5.5, 6.2, 6.4, 6.6, 7.0, 7.1, 7.2],
    })
    objects = [
        {"type": "wedge", "label": "upper", "x0": "2026-01-01", "y0": 10.0, "x1": "2026-01-05", "y1": 9.2},
        {"type": "wedge", "label": "lower", "x0": "2026-01-01", "y0": 6.0, "x1": "2026-01-05", "y1": 6.4},
    ]
    (sessions / "KLIN.json").write_text(json.dumps({"drawn_objects": objects}), encoding="utf-8")

    result = scanner._find_manual_unbroken_wedge_setup(df, "KLIN")

    assert result is not None
    assert result.breakout_direction == "-"
    assert result.breakout_date == "-"


def test_manual_wedge_later_touch_supersedes_earlier_apparent_breakout(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    dates = pd.date_range("2026-08-01", periods=6, freq="D")
    df = pd.DataFrame({
        "Date": dates, "Open": [9.0] * 6,
        "High": [10.0, 9.8, 9.6, 10.5, 9.2, 9.0],
        "Low": [6.0, 6.1, 6.2, 6.3, 6.4, 6.5],
        "Close": [8.0, 8.0, 8.0, 9.3, 8.5, 8.4],
    })
    objects = [
        {"type": "wedge", "label": "upper", "anchor_x": ["2026-08-01", "2026-08-03"], "anchor_y": [10.0, 9.6]},
        {"type": "wedge", "label": "lower", "anchor_x": ["2026-08-01", "2026-08-03"], "anchor_y": [6.0, 6.2]},
    ]
    (sessions / "KLIN.json").write_text(json.dumps({"drawn_objects": objects}), encoding="utf-8")

    result = scanner._find_manual_unbroken_wedge_setup(df, "KLIN")

    assert result is not None
    assert result.breakout_direction == "-"


def test_aluminium_saved_wedge_uses_calendar_time_and_remains_unbroken(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    objects = [
        {
            "type": "wedge", "label": "upper",
            "anchor_x": ["2026-06-05", "2026-08-06"], "anchor_y": [3793.5, 3452.25],
            "x": ["2026-06-05", "2026-08-11"], "y": [3793.5, 3539.73], "free_extension": True,
        },
        {
            "type": "wedge", "label": "lower",
            "anchor_x": ["2026-02-02", "2026-06-25"], "anchor_y": [2856.5, 3209.5],
            "x": ["2026-02-02", "2026-07-01"], "y": [2856.5, 3225.91], "free_extension": True,
        },
    ]
    (sessions / "ALUMINIUM.json").write_text(json.dumps({"drawn_objects": objects}), encoding="utf-8")
    df = pd.read_csv(COMMODITY_DATA_DIR / "AL_F.csv")

    result = scanner._find_manual_unbroken_wedge_setup(df, "ALUMINIUM")

    assert result is not None
    assert result.breakout_date == "-"
    assert result.breakout_direction == "-"
    assert result.upper_touches >= 2
    assert result.lower_touches >= 3


def test_price_only_markets_are_not_rejected_for_unusable_turnover():
    assert scanner._passes_scanner_liquidity(0.0, "commodity", 500_000.0)
    assert scanner._passes_scanner_liquidity(None, "commodity", 500_000.0)
    assert scanner._passes_scanner_liquidity(0.0, "forex", 500_000.0)
    assert scanner._passes_scanner_liquidity(None, "forex", 500_000.0)
    assert scanner._passes_scanner_liquidity(1.0, "forex", 500_000.0)
    assert not scanner._passes_scanner_liquidity(0.0, "stock", 500_000.0)


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


def test_bmc_wa_falling_wedge_prefers_recent_extreme_upper_anchor():
    df = pd.read_csv(StringIO(
        "Date,Open,High,Low,Close,Volume\n"
        "2026-04-07,22.70,29.40,22.40,28.52,\n"
        "2026-04-08,26.50,27.00,23.40,24.36,\n"
        "2026-04-09,24.80,25.22,24.32,24.76,\n"
        "2026-04-10,24.86,25.00,22.62,24.00,\n"
        "2026-04-13,24.82,25.30,24.04,24.46,\n"
        "2026-04-14,24.44,24.44,23.80,23.92,\n"
        "2026-04-15,23.90,24.30,23.72,24.10,\n"
        "2026-04-16,24.10,24.10,22.82,22.86,\n"
        "2026-04-17,22.86,23.28,21.68,22.38,\n"
        "2026-04-20,22.68,22.98,22.04,22.88,\n"
        "2026-04-21,22.66,22.68,21.70,21.72,\n"
        "2026-04-22,22.00,22.32,21.40,22.00,\n"
        "2026-04-23,21.82,22.64,21.52,21.68,\n"
        "2026-04-24,22.10,22.10,20.80,21.40,\n"
        "2026-04-27,21.42,21.70,19.82,20.50,\n"
        "2026-04-28,20.32,20.88,19.55,20.40,\n"
        "2026-04-29,20.10,20.48,19.86,20.00,\n"
        "2026-04-30,20.20,20.58,20.20,20.48,\n"
        "2026-05-04,20.48,21.58,20.48,20.80,\n"
        "2026-05-05,21.12,23.76,21.12,22.70,\n"
        "2026-05-06,22.74,22.98,20.80,21.40,\n"
        "2026-05-07,21.80,21.86,20.84,21.00,\n"
        "2026-05-08,21.46,21.58,20.10,20.80,\n"
        "2026-05-11,20.98,21.60,20.82,21.20,\n"
        "2026-05-12,21.00,21.00,19.50,20.06,\n"
        "2026-05-13,20.10,20.48,19.60,19.76,\n"
        "2026-05-14,19.90,20.20,19.70,19.90,\n"
        "2026-05-15,19.69,20.00,19.21,19.80,\n"
        "2026-05-18,19.75,19.75,19.04,19.20,\n"
        "2026-05-19,19.28,19.78,19.10,19.28,\n"
        "2026-05-20,19.59,19.59,19.20,19.50,\n"
        "2026-05-21,19.54,19.98,19.20,19.80,\n"
        "2026-05-22,19.85,19.85,19.01,19.15,\n"
        "2026-05-25,19.15,19.45,18.50,18.99,\n"
        "2026-05-26,19.14,19.44,18.80,19.10,\n"
        "2026-05-27,19.20,19.20,18.61,18.90,\n"
        "2026-05-28,18.90,19.51,18.51,18.80,\n"
        "2026-05-29,19.02,19.20,18.50,18.62,\n"
        "2026-06-01,19.00,20.36,18.96,19.45,\n"
        "2026-06-02,19.83,20.60,19.00,19.57,\n"
        "2026-06-03,19.70,19.70,19.14,19.28,\n"
        "2026-06-05,19.28,19.40,18.80,18.82,\n"
        "2026-06-08,18.80,19.10,18.30,18.44,\n"
        "2026-06-09,18.66,18.67,17.60,17.80,\n"
        "2026-06-10,17.80,17.84,16.02,17.46,\n"
        "2026-06-11,17.40,17.68,16.74,17.10,\n"
        "2026-06-12,17.10,17.40,16.83,17.00,\n"
        "2026-06-15,17.00,20.20,16.85,18.10,\n"
        "2026-06-16,18.40,18.40,17.21,17.55,\n"
        "2026-06-17,17.54,18.55,17.00,17.95,\n"
        "2026-06-18,18.34,18.34,17.00,17.82,\n"
        "2026-06-19,17.79,18.30,17.57,17.82,\n"
        "2026-06-22,18.12,18.23,17.02,17.70,\n"
        "2026-06-23,17.48,17.78,17.00,17.49,\n"
        "2026-06-24,17.49,17.49,16.85,16.90,\n"
        "2026-06-25,16.90,17.09,16.51,16.71,\n"
        "2026-06-26,16.89,16.89,15.34,16.23,\n"
        "2026-06-29,16.25,17.50,16.25,16.90,\n"
        "2026-06-30,16.51,17.26,15.97,16.35,\n"
        "2026-07-01,16.21,16.39,15.30,15.86,\n"
        "2026-07-02,15.86,16.40,15.55,16.25,\n"
        "2026-07-03,16.50,16.50,15.92,16.19,\n"
        "2026-07-06,16.19,18.00,16.05,17.21,\n"
        "2026-07-07,17.45,17.45,16.00,16.07,\n"
        "2026-07-08,16.13,16.24,14.98,15.70,\n"
        "2026-07-09,15.79,16.20,15.00,15.52,\n"
        "2026-07-10,15.44,15.85,15.00,15.70,\n"
        "2026-07-13,15.50,16.35,15.45,16.00,\n"
        "2026-07-14,16.24,16.25,15.50,15.85,\n"
        "2026-07-15,15.98,16.26,15.50,15.71,\n"
        "2026-07-16,15.64,16.10,15.24,15.86,\n"
        "2026-07-17,15.85,15.99,15.66,15.68,\n"
    ))

    setup = scanner._find_falling_wedge_setup(df)

    assert setup is not None
    assert setup.upper_start_date == "2026-04-07"
    assert setup.upper_start_price == pytest.approx(29.40)
    assert setup.upper_end_date == "2026-07-06"
    assert setup.upper_end_price == pytest.approx(18.00)
    assert setup.lower_start_date == "2026-06-10"
    assert setup.lower_start_price == pytest.approx(16.02)
    assert setup.lower_end_date == "2026-06-26"
    assert setup.lower_end_price == pytest.approx(15.34)
