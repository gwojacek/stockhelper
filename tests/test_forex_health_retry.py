from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")
scanner = pytest.importorskip("scanner_search")


def test_forced_commodity_refresh_ignores_daily_refresh_state(monkeypatch, capsys):
    monkeypatch.setenv("STOCKHELPER_FORCE_REMOTE_REFRESH", "1")
    monkeypatch.setenv("STOCKHELPER_CACHE_ONLY", "1")
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda symbol, _instrument: Path(f"/missing/{symbol}.csv"))

    assert scanner._should_refresh_group_data("commodities", ["GOLD", "SILVER"], None) is True
    assert scanner.os.environ.get("STOCKHELPER_CACHE_ONLY") == "1"
    assert scanner.os.environ.get("STOCKHELPER_MARKET_REFRESH_SYMBOLS") == "XAUUSD,XAGUSD"
    assert scanner.os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") is None
    assert "audited last 20 candles" in capsys.readouterr().out


def test_forex_health_replaces_short_csv_and_reports_post_retry(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "AUDUSD.csv"
    today = datetime.now(UTC).date()
    pd.DataFrame({"Date": pd.date_range(today - timedelta(days=100), today)}).to_csv(csv_path, index=False)
    calls = []

    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_WORKERS", "1")
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)

    def replace_csv(**kwargs):
        calls.append(kwargs)
        assert not csv_path.exists()
        assert scanner.os.environ.get("STOCKHELPER_CACHE_ONLY") is None
        assert scanner.os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") == "1"
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


def test_forex_health_retry_overrides_and_restores_cache_only(monkeypatch, tmp_path):
    csv_path = tmp_path / "AUDUSD.csv"
    today = datetime.now(UTC).date()
    pd.DataFrame({"Date": pd.date_range(today - timedelta(days=100), today)}).to_csv(csv_path, index=False)

    monkeypatch.setenv("STOCKHELPER_CACHE_ONLY", "1")
    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_WORKERS", "1")
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)

    def replace_csv(**_kwargs):
        assert scanner.os.environ.get("STOCKHELPER_CACHE_ONLY") is None
        assert scanner.os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") == "1"
        pd.DataFrame({"Date": pd.date_range(today - timedelta(days=548), today)}).to_csv(csv_path, index=False)
        return pd.DataFrame(), csv_path, {"source": "stooq_web_csv+yahoo"}

    monkeypatch.setattr(scanner, "load_or_update_daily_data", replace_csv)
    scanner._forex_csv_health_check(["AUDUSD"])

    assert scanner.os.environ.get("STOCKHELPER_CACHE_ONLY") == "1"
    assert scanner.os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") is None


def test_forex_scope_refreshes_stale_cache_without_trusting_yahoo_probe(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "AUDUSD.csv"
    expected_latest = scanner.get_expected_latest_session_date("forex", "FOREX", datetime.now(UTC), "AUDUSD")
    pd.DataFrame({"Date": [expected_latest - timedelta(days=3)]}).to_csv(csv_path, index=False)

    monkeypatch.delenv("STOCKHELPER_CACHE_ONLY", raising=False)
    monkeypatch.delenv("STOCKHELPER_FORCE_REMOTE_REFRESH", raising=False)
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)
    monkeypatch.setattr(
        scanner,
        "has_new_remote_data",
        lambda *_args, **_kwargs: pytest.fail("stale local FX cache must refresh before the Yahoo probe"),
    )

    assert scanner._should_refresh_group_data("forex", ["AUDUSD"], None) is True

    output = capsys.readouterr().out
    assert "missing expected sessions=" in output
    assert "refresh mode ON (Stooq + Yahoo merge)" in output
    assert scanner.os.environ.get("STOCKHELPER_CACHE_ONLY") is None
    assert scanner.os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") == "1"


def test_forex_health_retries_transient_tor_failure_in_next_round(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "EURCHF.csv"
    today = datetime.now(UTC).date()
    calls = []

    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_WORKERS", "1")
    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_RETRY_ROUNDS", "3")
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

    scanner._forex_csv_health_check(["USDJPY"], {"USDJPY": "cache"})

    output = capsys.readouterr().out
    assert "OK USDJPY:" in output
    assert "source=cache" in output
    assert "summary: ok=1, warn=0, total=1" in output


def test_forex_health_warns_on_yahoo_contaminated_tail(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "USDJPY.csv"
    today = datetime.now(UTC).date()
    dates = pd.date_range(today - timedelta(days=548), today)
    frame = pd.DataFrame({
        "Date": dates,
        "Open": [150.0] * (len(dates) - 2) + [150.10000610351562, 150.1999969482422],
        "High": [151.0] * len(dates),
        "Low": [149.0] * len(dates),
        "Close": [150.5] * len(dates),
    })
    frame.to_csv(csv_path, index=False)
    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_RETRY", "0")
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda *_args: csv_path)

    scanner._forex_csv_health_check(["USDJPY"], {"USDJPY": "cache"})

    output = capsys.readouterr().out
    assert "WARN USDJPY" in output
    assert "yahoo_like_last20=2" in output


def test_forex_health_detects_two_missing_weekday_candles(monkeypatch, tmp_path, capsys):
    csv_path = tmp_path / "USDJPY.csv"
    today = datetime.now(UTC).date()
    expected_latest = scanner.get_expected_latest_session_date("forex", "FOREX", datetime.now(UTC))
    latest = expected_latest - timedelta(days=2)
    # Keep the assertion deterministic when the two calendar days cross a weekend.
    while len(pd.bdate_range(latest + timedelta(days=1), expected_latest)) != 2:
        latest -= timedelta(days=1)
    pd.DataFrame({"Date": pd.date_range(today - timedelta(days=548), latest)}).to_csv(csv_path, index=False)

    monkeypatch.setenv("STOCKHELPER_FOREX_HEALTH_RETRY", "0")
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda _symbol, _instrument: csv_path)

    scanner._forex_csv_health_check(["USDJPY"], {"USDJPY": "cache"})

    output = capsys.readouterr().out
    assert "WARN USDJPY:" in output
    assert "missing_candles=2" in output
    assert f"expected_latest={expected_latest}" in output
    assert "summary: ok=0, warn=1, total=1" in output


def test_fibo_forex_reports_per_ticker_sources_and_health_summary():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert '_print_forex_source_summary("fibo", members, data_source_by_ticker)' in source
    assert '_print_forex_source_summary("search", members, data_source_by_ticker)' in source
    assert '_forex_csv_health_check(members, data_source_by_ticker)' in source


def test_forex_source_summary_uses_user_facing_fetch_paths(capsys):
    scanner._print_forex_source_summary(
        "search",
        ["AUDUSD", "EURCHF", "USDJPY"],
        {
            "AUDUSD": "stooq_web_csv+yahoo",
            "EURCHF": "stooq_web",
            "USDJPY": "cache",
        },
    )

    output = capsys.readouterr().out
    assert "[search-source] AUDUSD: downloaded_csv" in output
    assert "[search-source] EURCHF: table_ui" in output
    assert "[search-source] USDJPY: cache" in output
    assert "[search-source] summary: cache=1, downloaded_csv=1, table_ui=1" in output


def test_forex_rate_limits_do_not_request_vpn_pause():
    assert scanner._should_prompt_rate_limit("forex") is False
    assert scanner._should_prompt_rate_limit("commodities") is False
