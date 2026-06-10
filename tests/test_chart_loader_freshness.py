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


def test_warsaw_stock_merges_local_bulk_with_yahoo_fresh_candle_without_stooq_api(monkeypatch, tmp_path):
    csv_path = tmp_path / "ABC_WA.csv"
    _df("2026-06-07", "2026-06-09").to_csv(csv_path, index=False)

    def fail_stooq(*_args, **_kwargs):
        raise AssertionError("Warsaw stock refresh should not call per-symbol Stooq API")

    def fake_yahoo_window(symbol, instrument_type, *, period):
        return _df("2026-06-09", "2026-06-10"), "ABC.WA", "ABC SA"

    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda symbol, instrument_type: csv_path)
    monkeypatch.setattr(loader, "_stooq_download", fail_stooq)
    monkeypatch.setattr(loader, "_yahoo_download_window", fake_yahoo_window)

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="ABC.WA",
        instrument_type="stock",
        api_key=None,
        data_source="auto",
    )

    assert source == "stooq_bulk+yahoo"
    assert source_symbol == "ABC.WA"
    assert source_name == "ABC SA"
    assert sorted(df["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-07", "2026-06-09", "2026-06-10"]
    assert "Yahoo candles appended=1" in reason


def test_yahoo_symbol_candidates_include_warsaw_suffix_for_short_stock_symbols():
    assert loader._yahoo_symbol_candidates("ABC", "stock") == ["ABC", "ABC.WA"]


def test_warsaw_stock_uses_local_cache_and_merges_single_yahoo_candle(monkeypatch, tmp_path):
    csv_path = tmp_path / "ZAB_WA.csv"
    _df("2026-06-09").to_csv(csv_path, index=False)

    def fail_stooq(*_args, **_kwargs):
        raise AssertionError("Warsaw stock refresh should not call per-symbol Stooq API")

    def fake_yahoo_window(symbol, instrument_type, *, period):
        return _df("2026-06-09", "2026-06-10"), "ZAB.WA", "Zabka Group"

    monkeypatch.setattr(loader, "_stooq_download", fail_stooq)
    monkeypatch.setattr(loader, "_yahoo_download_window", fake_yahoo_window)
    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda symbol, instrument_type: csv_path)

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="ZAB.WA",
        instrument_type="stock",
        api_key=None,
        data_source="auto",
    )

    assert source == "stooq_bulk+yahoo"
    assert source_symbol == "ZAB.WA"
    assert source_name == "Zabka Group"
    assert sorted(df["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-09", "2026-06-10"]
    assert "Yahoo candles appended=1" in reason


def test_warsaw_stock_uses_yahoo_when_no_local_bulk_cache(monkeypatch, tmp_path):
    csv_path = tmp_path / "ZAB_WA.csv"

    def fail_stooq(*_args, **_kwargs):
        raise AssertionError("Warsaw stock refresh should not call per-symbol Stooq API")

    def fake_yahoo(symbol, instrument_type):
        return _df("2026-06-10"), "ZAB.WA", "Zabka Group"

    monkeypatch.setattr(loader, "_stooq_download", fail_stooq)
    monkeypatch.setattr(loader, "_yahoo_download", fake_yahoo)
    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda symbol, instrument_type: csv_path)

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="ZAB.WA",
        instrument_type="stock",
        api_key=None,
        data_source="auto",
    )

    assert source == "yahoo"
    assert source_symbol == "ZAB.WA"
    assert source_name == "Zabka Group"
    assert df["Date"].max() == pd.Timestamp("2026-06-10")
    assert "No local Stooq bulk cache" in reason


