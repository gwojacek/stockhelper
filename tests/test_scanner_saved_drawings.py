from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import scanner_search as scanner


def _prices(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({
        "Date": dates,
        "Open": closes,
        "High": [value + 1 for value in closes],
        "Low": [value - 1 for value in closes],
        "Close": closes,
    })


def test_saved_fibo_anchor_is_returned_until_first_touch_window_resolves(tmp_path: Path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    (sessions / "abc.json").write_text(json.dumps({"drawn_objects": [{
        "type": "fib-boundary", "group_id": "auto-fibo",
        "x0": "2026-01-01", "y0": 100, "x1": "2026-01-05", "y1": 200,
    }]}), encoding="utf-8")

    waiting = scanner._find_manual_fibo_setup(_prices([100, 130, 160, 180, 200, 190, 180]), "ABC")
    assert waiting is not None
    assert (waiting.incline_start_date, waiting.incline_end_date) == ("2026-01-01", "2026-01-05")

    touching = scanner._find_manual_fibo_setup(_prices([100, 130, 160, 180, 200, 138]), "ABC")
    assert touching is not None and touching.status == "touched_61_8_no_pattern"
    resolved = scanner._find_manual_fibo_setup(_prices([100, 130, 160, 180, 200, 138, 145, 150]), "ABC")
    assert resolved is None


def test_scanner_finds_direction_specific_session_file(tmp_path: Path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setattr(scanner, "STATE_DATA_DIR", tmp_path)
    (sessions / "eurpln_long.json").write_text('{"drawn_objects": []}', encoding="utf-8")
    assert scanner._scanner_session_for_ticker("EURPLN") == {"drawn_objects": []}
