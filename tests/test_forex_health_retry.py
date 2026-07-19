from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
scanner = pytest.importorskip("scanner_search")


def test_forex_health_replaces_short_csv_and_reports_post_retry(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "AUDUSD.csv"
    today = datetime.now(UTC).date()
    pd.DataFrame({"Date": pd.date_range(today - timedelta(days=100), today)}).to_csv(csv_path, index=False)
    calls = []

    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_WORKERS", "1")
    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_RETRY_DELAY", "0")
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)

    def replace_csv(**kwargs):
        calls.append(kwargs)
        assert not csv_path.exists()
        pd.DataFrame({"Date": pd.date_range(today - timedelta(days=548), today)}).to_csv(csv_path, index=False)
        return pd.DataFrame(), csv_path, {}

    monkeypatch.setattr(scanner, "load_or_update_daily_data", replace_csv)
    scanner._forex_csv_health_check(["AUDUSD"])

    output = capsys.readouterr().out
    assert "rolling 1.5-year coverage check" in output
    assert "summary: ok=0, warn=1, total=1" in output
    assert "retry round 1/4: replacing and retrying 1 incomplete CSV(s)" in output
    assert "post-retry round 1 rolling coverage check" in output
    assert "all forex CSVs complete after retry round 1" in output
    assert len(calls) == 1


def test_forex_health_retries_transient_tor_failure_in_next_round(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "EURCHF.csv"
    today = datetime.now(UTC).date()
    calls = []

    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_WORKERS", "1")
    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_RETRY_ROUNDS", "3")
    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_RETRY_DELAY", "0")
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)

    def transient_then_success(**_kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("Odmowa dostępu")
        pd.DataFrame({"Date": pd.date_range(today - timedelta(days=548), today)}).to_csv(csv_path, index=False)
        return pd.DataFrame(), csv_path, {}

    monkeypatch.setattr(scanner, "load_or_update_daily_data", transient_then_success)
    scanner._forex_csv_health_check(["EURCHF"])

    output = capsys.readouterr().out
    assert "retry round 1 failed for EURCHF" in output
    assert "retry round 2/3" in output
    assert "all forex CSVs complete after retry round 2" in output
    assert len(calls) == 2


def test_forex_health_does_not_retry_complete_rolling_window(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "USDJPY.csv"
    today = datetime.now(UTC).date()
    pd.DataFrame({"Date": pd.date_range(today - timedelta(days=548), today)}).to_csv(csv_path, index=False)

    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)
    monkeypatch.setattr(
        scanner,
        "load_or_update_daily_data",
        lambda **_kwargs: pytest.fail("complete forex CSV must not be retried"),
    )

    scanner._forex_csv_health_check(["USDJPY"])

    assert "summary: ok=1, warn=0, total=1" in capsys.readouterr().out