def test_literal_commodity_uses_yahoo_only_when_one_candle_newer(monkeypatch, tmp_path):
    csv_path = tmp_path / "CC_F.csv"
    _df("2026-06-09").to_csv(csv_path, index=False)

    def fail_stooq_web(*_args, **_kwargs):
        raise AssertionError("one missing commodity candle should not trigger Stooq UI")

    def fake_yahoo_window(symbol, instrument_type, *, period):
        assert symbol == "COCOA"
        assert instrument_type == "commodity"
        return _df("2026-06-09", "2026-06-10"), "CC=F", None

    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda symbol, instrument_type: csv_path)
    monkeypatch.setattr(loader, "update_stooq_history_with_playwright", fail_stooq_web)
    monkeypatch.setattr(loader, "_yahoo_download_window", fake_yahoo_window)

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="COCOA",
        instrument_type="commodity",
        api_key=None,
        data_source="auto",
    )

    assert source == "stooq_web+yahoo"
    assert source_symbol == "CC=F"
    assert source_name is None
    assert sorted(df["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-09", "2026-06-10"]
    assert "only one candle newer" in reason
    assert "Yahoo newer candles=1" in reason


def test_literal_commodity_uses_stooq_ui_then_yahoo_when_more_than_one_candle_newer(monkeypatch, tmp_path):
    csv_path = tmp_path / "CC_F.csv"
    _df("2026-06-08").to_csv(csv_path, index=False)
    stooq_web_calls = []

    def fake_stooq_web(*, symbol, csv_path, lookback_days, end_date, verbose, interactive_captcha):
        stooq_web_calls.append(symbol)
        return _df("2026-06-08", "2026-06-09")

    def fake_yahoo_window(symbol, instrument_type, *, period):
        assert symbol == "COCOA"
        assert instrument_type == "commodity"
        return _df("2026-06-09", "2026-06-10"), "CC=F", None

    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda symbol, instrument_type: csv_path)
    monkeypatch.setattr(loader, "update_stooq_history_with_playwright", fake_stooq_web)
    monkeypatch.setattr(loader, "_yahoo_download_window", fake_yahoo_window)

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="COCOA",
        instrument_type="commodity",
        api_key=None,
        data_source="auto",
    )

    assert stooq_web_calls == ["cc.f"]
    assert source == "stooq_web+yahoo"
    assert source_symbol == "CC=F"
    assert source_name is None
    assert sorted(df["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-08", "2026-06-09", "2026-06-10"]
    assert "Stooq web used as primary source for commodity" in reason
    assert "Yahoo newer candles=1" in reason


def test_yahoo_merge_appends_only_newer_rows_and_preserves_stooq_overlap():
    base = pd.DataFrame(
        [
            {"Date": pd.Timestamp("2026-06-08"), "Open": 10, "High": 12, "Low": 9, "Close": 11, "Volume": 111},
            {"Date": pd.Timestamp("2026-06-09"), "Open": 20, "High": 22, "Low": 19, "Close": 21, "Volume": 53913},
        ]
    )
    yahoo = pd.DataFrame(
        [
            {
                "Date": pd.Timestamp("2026-06-09"),
                "Open": 200,
                "High": 220,
                "Low": 190,
                "Close": 210,
                "Volume": 21110,
                "Adj Close": 210,
                "Dividends": 0,
                "Stock Splits": 0,
            },
            {
                "Date": pd.Timestamp("2026-06-10"),
                "Open": 30,
                "High": 32,
                "Low": 29,
                "Close": 31,
                "Volume": 23547,
                "Adj Close": 31,
                "Dividends": 0,
                "Stock Splits": 0,
            },
        ]
    )

    def fake_yahoo_window(symbol, instrument_type, *, period):
        return yahoo, "CC=F", None

    original = loader._yahoo_download_window
    loader._yahoo_download_window = fake_yahoo_window
    try:
        merged, yahoo_symbol, _name, added_count = loader._merge_yahoo_fresh_candle(base, "COCOA", "commodity")
    finally:
        loader._yahoo_download_window = original

    assert yahoo_symbol == "CC=F"
    assert added_count == 1
    assert list(merged.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert list(merged["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-08", "2026-06-09", "2026-06-10"]
    june_9 = merged.loc[merged["Date"] == pd.Timestamp("2026-06-09")].iloc[0]
    assert float(june_9["Open"]) == 20.0
    assert float(june_9["Volume"]) == 53913.0
    june_10 = merged.loc[merged["Date"] == pd.Timestamp("2026-06-10")].iloc[0]
    assert float(june_10["Volume"]) == 23547.0


def test_non_warsaw_stock_uses_yahoo_without_stooq_api(monkeypatch):
    calls = []

    def fake_yahoo(symbol, instrument_type):
        calls.append((symbol, instrument_type))
        return _df("2026-06-10"), "AAPL", "Apple Inc."

    def fail_stooq(*_args, **_kwargs):
        raise AssertionError("Non-Warsaw stock should not call per-symbol Stooq API")

    monkeypatch.setattr(loader, "_yahoo_download", fake_yahoo)
    monkeypatch.setattr(loader, "_stooq_download", fail_stooq)

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="AAPL.US",
        instrument_type="stock",
        api_key=None,
        data_source="auto",
    )

    assert calls == [("AAPL.US", "stock")]
    assert source == "yahoo"
    assert source_symbol == "AAPL"
    assert source_name == "Apple Inc."
    assert df["Date"].max() == pd.Timestamp("2026-06-10")
    assert "non-Warsaw-stock" in reason
