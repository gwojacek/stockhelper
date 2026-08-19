import sys
import types

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


def test_forex_fetches_table_ui_and_merges_yahoo_newest_candle(monkeypatch, tmp_path):
    calls = []

    def fake_stooq_table(**kwargs):
        calls.append(kwargs)
        return _df("2025-01-20", "2026-06-09")

    csv_path = tmp_path / "EURUSD.csv"
    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(loader, "update_stooq_history_with_playwright", fake_stooq_table)
    monkeypatch.setattr(
        loader,
        "_yahoo_download_window",
        lambda *_args, **_kwargs: (_df("2026-06-09", "2026-06-10"), "EURUSD=X", "EUR/USD"),
    )

    df, source, source_symbol, source_name, reason = loader._download_remote(
        symbol="EURUSD",
        instrument_type="forex",
        api_key=None,
        data_source="auto",
    )

    assert calls == [{
        "symbol": "eurusd", "csv_path": csv_path, "lookback_days": 548,
        "end_date": None, "verbose": False, "interactive_captcha": True,
    }]
    assert source == "stooq_web+yahoo"
    assert source_symbol == "EURUSD=X"
    assert source_name == "EUR/USD"
    assert "Yahoo newer candles=1" in reason
    assert df["Date"].min() == pd.Timestamp("2025-01-20")
    assert df["Date"].max() == pd.Timestamp("2026-06-10")


def test_forex_uses_table_ui_without_csv_download_attempt(monkeypatch, tmp_path):
    csv_path = tmp_path / "EURCHF.csv"
    calls = []

    def fetch_table(**kwargs):
        calls.append(kwargs)
        return _df("2025-01-20", "2026-06-10")

    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(loader, "_try_yahoo_fresh_candle_merge", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loader, "update_stooq_history_with_playwright", fetch_table)

    df, source, source_symbol, _name, reason = loader._download_remote(
        symbol="EURCHF", instrument_type="forex", api_key=None, data_source="auto"
    )

    assert len(calls) == 1
    assert calls[0]["symbol"] == "eurchf"
    assert calls[0]["interactive_captcha"] is True
    assert source == "stooq_web"
    assert source_symbol == "EURCHF"
    assert reason == "Used paginated Stooq UI table fetching for forex."
    assert df["Date"].min() == pd.Timestamp("2025-01-20")


def test_complete_forex_window_uses_cache_without_ui_download(monkeypatch, tmp_path):
    csv_path = tmp_path / "EURUSD.csv"
    today = pd.Timestamp.now(tz="UTC").date()
    pd.DataFrame(
        {
            "Date": pd.date_range(today - pd.Timedelta(days=548), today),
            "Open": 1.0,
            "High": 1.1,
            "Low": 0.9,
            "Close": 1.0,
            "Volume": 0,
        }
    ).to_csv(csv_path, index=False)
    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(
        loader,
        "update_stooq_history_with_playwright",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("complete forex cache must not download")),
    )

    df, source, source_symbol, _name, reason = loader._download_remote(
        symbol="EURUSD", instrument_type="forex", api_key=None, data_source="auto"
    )

    assert source == "cache"
    assert source_symbol == "EURUSD"
    assert "already covers" in reason
    assert not df.empty


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
    assert "index symbols" in reason


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


def test_warsaw_stock_refresh_persists_changed_same_date_yahoo_quote(monkeypatch, tmp_path):
    csv_path = tmp_path / "XTB_WA.csv"
    cached = _df("2026-08-17", "2026-08-18")
    cached.to_csv(csv_path, index=False)
    yahoo = cached.copy()
    yahoo.loc[yahoo.index[-1], ["High", "Close", "Volume"]] = [170.0, 166.46, 500_000]

    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(
        loader,
        "_yahoo_download_window",
        lambda *_args, **_kwargs: (yahoo.copy(), "XTB.WA", "XTB S.A."),
    )
    monkeypatch.setenv("STOCKHELPER_FORCE_REMOTE_REFRESH", "1")

    df, written_path, info = loader.load_or_update_daily_data(
        symbol="XTB.WA",
        instrument_type="stock",
    )

    assert info["source"] == "stooq_bulk+yahoo"
    assert info["symbol"] == "XTB.WA"
    assert float(df.iloc[-1]["Close"]) == 166.46
    assert float(df.iloc[-1]["Volume"]) == 500_000
    assert "same-date updated" in info["fallback_reason"]
    persisted = pd.read_csv(written_path)
    assert float(persisted.iloc[-1]["Close"]) == 166.46
    assert float(persisted.iloc[-1]["Volume"]) == 500_000


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


