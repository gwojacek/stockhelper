from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")
scanner = pytest.importorskip("scanner_search")


def test_health_check_prints_summary_then_replaces_warned_csv(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "SOYOIL.csv"
    pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=80)}).to_csv(csv_path, index=False)
    replacement_calls = []

    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)

    def replace_csv(**kwargs):
        replacement_calls.append(kwargs)
        assert not csv_path.exists(), "warned CSV must be removed before the full-history retry"
        pd.DataFrame({"Date": pd.date_range("2025-07-01", periods=260)}).to_csv(csv_path, index=False)
        return pd.DataFrame(), None, None

    monkeypatch.setattr(scanner, "load_or_update_daily_data", replace_csv)
    scanner._commodity_csv_health_check(["SOYOIL"])

    output = capsys.readouterr().out
    first_summary = output.index("summary: ok=0, warn=1, total=1")
    retry = output.index("replacing and retrying 1 warned commodity CSV(s) once")
    final_summary = output.index("summary: ok=1, warn=0, total=1")
    assert first_summary < retry < final_summary
    assert len(replacement_calls) == 1
    assert len(pd.read_csv(csv_path)) == 260


def test_health_check_restores_warned_csv_when_replacement_fails(monkeypatch, tmp_path):
    csv_path = tmp_path / "PALLADIUM.csv"
    original = pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=80)})
    original.to_csv(csv_path, index=False)

    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)

    def fail_download(**_kwargs):
        assert not csv_path.exists()
        raise RuntimeError("remote unavailable")

    monkeypatch.setattr(scanner, "load_or_update_daily_data", fail_download)
    scanner._commodity_csv_health_check(["PALLADIUM"])

    assert len(pd.read_csv(csv_path)) == 80
