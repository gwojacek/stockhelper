import pandas as pd

import chart_program.chart_loader as loader


def _df(*dates: str) -> pd.DataFrame:
    rows = []
    for idx, date in enumerate(dates, start=1):
        rows.append(
            {
                "Date": pd.Timestamp(date),
                "Open": float(idx),
                "High": float(idx + 1),
                "Low": float(idx - 0.5),
                "Close": float(idx + 0.25),
                "Volume": 1000 * idx,
            }
        )
    return pd.DataFrame(rows)


def test_forex_uses_yahoo_as_primary_source(monkeypatch):
    calls = []

    def fake_yahoo(symbol, instrument_type):
        calls.append((symbol, instrument_type))
        return _df("2026-06-10"), "EURUSD=X", "Euro / US Dollar"

    def fail_stooq(*_args, **_kwargs):
        raise AssertionError("forex should not call Stooq in auto mode")

    monkeypatch.setattr(loader, "_yahoo_download", fake_yahoo)
    monkeypatch.setattr(loader, "_stooq_download", fail_stooq)

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="EURUSD",
        instrument_type="forex",
        api_key=None,
        data_source="auto",
    )

    assert calls == [("EURUSD", "forex")]
    assert source == "yahoo"
    assert source_symbol == "EURUSD=X"
    assert source_name == "Euro / US Dollar"
    assert "forex/index" in reason
    assert df["Date"].max() == pd.Timestamp("2026-06-10")


def test_index_like_commodity_uses_yahoo_as_primary_source(monkeypatch):
    calls = []

    def fake_yahoo(symbol, instrument_type):
        calls.append((symbol, instrument_type))
        return _df("2026-06-10"), "^NDX", None

    def fail_stooq(*_args, **_kwargs):
        raise AssertionError("US100 should not call Stooq in auto mode")

    monkeypatch.setattr(loader, "_yahoo_download", fake_yahoo)
    monkeypatch.setattr(loader, "_stooq_download", fail_stooq)

    _df_out, source, source_symbol, _source_name, reason = loader._download_remote(
        symbol="US100",
        instrument_type="commodity",
        api_key=None,
        data_source="auto",
    )

    assert calls == [("US100", "commodity")]
    assert source == "yahoo"
    assert source_symbol == "^NDX"
    assert "forex/index" in reason


def test_warsaw_stock_merges_stooq_bulk_with_yahoo_fresh_candle(monkeypatch):
    def fake_stooq(symbol, instrument_type, api_key=None, lookback_days=364, end_date=None):
        return _df("2026-06-07", "2026-06-09"), "abc.pl"

    def fake_yahoo_window(symbol, instrument_type, *, period):
        return _df("2026-06-09", "2026-06-10"), "ABC.WA", "ABC SA"

    monkeypatch.setattr(loader, "_stooq_download", fake_stooq)
    monkeypatch.setattr(loader, "_yahoo_download_window", fake_yahoo_window)
    monkeypatch.setattr(loader, "_is_after_warsaw_market_close", lambda now=None: True)

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="ABC.WA",
        instrument_type="stock",
        api_key=None,
        data_source="auto",
    )

    assert source == "stooq+yahoo"
    assert source_symbol == "ABC.WA"
    assert source_name == "ABC SA"
    assert sorted(df["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-07", "2026-06-09", "2026-06-10"]
    assert "after 17:30 Warsaw" in reason or "no local cache" in reason


def test_yahoo_symbol_candidates_include_warsaw_suffix_for_short_stock_symbols():
    assert loader._yahoo_symbol_candidates("ABC", "stock") == ["ABC", "ABC.WA"]