def test_yahoo_merge_keeps_only_newest_when_stooq_is_multiple_days_behind(monkeypatch):
    base = _df("2026-06-08")
    yahoo = _df("2026-06-09", "2026-06-10", "2026-06-11")
    monkeypatch.setattr(
        loader,
        "_yahoo_download_window",
        lambda *_args, **_kwargs: (yahoo, "EURUSD=X", None),
    )

    merged, _symbol, _name, available_count = loader._merge_yahoo_fresh_candle(
        base, "EURUSD", "forex", trim_to_last_year=False
    )

    assert available_count == 3
    assert list(merged["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-08", "2026-06-11"]


def test_recent_yahoo_candle_count_checks_only_last_twenty_cached_rows():
    cached = _df(*pd.date_range("2026-05-01", periods=25).strftime("%Y-%m-%d"))
    yahoo = cached.copy()
    # One match falls outside the inspected cache tail, leaving exactly two.
    yahoo.loc[~yahoo["Date"].isin(cached.tail(2)["Date"]), "Close"] += 10
    yahoo.loc[yahoo.index[0], "Close"] = cached.loc[cached.index[0], "Close"]

    assert loader._recent_yahoo_candle_count(cached, yahoo) == 2


def test_recent_high_precision_count_detects_yahoo_float_artifacts():
    cached = pd.DataFrame(
        [
            {"Date": "2026-07-23", "Open": 59.666, "High": 60.07, "Low": 57.073, "Close": 57.658},
            {"Date": "2026-07-27", "Open": 59.810001373291016, "High": 60.39500045776367, "Low": 59.400001525878906, "Close": 59.68999862670898},
            {"Date": "2026-07-28", "Open": 58.744998931884766, "High": 58.82500076293945, "Low": 56.900001525878906, "Close": 57.69499969482422},
        ]
    )

    assert loader._recent_high_precision_candle_count(cached) == 2


def test_forced_load_does_not_reintroduce_yahoo_tail_after_remote_rebase(monkeypatch, tmp_path):
    csv_path = tmp_path / "XAGUSD.csv"
    pd.DataFrame(
        [
            {"Date": "2026-07-24", "Open": 57.706, "High": 58.972, "Low": 57.1, "Close": 58.203, "Volume": 0},
            {"Date": "2026-07-28", "Open": 58.744998931884766, "High": 58.82500076293945, "Low": 56.900001525878906, "Close": 57.69499969482422, "Volume": 8767},
            {"Date": "2026-07-29", "Open": 57.3849983215332, "High": 58.459999084472656, "Low": 57.09000015258789, "Close": 58.415000915527344, "Volume": 5892},
        ]
    ).to_csv(csv_path, index=False)
    remote = pd.DataFrame(
        [
            {"Date": "2026-07-27", "Open": 59.508, "High": 60.086, "Low": 58.177, "Close": 58.403, "Volume": 0},
            {"Date": "2026-07-31", "Open": 59.039, "High": 59.168, "Low": 57.037, "Close": 57.928, "Volume": 0},
        ]
    )
    monkeypatch.setenv("STOCKHELPER_FORCE_REMOTE_REFRESH", "1")
    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(
        loader,
        "_download_remote",
        lambda **_kwargs: (remote, "stooq_web", "XAGUSD", None, "forced test rebase"),
    )
    loader._SESSION_REFRESHED_KEYS.clear()

    _df_out, _path, _meta = loader.load_or_update_daily_data("XAGUSD", "commodity", persist=True)

    written = pd.read_csv(csv_path)
    assert written["Date"].tolist() == ["2026-07-24", "2026-07-27", "2026-07-31"]


def test_high_precision_cache_forces_rebase_without_yahoo_probe(monkeypatch):
    cached = _df("2026-07-27", "2026-07-28")
    cached.loc[:, "Open"] = [59.810001373291016, 58.744998931884766]
    monkeypatch.setattr(
        loader,
        "_yahoo_download_window",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("precision detector should decide locally")),
    )

    assert loader._cache_has_too_many_recent_yahoo_candles(cached, "SILVER", "commodity")


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


def test_index_yahoo_symbol_candidates_match_expected_yahoo_tickers():
    expected = {
        "BRACOMP": "^BVSP",
        "US500": "^GSPC",
        "MEXCOMP": "^MXX",
        "VIX": "^VIX",
        "US30": "^DJI",
        "US100": "^NDX",
        "HK.CASH": "^HSI",
        "SG20CASH": "^STI",
        "AU200.CASH": "^AXJO",
        "CHN.CASH": "^HSCE",
        "HSCE": "^HSCE",
        "JP225": "^N225",
        "WIG20": "WIG20.WA",
        "UK100": "^FTSE",
        "ITA40": "FTSEMIB.MI",
        "DE40": "^GDAXI",
        "FRA40": "^FCHI",
        "NED25": "^AEX",
        "SUI20": "^SSMI",
        "SPA35": "^IBEX",
        "EU50": "^STOXX50E",
    }

    for symbol, yahoo_ticker in expected.items():
        assert loader._yahoo_symbol_candidates(symbol, "commodity")[0] == yahoo_ticker


def test_index_yahoo_candidates_translate_legacy_stooq_symbols():
    expected = {
        "^BVP": "^BVSP",
        "^SPX": "^GSPC",
        "^IPC": "^MXX",
        "VI.C": "^VIX",
        "^DJI": "^DJI",
        "^NDX": "^NDX",
        "^HSI": "^HSI",
        "^STI": "^STI",
        "^AOR": "^AXJO",
        "0EL.C": "^HSCE",
        "^NKX": "^N225",
        "WIG20": "WIG20.WA",
        "^UKX": "^FTSE",
        "^FMIB": "FTSEMIB.MI",
        "^DAX": "^GDAXI",
        "^CAC": "^FCHI",
        "^AEX": "^AEX",
        "^SMI": "^SSMI",
        "^IBEX": "^IBEX",
        "FX.F": "^STOXX50E",
    }

    for symbol, yahoo_ticker in expected.items():
        assert loader._yahoo_symbol_candidates(symbol, "commodity")[0] == yahoo_ticker


