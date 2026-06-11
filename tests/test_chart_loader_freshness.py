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
    result = import_stooq_wig_bulk_zip(zip_path, stocks_dir=stocks_dir, commodities_dir=commodities_dir)

    assert result["written"] == 1
    assert result["indices_written"] == 1
    assert (stocks_dir / "ABC_WA.csv").exists()
    wig20_csv = commodities_dir / "WIG20.csv"
    assert wig20_csv.exists()
    assert not (commodities_dir / "MWIG40.csv").exists()
    assert pd.read_csv(wig20_csv)["Close"].iloc[-1] == 2805


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