def test_wig20_uses_stooq_base_and_yahoo_only_for_fresh_candle(monkeypatch, tmp_path):
    csv_path = tmp_path / "WIG20.csv"

    def fake_stooq(symbol, instrument_type, **_kwargs):
        assert symbol == "WIG20"
        assert instrument_type == "commodity"
        return _df("2026-06-09"), "wig20"

    def fail_full_yahoo(*_args, **_kwargs):
        raise AssertionError("WIG20 should not use Yahoo max-history as primary source")

    def fake_yahoo_window(symbol, instrument_type, *, period):
        assert symbol == "WIG20"
        assert instrument_type == "commodity"
        assert period == "10d"
        return _df("2026-06-09", "2026-06-10"), "WIG20.WA", None

    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda symbol, instrument_type: csv_path)
    monkeypatch.setattr(loader, "_stooq_download", fake_stooq)
    monkeypatch.setattr(loader, "_yahoo_download", fail_full_yahoo)
    monkeypatch.setattr(loader, "_yahoo_download_window", fake_yahoo_window)

    df, source, source_symbol, _source_name, reason = loader._download_remote(
        symbol="WIG20",
        instrument_type="commodity",
        api_key=None,
        data_source="auto",
    )

    assert source == "stooq+yahoo"
    assert source_symbol == "WIG20.WA"
    assert sorted(df["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-09", "2026-06-10"]
    assert "Yahoo is used only for newer WIG20 candle" in reason


def test_stooq_bulk_import_includes_wse_indices(tmp_path):
    import zipfile
    from utilities.stooq_playwright import import_stooq_wig_bulk_zip

    zip_path = tmp_path / "d_pl_txt.zip"
    stock_txt = "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\nABC,D,20260609,000000,1,2,0.5,1.5,100,0\n"
    index_txt = "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\nWIG20,D,20260609,000000,2800,2810,2790,2805,0,0\n"
    other_index_txt = "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\nMWIG40,D,20260609,000000,6000,6010,5990,6005,0,0\n"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data/daily/pl/wse stocks/abc.txt", stock_txt)
        zf.writestr("data/daily/pl/wse indices/wig20.txt", index_txt)
        zf.writestr("data/daily/pl/wse indices/mwig40.txt", other_index_txt)

    stocks_dir = tmp_path / "stocks"
    commodities_dir = tmp_path / "commodities"
    indexes_dir = tmp_path / "indexes"
    result = import_stooq_wig_bulk_zip(zip_path, stocks_dir=stocks_dir, commodities_dir=commodities_dir, indexes_dir=indexes_dir)

    assert result["written"] == 1
    assert result["indices_written"] == 1
    assert (stocks_dir / "ABC_WA.csv").exists()
    wig20_csv = indexes_dir / "WIG20.csv"
    assert wig20_csv.exists()
    assert not (commodities_dir / "WIG20.csv").exists()
    assert not (indexes_dir / "MWIG40.csv").exists()
    assert pd.read_csv(wig20_csv)["Close"].iloc[-1] == 2805


def test_index_like_commodity_csv_path_uses_indexes_folder():
    from chart_program.chart_loader import local_csv_path_for_symbol

    path = local_csv_path_for_symbol("WIG20", "commodity")

    assert path.parts[-2:] == ("indexes", "WIG20.csv")


def test_commodity_display_name_csv_path_uses_canonical_stooq_symbol():
    from chart_program.chart_loader import local_csv_path_for_symbol

    path = local_csv_path_for_symbol("Natural Gas", "commodity")

    assert path.parts[-2:] == ("commodities", "NG_F.csv")


def test_indexes_refresh_triggers_stooq_bulk_when_wig20_missing_multiple_sessions(monkeypatch):
    import scanner_search as scanner

    calls = []
    monkeypatch.delenv("STOCKHELPER_CACHE_ONLY", raising=False)
    monkeypatch.delenv("STOCKHELPER_FORCE_REMOTE_REFRESH", raising=False)
    monkeypatch.setattr(
        scanner,
        "_wig20_index_yahoo_freshness_probe",
        lambda: (4, "2026-06-03", "2026-06-11", "WIG20.WA"),
    )

    def fake_bulk(group_name, reason):
        calls.append((group_name, reason))
        return True

    monkeypatch.setattr(scanner, "_try_refresh_wig_with_stooq_bulk", fake_bulk)

    assert scanner._should_refresh_group_data("indexes", ["WIG20"], None) is True
    assert calls
    assert calls[0][0] == "indexes"
    assert "missing 4 sessions" in calls[0][1]


def test_wig_bulk_download_is_attempted_once_per_process(monkeypatch):
    import scanner_search as scanner

    calls = []
    fake_module = types.SimpleNamespace(
        download_and_import_stooq_wig_bulk_data=lambda **_kwargs: calls.append(_kwargs)
        or {"written": 1, "skipped": 0, "members": 1, "indices_written": 1, "indices_members": 1}
    )
    monkeypatch.setitem(sys.modules, "utilities.stooq_playwright", fake_module)
    monkeypatch.setenv("STOCKHELPER_STOOQ_BULK_ATTEMPTED_BUCKET", "")
    monkeypatch.setattr(scanner, "_warsaw_daily_bulk_day", lambda: "2026-07-13")
    state = {}
    monkeypatch.setattr(scanner, "_read_refresh_state", lambda: dict(state))
    monkeypatch.setattr(scanner, "_write_refresh_state", lambda new_state: state.update(new_state))

    assert scanner._try_refresh_wig_with_stooq_bulk("wig", "daily allsearch warm-up") is True
    assert scanner._try_refresh_wig_with_stooq_bulk("indexes", "later indexes probe found newer data") is False

    assert len(calls) == 1
    assert state["stooq_bulk:2026-07-13"]["result"] == "bulk"


def test_wig20_freshness_probe_uses_kgh_reference_dates(monkeypatch, tmp_path):
    import scanner_search as scanner

    wig20_csv = tmp_path / "WIG20.csv"
    _df("2026-06-03").to_csv(wig20_csv, index=False)

    def fake_local_csv_path(symbol, instrument_type):
        assert symbol == "WIG20"
        assert instrument_type == "commodity"
        return wig20_csv

    def fake_yahoo_window(symbol, instrument_type, *, period):
        assert symbol == "KGH.WA"
        assert instrument_type == "stock"
        assert period == "10d"
        return _df("2026-06-11"), "KGH.WA", "KGHM"

    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", fake_local_csv_path)
    monkeypatch.setattr(scanner, "_yahoo_download_window", fake_yahoo_window)

    missing, local_latest, yahoo_latest, candidate = scanner._wig20_index_yahoo_freshness_probe()

    assert missing > 1
    assert local_latest == "2026-06-03"
    assert yahoo_latest == "2026-06-11"
    assert candidate == "KGH.WA"


def test_precious_metals_use_requested_yahoo_futures_tickers():
    assert loader._yahoo_symbol_candidates("GOLD", "commodity")[0] == "GC=F"
    assert loader._yahoo_symbol_candidates("SILVER", "commodity")[0] == "SI=F"
    assert loader._yahoo_symbol_candidates("PALLADIUM", "commodity")[0] == "PA=F"
    assert "XAUUSD" not in loader.COMMODITY_YAHOO_MAP
    assert "XAGUSD" not in loader.COMMODITY_YAHOO_MAP
    assert "XPDUSD" not in loader.COMMODITY_YAHOO_MAP
    assert loader._storage_symbol_for_csv("GOLD", "commodity") == "GOLD"
    assert loader._storage_symbol_for_csv("SILVER", "commodity") == "SILVER"
    assert loader._storage_symbol_for_csv("PALLADIUM", "commodity") == "PALLADIUM"


def test_api_metals_use_yahoo_primary_even_when_scanner_passes_stooq_symbol(monkeypatch):
    calls = []

    def fake_yahoo(symbol, instrument_type):
        calls.append((symbol, instrument_type))
        return _df("2026-06-10"), loader._yahoo_symbol_candidates(symbol, instrument_type)[0], None

    def fail_stooq(*_args, **_kwargs):
        raise AssertionError("API metals should use Yahoo futures tickers instead of Stooq API")

    monkeypatch.setattr(loader, "_yahoo_download", fake_yahoo)
    monkeypatch.setattr(loader, "_stooq_download", fail_stooq)

    expected = {
        "GOLD": "GC=F",
        "SILVER": "SI=F",
        "PALLADIUM": "PA=F",
    }
    for symbol, yahoo_ticker in expected.items():
        _df_out, source, source_symbol, _name, reason = loader._download_remote(
            symbol=symbol,
            instrument_type="commodity",
            api_key=None,
            data_source="auto",
        )
        assert source == "yahoo"
        assert source_symbol == yahoo_ticker
        assert "API metal" in reason

    assert calls == [(symbol, "commodity") for symbol in expected]


def test_commodity_search_uses_canonical_metal_names():
    import scanner_search as scanner

    assert "GOLD" in scanner.COMMODITIES_SEARCH_TICKERS
    assert "SILVER" in scanner.COMMODITIES_SEARCH_TICKERS
    assert "PALLADIUM" in scanner.COMMODITIES_SEARCH_TICKERS
    assert "XAUUSD" not in scanner.COMMODITIES_SEARCH_TICKERS
    assert "XAGUSD" not in scanner.COMMODITIES_SEARCH_TICKERS
    assert scanner._search_fetch_symbol("GOLD", "commodities", None) == ("GOLD", "commodity")
    assert scanner._search_fetch_symbol("SILVER", "commodities", None) == ("SILVER", "commodity")
    assert scanner._search_fetch_symbol("PALLADIUM", "commodities", None) == ("PALLADIUM", "commodity")


def test_etfs_market_uses_stooq_tickers_and_cache_folder():
    import scanner_search as scanner

    group, members, source, suffix = scanner._get_members("etfs")

    assert group == "etfs"
    assert source == "Yahoo Finance"
    assert suffix is None
    assert len(members) == 50
    assert len(set(members)) == 50
    assert members[0] == "VOO.US"
    assert members[-1] == "SCHG.US"
    assert {"1306.JP", "SXR8.DE", "EUNL.DE", "0050.TW"} <= set(members)
    assert scanner._search_fetch_symbol("VOO.US", group, suffix) == ("VOO.US", "etf")
    assert scanner._search_fetch_symbol("1306.JP", group, suffix) == ("1306.JP", "etf")

    from chart_program.chart_loader import local_csv_path_for_symbol
    assert local_csv_path_for_symbol("VOO.US", "etf").as_posix().endswith("data/csv/etfs/VOO_US.csv")


def test_etf_remote_download_is_yahoo_primary(monkeypatch):
    from chart_program import chart_loader as loader

    expected = pd.DataFrame(
        [{"Date": "2026-08-14", "Open": 1, "High": 2, "Low": 0.5, "Close": 1.5, "Volume": 100}]
    )
    calls = []

    def fake_yahoo(symbol, instrument_type):
        calls.append((symbol, instrument_type))
        return expected, "VOO", "Vanguard S&P 500 ETF"

    monkeypatch.setattr(loader, "_yahoo_download", fake_yahoo)
    frame, source, symbol, name, reason = loader._download_remote("VOO.US", "etf")

    assert frame is expected
    assert (source, symbol, name) == ("yahoo", "VOO", "Vanguard S&P 500 ETF")
    assert "Yahoo used as primary source" in reason
    assert calls == [("VOO.US", "etf")]
    assert loader._yahoo_symbol_candidates("VOO.US", "etf")[:2] == ["VOO", "VOO.US"]
    assert loader._yahoo_symbol_candidates("1306.JP", "etf")[:2] == ["1306.T", "1306.JP"]


def test_trim_wig_stock_csvs_keeps_only_last_two_years(tmp_path):
    from utilities.stooq_playwright import trim_wig_stock_csvs

    stocks_dir = tmp_path / "stocks"
    stocks_dir.mkdir()
    stock_csv = stocks_dir / "ABC_WA.csv"
    pd.DataFrame(
        [
            {"Date": "2022-06-10", "Open": 1, "High": 2, "Low": 0.5, "Close": 1.5, "Volume": 100},
            {"Date": "2024-06-11", "Open": 2, "High": 3, "Low": 1.5, "Close": 2.5, "Volume": 200},
            {"Date": "2026-06-11", "Open": 3, "High": 4, "Low": 2.5, "Close": 3.5, "Volume": 300},
        ]
    ).to_csv(stock_csv, index=False)
    non_wig_csv = stocks_dir / "AAPL_US.csv"
    pd.DataFrame([{"Date": "2020-01-01", "Open": 1, "High": 1, "Low": 1, "Close": 1, "Volume": 1}]).to_csv(non_wig_csv, index=False)

    result = trim_wig_stock_csvs(stocks_dir=stocks_dir, years=2, as_of=pd.Timestamp("2026-06-11"))

    trimmed = pd.read_csv(stock_csv)
    assert result["scanned"] == 1
    assert result["trimmed"] == 1
    assert result["rows_before"] == 3
    assert result["rows_after"] == 2
    assert list(trimmed["Date"]) == ["2024-06-11", "2026-06-11"]
    assert pd.read_csv(non_wig_csv)["Date"].iloc[0] == "2020-01-01"


def test_level_selector_refreshes_latest_then_does_not_rewrite_market_data_csv(monkeypatch, tmp_path):
    import chart_program.level_selector as selector

    csv_path = tmp_path / "ABC_WA.csv"
    _df("2026-06-09").to_csv(csv_path, index=False)

    config_path = tmp_path / "abc.py"
    calls: list[bool] = []

    def fake_load_or_update_daily_data(**kwargs):
        calls.append(bool(kwargs.get("fetch_older_data")))
        if not kwargs.get("fetch_older_data"):
            # The initial latest-candle refresh persists the Yahoo-fresh row.
            refreshed = _df("2026-06-09", "2026-06-10")
            refreshed.to_csv(csv_path, index=False)
            return refreshed, csv_path, {
                "source": "stooq_bulk+yahoo",
                "symbol": "ABC.WA",
                "name": "ABC",
                "fallback_reason": "Yahoo candles appended=1",
            }

        # Simulate the chart/full-history path receiving an older/trimmed
        # dataframe. Opening and finishing the chart must not let this dataframe
        # undo the cache on disk.
        return _df("2026-06-09"), csv_path, {
            "source": "cache",
            "symbol": "ABC.WA",
            "name": "ABC",
            "fallback_reason": "Cache-only mode enabled.",
        }

    class FakeUI:
        def __init__(self, *args, **kwargs):
            pass

        def run(self):
            return {
                "__finished__": True,
                "high": 10.0,
                "low": 8.0,
                "entry": 9.0,
                "stop_loss": 7.5,
                "check_zr_value_fibo_or_elevation": 1.0,
                "line_cross_value": 9.5,
                "capital": 1000.0,
            }

        def save_chart_snapshot(self, selected, chart_path):
            chart_path.parent.mkdir(parents=True, exist_ok=True)
            chart_path.write_bytes(b"fake image")

    def fake_write_or_update_config(*, instrument_type, config_path, values):
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("# fake config\n", encoding="utf-8")
        return config_path

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(selector, "detect_instrument_type", lambda *_args, **_kwargs: "stock")
    monkeypatch.setattr(selector, "resolve_config_path", lambda *_args, **_kwargs: config_path)
    monkeypatch.setattr(selector, "load_or_update_daily_data", fake_load_or_update_daily_data)
    monkeypatch.setattr(selector, "LightweightChartLevelSelectorUI", FakeUI)
    monkeypatch.setattr(selector, "write_or_update_config", fake_write_or_update_config)
    monkeypatch.setattr(selector, "_save_session_state", lambda *_args, **_kwargs: None)

    result = selector.run_level_selector(["ABC.WA", "--instrument", "stock"])

    assert calls == [False, True]
    assert result["data_path"] == str(csv_path)
    assert "2026-06-10" in csv_path.read_text(encoding="utf-8")


def test_yahoo_quote_page_row_fills_history_lag(monkeypatch):
    base = _df("2026-06-11")
    quote_ts = pd.Timestamp("2026-06-12 17:10", tz="Europe/Warsaw").timestamp()

    def fake_quote(symbol):
        assert symbol == "PCO.WA"
        return {
            "exchangeTimezoneName": "Europe/Warsaw",
            "regularMarketTime": quote_ts,
            "regularMarketOpen": 34.5,
            "regularMarketDayHigh": 35.0,
            "regularMarketDayLow": 34.2,
            "regularMarketPrice": 34.8,
            "regularMarketVolume": 515100,
        }

    monkeypatch.setattr(loader, "_yahoo_quote_result", fake_quote)

    merged = loader._merge_yahoo_regular_market_quote(base, "PCO.WA")

    assert list(merged["Date"].dt.strftime("%Y-%m-%d")) == ["2026-06-11", "2026-06-12"]
    latest = merged.iloc[-1]
    assert float(latest["Open"]) == 34.5
    assert float(latest["Close"]) == 34.8
    assert float(latest["Volume"]) == 515100.0


def test_yfinance_metadata_fills_quote_when_direct_quote_endpoint_fails(monkeypatch):
    base = _df("2026-08-17", "2026-08-18")

    class FakeTicker:
        fast_info = {
            "open": 167.14,
            "day_high": 168.0,
            "day_low": 160.7,
            "last_price": 166.46,
            "last_volume": 500_000,
        }

        def get_history_metadata(self):
            return {
                "regularMarketTime": pd.Timestamp("2026-08-18 15:04:35", tz="UTC").timestamp(),
                "exchangeTimezoneName": "Europe/Warsaw",
            }

    monkeypatch.setattr(loader, "_yahoo_quote_result", lambda *_args: (_ for _ in ()).throw(OSError("401")))

    merged = loader._merge_yahoo_regular_market_quote(base, "XTB.WA", ticker=FakeTicker())

    assert list(merged["Date"].dt.strftime("%Y-%m-%d")) == ["2026-08-17", "2026-08-18"]
    assert float(merged.iloc[-1]["Close"]) == 166.46
    assert float(merged.iloc[-1]["Volume"]) == 500_000


def test_single_stock_refresh_probe_uses_yahoo_missing_candle_count(monkeypatch):
    import os
    import scanner_search as scanner

    monkeypatch.delenv("STOCKHELPER_CACHE_ONLY", raising=False)
    monkeypatch.delenv("STOCKHELPER_FORCE_REMOTE_REFRESH", raising=False)
    monkeypatch.setattr(scanner, "_search_fetch_symbol", lambda ticker, group, suffix: ("PCO.WA", "stock"))
    monkeypatch.setattr(
        scanner,
        "_stock_yahoo_freshness_probe",
        lambda fetch_symbol: (1, "2026-06-11", "2026-06-12", "PCO.WA"),
    )

    def fail_generic_probe(*_args, **_kwargs):
        raise AssertionError("stock probes should use Yahoo candle counts, not generic remote probe")

    monkeypatch.setattr(scanner, "has_new_remote_data", fail_generic_probe)

    assert scanner._should_refresh_group_data("single", ["PCO"], None) is True
    assert os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") == "1"


def test_stock_group_refreshes_same_day_candle_while_market_is_open(monkeypatch, capsys):
    import os
    import scanner_search as scanner

    monkeypatch.delenv("STOCKHELPER_CACHE_ONLY", raising=False)
    monkeypatch.delenv("STOCKHELPER_FORCE_REMOTE_REFRESH", raising=False)
    monkeypatch.setattr(scanner, "_search_fetch_symbol", lambda ticker, group, suffix: (ticker, "stock"))
    monkeypatch.setattr(
        scanner,
        "_stock_yahoo_freshness_probe",
        lambda fetch_symbol: (0, "2026-08-13", "2026-08-13", fetch_symbol),
    )
    monkeypatch.setattr(scanner, "_is_market_session_open", lambda *args, **kwargs: True)

    assert scanner._should_refresh_group_data("DAX40", ["BNR.DE"], ".DE") is True
    assert os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") == "1"
    assert "today's Yahoo candle is updated" in capsys.readouterr().out


def test_allsearch_ichimoku_three_yahoo_probes_refresh_whole_market_on_changed_candle(monkeypatch, tmp_path):
    import os
    import scanner_search as scanner

    members = ["AAA", "BBB", "CCC", "DDD"]
    cached = _df("2026-08-12", "2026-08-13")
    changed = cached.copy()
    changed.loc[changed.index[-1], "Close"] += 0.01
    for ticker in members:
        cached.to_csv(tmp_path / f"{ticker}.csv", index=False)

    monkeypatch.setenv("STOCKHELPER_ALLSEARCH_ICHIMOKU_PROBES", "1")
    monkeypatch.delenv("STOCKHELPER_CACHE_ONLY", raising=False)
    monkeypatch.delenv("STOCKHELPER_FORCE_REMOTE_REFRESH", raising=False)
    monkeypatch.setattr(scanner.random, "sample", lambda population, k: members[:k])
    monkeypatch.setattr(scanner, "_search_fetch_symbol", lambda ticker, *_args: (ticker, "stock"))
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda symbol, *_args: tmp_path / f"{symbol}.csv")
    monkeypatch.setattr(
        scanner,
        "_yahoo_download_window",
        lambda symbol, *_args, **_kwargs: (changed if symbol == "CCC" else cached, symbol, None),
    )

    assert scanner._should_refresh_group_data("DAX40", members, ".DE") is True
    assert os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") == "1"
    assert "STOCKHELPER_CACHE_ONLY" not in os.environ


def test_allsearch_ichimoku_three_exact_yahoo_probes_keep_cached_market(monkeypatch, tmp_path):
    import os
    import scanner_search as scanner

    members = ["AAA", "BBB", "CCC", "DDD"]
    cached = _df("2026-08-12", "2026-08-13")
    for ticker in members:
        cached.to_csv(tmp_path / f"{ticker}.csv", index=False)

    monkeypatch.setenv("STOCKHELPER_ALLSEARCH_ICHIMOKU_PROBES", "1")
    monkeypatch.delenv("STOCKHELPER_CACHE_ONLY", raising=False)
    monkeypatch.delenv("STOCKHELPER_FORCE_REMOTE_REFRESH", raising=False)
    monkeypatch.setattr(scanner.random, "sample", lambda population, k: members[:k])
    monkeypatch.setattr(scanner, "_search_fetch_symbol", lambda ticker, *_args: (ticker, "stock"))
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda symbol, *_args: tmp_path / f"{symbol}.csv")
    monkeypatch.setattr(
        scanner,
        "_yahoo_download_window",
        lambda symbol, *_args, **_kwargs: (cached.copy(), symbol, None),
    )

    assert scanner._should_refresh_group_data("DAX40", members, ".DE") is False
    assert os.environ.get("STOCKHELPER_CACHE_ONLY") == "1"
    assert "STOCKHELPER_FORCE_REMOTE_REFRESH" not in os.environ


def test_allsearch_ichimoku_probe_ignores_csv_float_round_trip_noise():
    import scanner_search as scanner

    cached = ("2026-08-18", 0.4600000083446502, 0.4695000052452087, 0.4600000083446502, 0.4695000052452087, 2150.0)
    yahoo = ("2026-08-18", 0.46000000834465027, 0.46950000524520874, 0.46000000834465027, 0.46950000524520874, 2150.0)

    assert scanner._latest_candle_signatures_match(cached, yahoo)


def test_allsearch_ichimoku_probe_skips_yahoo_symbol_older_than_cache(monkeypatch, tmp_path):
    import os
    import scanner_search as scanner

    members = ["IPE", "AAA", "BBB", "CCC"]
    cached = _df("2026-08-17", "2026-08-18")
    older = _df("2026-08-17")
    for ticker in members:
        cached.to_csv(tmp_path / f"{ticker}.csv", index=False)

    monkeypatch.setenv("STOCKHELPER_ALLSEARCH_ICHIMOKU_PROBES", "1")
    monkeypatch.setattr(scanner, "_warsaw_daily_bulk_day", lambda: None)
    monkeypatch.setattr(scanner.random, "sample", lambda population, k: members)
    monkeypatch.setattr(scanner, "_search_fetch_symbol", lambda ticker, *_args: (ticker, "stock"))
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda symbol, *_args: tmp_path / f"{symbol}.csv")
    monkeypatch.setattr(
        scanner,
        "_yahoo_download_window",
        lambda symbol, *_args, **_kwargs: (older if symbol == "IPE" else cached, symbol, None),
    )

    assert scanner._should_refresh_group_data("WIG", members, ".WA") is False
    assert os.environ.get("STOCKHELPER_CACHE_ONLY") == "1"


def test_allsearch_wig_refreshes_stooq_bulk_before_yahoo_probe(monkeypatch):
    import os
    import scanner_search as scanner

    calls = []
    monkeypatch.setenv("STOCKHELPER_ALLSEARCH_ICHIMOKU_PROBES", "1")
    monkeypatch.delenv("STOCKHELPER_CACHE_ONLY", raising=False)
    monkeypatch.delenv("STOCKHELPER_FORCE_REMOTE_REFRESH", raising=False)
    monkeypatch.setattr(scanner, "_warsaw_daily_bulk_day", lambda: "2026-08-19")
    monkeypatch.setattr(scanner, "_stooq_bulk_already_attempted", lambda _bucket: False)

    def refresh_bulk(group_name, reason):
        calls.append((group_name, reason))
        os.environ["STOCKHELPER_FORCE_REMOTE_REFRESH"] = "1"
        return True

    monkeypatch.setattr(scanner, "_try_refresh_wig_with_stooq_bulk", refresh_bulk)
    monkeypatch.setattr(
        scanner,
        "_allsearch_ichimoku_yahoo_probe",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Yahoo probe must run after the Stooq bulk rebase")),
    )

    assert scanner._should_refresh_group_data("WIG", ["XTB"], ".WA") is True
    assert calls and calls[0][0] == "WIG"
    assert "before Yahoo newest-candle probe" in calls[0][1]
    assert os.environ.get("STOCKHELPER_FORCE_REMOTE_REFRESH") == "1"


def test_allsearch_commodity_same_day_change_uses_yahoo_only_without_stooq_ui(monkeypatch, tmp_path):
    import os
    import scanner_search as scanner

    cached = _df("2026-08-18", "2026-08-19")
    yahoo = cached.copy()
    yahoo.loc[yahoo.index[-1], ["Close", "Volume"]] = [683.75, 5362]
    csv_path = tmp_path / "ZW_F.csv"
    cached.to_csv(csv_path, index=False)

    monkeypatch.setenv("STOCKHELPER_ALLSEARCH_ICHIMOKU_PROBES", "1")
    monkeypatch.setattr(scanner.random, "sample", lambda population, k: list(population))
    monkeypatch.setattr(scanner, "_search_fetch_symbol", lambda *_args: ("ZW.F", "commodity"))
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(
        scanner,
        "_yahoo_download_window",
        lambda *_args, **_kwargs: (yahoo.copy(), "ZW=F", None),
    )

    assert scanner._should_refresh_group_data("commodities", ["WHEAT"], None) is True
    assert os.environ.get("STOCKHELPER_YAHOO_LATEST_ONLY") == "1"
    assert os.environ.get("STOCKHELPER_MARKET_REFRESH_SYMBOLS") == ""
    assert "STOCKHELPER_FORCE_REMOTE_REFRESH" not in os.environ


def test_commodity_yahoo_latest_only_persists_same_day_without_stooq_download(monkeypatch, tmp_path):
    csv_path = tmp_path / "ZW_F.csv"
    cached = _df("2026-08-18", "2026-08-19")
    cached.to_csv(csv_path, index=False)
    yahoo = cached.copy()
    yahoo.loc[yahoo.index[-1], ["Close", "Volume"]] = [683.75, 5362]

    monkeypatch.setenv("STOCKHELPER_YAHOO_LATEST_ONLY", "1")
    monkeypatch.delenv("STOCKHELPER_FORCE_REMOTE_REFRESH", raising=False)
    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(
        loader,
        "_yahoo_download_window",
        lambda *_args, **_kwargs: (yahoo.copy(), "ZW=F", None),
    )
    monkeypatch.setattr(
        loader,
        "_download_remote",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Stooq UI must not run for a same-day Yahoo update")),
    )

    loaded, written_path, info = loader.load_or_update_daily_data("ZW.F", "commodity")

    assert info["source"] == "cache+yahoo"
    assert float(loaded.iloc[-1]["Close"]) == 683.75
    assert float(pd.read_csv(written_path).iloc[-1]["Volume"]) == 5362


def test_allsearch_commodity_two_missing_yahoo_dates_targets_only_that_instrument_for_stooq(monkeypatch, tmp_path):
    import os
    import scanner_search as scanner

    cached = _df("2026-08-17")
    yahoo = _df("2026-08-17", "2026-08-18", "2026-08-19")
    csv_path = tmp_path / "ZW_F.csv"
    cached.to_csv(csv_path, index=False)

    monkeypatch.setenv("STOCKHELPER_ALLSEARCH_ICHIMOKU_PROBES", "1")
    monkeypatch.setattr(scanner.random, "sample", lambda population, k: list(population))
    monkeypatch.setattr(scanner, "_search_fetch_symbol", lambda *_args: ("ZW.F", "commodity"))
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(
        scanner,
        "_yahoo_download_window",
        lambda *_args, **_kwargs: (yahoo.copy(), "ZW=F", None),
    )

    assert scanner._should_refresh_group_data("commodities", ["WHEAT"], None) is True
    assert os.environ.get("STOCKHELPER_YAHOO_LATEST_ONLY") == "1"
    assert os.environ.get("STOCKHELPER_MARKET_REFRESH_SYMBOLS") == "ZW.F"
    assert "STOCKHELPER_FORCE_REMOTE_REFRESH" not in os.environ


def test_targeted_forex_rebase_fetches_only_incremental_stooq_window(monkeypatch, tmp_path):
    csv_path = tmp_path / "EURUSD.csv"
    cached = _df("2025-02-20", "2026-08-17")
    cached.to_csv(csv_path, index=False)
    calls = []

    monkeypatch.setenv("STOCKHELPER_FORCE_REMOTE_REFRESH", "1")
    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(
        loader,
        "update_stooq_history_with_playwright",
        lambda **kwargs: (calls.append(kwargs) or _df("2026-08-17", "2026-08-18")),
    )
    monkeypatch.setattr(
        loader,
        "_yahoo_download_window",
        lambda *_args, **_kwargs: (_df("2026-08-18", "2026-08-19"), "EURUSD=X", None),
    )

    df, source, *_rest = loader._download_remote("EURUSD", "forex", None, "auto")

    assert calls[0]["lookback_days"] == 30
    assert source == "stooq_web+yahoo"
    assert list(df["Date"].dt.strftime("%Y-%m-%d")) == ["2026-08-17", "2026-08-18", "2026-08-19"]


def test_market_session_open_uses_local_market_hours():
    from datetime import UTC, datetime
    import scanner_search as scanner

    assert scanner._is_market_session_open(
        "stock", "DAX40", "BNR.DE", now=datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
    )
    assert not scanner._is_market_session_open(
        "stock", "DAX40", "BNR.DE", now=datetime(2026, 8, 13, 5, 0, tzinfo=UTC)
    )


def test_repeated_stock_load_refreshes_same_day_yahoo_candle(monkeypatch, tmp_path):
    csv_path = tmp_path / "CSGP.US.csv"
    first = _df("2026-08-11", "2026-08-12")
    first.to_csv(csv_path, index=False)
    refreshed = first.copy()
    refreshed.loc[refreshed.index[-1], ["High", "Close", "Volume"]] = [32.0, 31.5, 9000]
    calls = []

    monkeypatch.setattr(loader, "local_csv_path_for_symbol", lambda *_args: csv_path)
    monkeypatch.setattr(
        loader,
        "_yahoo_download",
        lambda *_args, **_kwargs: (calls.append(True) or refreshed.copy(), "CSGP", "CoStar Group"),
    )
    loader._SESSION_REFRESHED_KEYS.add(("stock", "CSGP.US", False))

    loaded, _, info = loader.load_or_update_daily_data("CSGP.US", "stock")

    assert len(calls) == 1
    assert info["source"] == "yahoo"
    assert float(loaded.iloc[-1]["Close"]) == 31.5
    assert float(pd.read_csv(csv_path).iloc[-1]["Volume"]) == 9000


def test_allsearch_fibo_snapshot_does_not_refresh_same_day_candle(monkeypatch, tmp_path):
    import scanner_search as scanner

    csv_path = tmp_path / "BNR.DE.csv"
    cached = _df("2026-08-12", "2026-08-13")
    cached.to_csv(csv_path, index=False)
    monkeypatch.setenv("STOCKHELPER_CACHE_ONLY", "1")
    monkeypatch.setenv("STOCKHELPER_SNAPSHOT_CACHE_ONLY", "1")
    monkeypatch.setattr(scanner, "local_csv_path_for_symbol", lambda *_args: csv_path)

    # The scanner still invokes its loader wrapper, but strict snapshot mode
    # must remain cache-only all the way through that call.
    def cached_loader(**kwargs):
        assert os.environ.get("STOCKHELPER_CACHE_ONLY") == "1"
        return cached, csv_path, {"source": "cache"}

    monkeypatch.setattr(scanner, "_load_daily_data_with_retries", cached_loader)
    loaded, _, meta = scanner._load_full_cached_history_for_scan("BNR.DE", "stock")

    assert meta["source"] == "cache"
    assert list(loaded["Date"].dt.strftime("%Y-%m-%d")) == ["2026-08-12", "2026-08-13"]


def test_allsearch_fibo_snapshot_ignores_leftover_commodity_refresh_targets(monkeypatch):
    import scanner_search as scanner

    monkeypatch.setenv("STOCKHELPER_COMMODITIES_REFRESH_TICKERS", "PLATINUM,OIL,GOLD")
    monkeypatch.setenv("STOCKHELPER_SNAPSHOT_CACHE_ONLY", "1")

    assert scanner._commodity_refresh_targets_for_scan("commodities") == set()

    monkeypatch.delenv("STOCKHELPER_SNAPSHOT_CACHE_ONLY")
    assert scanner._commodity_refresh_targets_for_scan("commodities") == {
        "PLATINUM",
        "OIL",
        "GOLD",
    }


def test_yahoo_only_download_keeps_about_18_months(monkeypatch):
    dates = pd.date_range("2025-01-01", periods=700, freq="D")
    full = _df(*(d.strftime("%Y-%m-%d") for d in dates))

    def fake_window(symbol, instrument_type, *, period):
        assert period == "max"
        return full, "AAPL", "Apple Inc."

    monkeypatch.setattr(loader, "_yahoo_download_window", fake_window)

    df, candidate, name = loader._yahoo_download("AAPL.US", "stock")

    assert candidate == "AAPL"
    assert name == "Apple Inc."
    assert df["Date"].min() == pd.Timestamp("2025-05-30")
    assert df["Date"].max() == pd.Timestamp("2026-12-01")
    assert len(df) == 551


def test_sp500_display_name_uses_us500_index_cache(monkeypatch, tmp_path):
    index_dir = tmp_path / "indexes"
    index_dir.mkdir()
    csv_path = index_dir / "US500.csv"
    _df("2025-01-02", "2026-08-06").to_csv(csv_path, index=False)
    monkeypatch.setitem(loader.DATA_DIR_BY_INSTRUMENT, "index", index_dir)
    monkeypatch.setenv("STOCKHELPER_CACHE_ONLY", "1")

    loaded, resolved_path, info = loader.load_or_update_daily_data(
        symbol="S&P500",
        instrument_type="commodity",
        fetch_older_data=True,
    )

    assert resolved_path == csv_path
    assert list(loaded["Date"].dt.strftime("%Y-%m-%d")) == ["2025-01-02", "2026-08-06"]
    assert info["source"] == "cache"


def test_sp500_display_aliases_resolve_to_us500_csv():
    for alias in ("S&P500", "S&P 500", "SP500"):
        assert loader.local_csv_path_for_symbol(alias, "commodity").name == "US500.csv"


def test_chart_canonicalizes_gpp_cloud_entry_to_far_edge_breakout():
    from chart_program.level_selector import _canonical_scanner_breakout_date

    rows = 90
    df = _df(*(pd.date_range("2025-12-01", periods=rows, freq="D").strftime("%Y-%m-%d")))
    # Make the shifted cloud deterministic for the final transition candles.
    df.loc[:, ["Open", "High", "Low", "Close"]] = [40.0, 44.0, 38.0, 40.0]
    df.loc[84:, "Date"] = pd.to_datetime(["2026-04-15", "2026-04-16", "2026-04-17", "2026-04-20", "2026-04-21", "2026-04-22"])
    df.loc[84:, "Close"] = [40.2, 40.4, 40.8, 41.0, 42.0, 42.2]

    corrected = _canonical_scanner_breakout_date(df, "2026-04-15", "long")

    assert corrected == "2026-04-21"
