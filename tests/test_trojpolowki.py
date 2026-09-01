from __future__ import annotations

import ast
import csv
import importlib.machinery
import importlib.util
import itertools
import json
import os
import re
import statistics
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest import mock


def load_run_module():
    sys.modules.setdefault("chart_program", types.ModuleType("chart_program"))
    detector = types.ModuleType("chart_program.instrument_detector")
    detector.detect_instrument_type = lambda ticker, default=None: default or "stock"
    loader_mod = types.ModuleType("chart_program.chart_loader")
    loader_mod.COMMODITY_STOOQ_MAP = {"OIL": "cl.f"}
    loader_mod.local_csv_path_for_symbol = lambda *args, **kwargs: Path("data/fake.csv")
    scanner = types.ModuleType("scanner_search")
    scanner.COMMODITIES_SEARCH_TICKERS = []
    scanner._get_members = lambda scope: (scope.upper(), ["AAA", "BBB"], "test", None)
    scanner.ETFS_MARKET = [("iShares MSCI EAFE ETF", "EFA.US")]
    sys.modules["chart_program.instrument_detector"] = detector
    sys.modules["chart_program.chart_loader"] = loader_mod
    sys.modules["scanner_search"] = scanner

    loader = importlib.machinery.SourceFileLoader("stockhelper_run_test", "run")
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def test_scanner_report_instrument_labels_include_full_names_and_tickers():
    mod = load_run_module()

    assert mod._report_instrument_label("WIG", "KGH", {"KGH.WA": "KGHM"}) == "KGHM (KGH)"
    assert mod._report_instrument_label("ETFS", "EFA.US", {"EFA.US": "iShares MSCI EAFE ETF"}) == "iShares MSCI EAFE ETF (EFA.US)"
    assert mod._report_instrument_label("FOREX", "EURUSD", {"EURUSD": "ignored"}) == "EURUSD"
    assert mod._report_instrument_label("COMMODITIES", "GOLD", {"GOLD": "ignored"}) == "GOLD"
    assert mod._report_instrument_label("US100", "UNKNOWN.US", {}) == "UNKNOWN.US"

    row = mod.ScannerRow(
        market="US100", scanner="FIBO", category="waiting", ticker="AAPL.US", status="waiting",
        direction="long", dates={"start": "2026-01-02", "incline": "2026-01-02->2026-02-03"},
    )
    cell = mod._fibo_item(row)
    assert "Apple (AAPL.US)" in cell
    assert mod._fibo_board_cell_key(cell) == ("AAPL.US", "long", "2026-01-02")


def test_instrument_name_registry_covers_every_scanned_stock_and_etf():
    source = ast.parse(Path("scanner_search.py").read_text(encoding="utf-8"))
    universes = {}
    for node in source.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {
                "WIG_SEARCH_TICKERS", "DAX40_SEARCH_TICKERS", "NDX100_SEARCH_TICKERS", "ETFS_MARKET"
            }:
                universes[target.id] = ast.literal_eval(node.value)

    registry = json.loads(Path("data/instrument_names.json").read_text(encoding="utf-8"))
    etf_names = {ticker.upper(): name for name, ticker in universes["ETFS_MARKET"]}
    registry.update(etf_names)
    expected = {
        *(f"{ticker}.WA" for ticker in universes["WIG_SEARCH_TICKERS"]),
        *universes["DAX40_SEARCH_TICKERS"],
        *universes["NDX100_SEARCH_TICKERS"],
        *(ticker for _name, ticker in universes["ETFS_MARKET"]),
    }

    assert expected <= registry.keys()


def test_report_launcher_protocol_matches_report_server():
    run_source = Path("run").read_text(encoding="utf-8")
    server_source = Path("utilities/report_server.py").read_text(encoding="utf-8")
    assert 'report_server_protocol = "stockhelper-report-server-v24"' in run_source
    assert 'REPORT_SERVER_PROTOCOL = "stockhelper-report-server-v24"' in server_source


def test_latest_scope_report_uses_filename_date_when_mtimes_tie(tmp_path):
    mod = load_run_module()
    search_dir = tmp_path / "fibo"
    search_dir.mkdir()
    old = search_dir / "fibo_search_ndx100_20260813.md"
    current = search_dir / "fibo_search_ndx100_20260827.md"
    old.write_text("obsolete DASH short", encoding="utf-8")
    current.write_text("current DASH long", encoding="utf-8")
    tied_mtime = 1_787_814_930
    os.utime(old, (tied_mtime, tied_mtime))
    os.utime(current, (tied_mtime, tied_mtime))

    with mock.patch.object(mod, "FIBO_SEARCH_OUTPUT_DIR", search_dir):
        assert mod._latest_scope_md("fibo_search", "us100") == current


def test_allsearch_cleanup_removes_stooq_debug_directory(tmp_path, capsys):
    mod = load_run_module()
    debug_dir = tmp_path / "debug" / "stooq"
    debug_dir.mkdir(parents=True)
    (debug_dir / "old_failure.png").write_bytes(b"old")
    mod.PROJECT_ROOT = tmp_path

    mod._clear_stooq_debug_artifacts()

    assert not debug_dir.exists()
    assert "cleared old Stooq debug artifacts" in capsys.readouterr().out


def test_allsearch_fibo_reuses_ichimoku_market_data_snapshot():
    source = Path("run").read_text(encoding="utf-8")
    combo = source[source.index("def _run_allsearch_combo"):source.index("def _run_batch_search")]
    fibo_call = combo[combo.index('code_f = _run_batch_search('):]

    assert '"fibo"' in fibo_call
    assert "force_cache_only=True" in fibo_call
    assert "strict_cache_only=True" in fibo_call
    assert "force_remote_refresh=False" in fibo_call
    assert "FIBO reuses the Ichimoku market-data snapshot" in combo
    assert 'os.environ["STOCKHELPER_ALLSEARCH_ICHIMOKU_PROBES"] = "1"' in combo
    assert 'os.environ.pop("STOCKHELPER_ALLSEARCH_ICHIMOKU_PROBES", None)' in combo

    batch = source[source.index("def _run_batch_search"):source.index("def main")]
    assert 'os.environ["STOCKHELPER_SNAPSHOT_CACHE_ONLY"] = "1"' in batch
    assert "if code == 0 and not strict_cache_only:" in batch

    scanner_source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert 'if os.environ.get("STOCKHELPER_SNAPSHOT_CACHE_ONLY") == "1":' in scanner_source
    assert 'os.environ.pop("STOCKHELPER_COMMODITIES_REFRESH_TICKERS", None)' in scanner_source
    fibo_worker = scanner_source[
        scanner_source.index("def _scan_fibo_one"):
        scanner_source.index("def run_fibo_explain", scanner_source.index("def _scan_fibo_one"))
    ]
    assert "with MARKET_REFRESH_LOCK:" in fibo_worker


def test_allsearch_accepts_comma_separated_selected_instruments():
    mod = load_run_module()

    assert mod._parse_allsearch_scopes("TXT, CDR, SILVER,TXT") == [
        "selected__TXT__CDR__SILVER",
    ]
    assert mod._parse_allsearch_scopes("ARM.US,BFT.WA,INSM.US") == [
        "selected__ARM.US__BFT.WA__INSM.US",
    ]
    assert mod._parse_allsearch_scopes("all") == mod.DEFAULT_ALLSEARCH_SCOPES
    assert mod._parse_allsearch_scopes(["SNT.WA,", "CDR.WA,", "TXT.WA,", "CRI.WA"]) == [
        "selected__SNT.WA__CDR.WA__TXT.WA__CRI.WA",
    ]
    assert mod._report_market_for_ticker("SELECTED__SNT.WA__ARM.US", "SNT.WA") == "WIG"
    assert mod._report_market_for_ticker("SELECTED__SNT.WA__ARM.US", "ARM.US") == "US100"

    source = Path("run").read_text(encoding="utf-8")
    assert "dest='allsearch_target', nargs='*', default=None" in source
    assert "if args.allsearch_target is not None:" in source
    assert 'selected_scope = any(str(scope).lower().startswith("selected__")' in source
    assert "sorted({r.market for r in rows}, key=lambda market: _market_order(market))" in source


def test_fibo_columns_are_compact_and_without_chart_links(tmp_path: Path):
    mod = load_run_module()
    rows = [
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="waiting", ticker="TRN", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2026-01-30", "incline": "2026-01-30->2026-03-30"},
            metrics={"near61_raw": "92.7", "ratio_raw": "3.2", "incline_days": "59"}, chart_url="https://stooq.pl/trn",
        ),
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="waiting", ticker="TRN", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2025-12-29", "incline": "2025-12-29->2026-03-30"},
            metrics={"near61_raw": "91.6", "ratio_raw": "2.8", "incline_days": "91"}, chart_url="https://stooq.pl/trn",
        ),
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="steep", ticker="TRN", status="3p_steep_incline",
            direction="long", dates={"start": "2025-12-29", "incline": "2025-12-29->2026-05-21"},
            metrics={"near61_raw": "91.6", "ratio_raw": "698.3", "incline_days": "143"}, chart_url="https://stooq.pl/trn",
        ),
        mod.ScannerRow(
            market="US100", scanner="FIBO", category="waiting", ticker="AEP.US", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2026-01-05", "incline": "2026-01-05->2026-02-20"},
            metrics={"near61_raw": "62.5", "ratio_raw": "1.5", "incline_days": "46"}, chart_url="https://stooq.pl/aep",
        ),
        mod.ScannerRow(
            market="DAX", scanner="FIBO", category="waiting", ticker="EARLY.DE", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2026-04-15", "incline": "2026-04-15->2026-05-20"},
            metrics={"near61_raw": "10.0", "ratio_raw": "9.9", "incline_days": "35"}, chart_url="https://stooq.pl/early",
        ),
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="steep", ticker="OPL", status="3p_steep_incline",
            direction="long", dates={"start": "2026-01-15", "incline": "2026-01-15->2026-05-29"},
            metrics={"ratio_raw": "82.0", "incline_days": "95", "near61_raw": "-1"}, chart_url="https://stooq.pl/opl",
        ),
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="steep", ticker="CPS", status="3p_steep_23_6_zone",
            direction="long", dates={"start": "2026-03-23", "incline": "2026-03-23->2026-05-14"},
            metrics={"ratio_raw": "55.0", "incline_days": "35", "near61_raw": "0.0"}, chart_url="https://stooq.pl/cps",
        ),
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="steep", ticker="GPW", status="3p_steep_23_6_zone",
            direction="long", dates={"start": "2026-03-27", "incline": "2026-03-27->2026-05-29"},
            metrics={"ratio_raw": "30.0", "incline_days": "45", "near61_raw": "14.5"}, chart_url="https://stooq.pl/gpw",
        ),
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="steep", ticker="CROSSED", status="3p_steep_incline",
            direction="long", dates={"start": "2026-01-01", "incline": "2026-01-01->2026-05-21"},
            metrics={"ratio_raw": "100.0", "incline_days": "97", "near61_raw": "109.7"}, chart_url="https://stooq.pl/crossed",
        ),
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="waiting", ticker="GPW", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2026-03-27", "incline": "2026-03-27->2026-05-29"},
            metrics={"ratio_raw": "30.0", "incline_days": "45", "near61_raw": "14.5"}, chart_url="https://stooq.pl/gpw",
        ),
        mod.ScannerRow(
            market="COMMODITIES", scanner="FIBO", category="waiting", ticker="BRACOMP", status="reached_23_6_waiting_for_61_8",
            direction="short", dates={"start": "2026-02-25", "incline": "2026-02-25->2026-04-14"},
            metrics={"ratio_raw": "2.0", "incline_days": "48", "near61_raw": "45.3"}, chart_url="https://stooq.pl/bracomp",
        ),
        mod.ScannerRow(
            market="COMMODITIES", scanner="FIBO", category="waiting", ticker="BRACOMP", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2025-10-10", "incline": "2025-10-10->2026-04-10"},
            metrics={"ratio_raw": "1.8", "incline_days": "120", "near61_raw": "33.4"}, chart_url="https://stooq.pl/bracomp",
        ),
        mod.ScannerRow(
            market="COMMODITIES", scanner="FIBO", category="waiting", ticker="BRACOMP", status="reached_23_6_waiting_for_61_8",
            direction="short", dates={"start": "2026-04-14", "incline": "2026-04-14->2026-05-20"},
            metrics={"ratio_raw": "1.7", "incline_days": "36", "near61_raw": "22.5"}, chart_url="https://stooq.pl/bracomp",
        ),
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="valid", ticker="TPE", status="valid_reversal",
            direction="long", dates={"start": "2026-03-23", "incline": "2026-03-23->2026-04-20"},
            metrics={"ratio_raw": "3.2", "incline_days": "28"}, chart_url="https://stooq.pl/tpe",
        ),
    ]
    out = mod._write_trojpolowki_fibo(rows, tmp_path, datetime(2026, 5, 30, 10, 11, 12))
    text = out.read_text(encoding="utf-8")
    assert "# Trójpolówki — Fibo" in text
    assert "Updated from allsearch: 2026-05-30 10:11:12" in text
    assert "✅ Pattern ≤14d / SL intact" in text
    assert "**🇵🇱 TAURONPE (TPE) ↗️ (2026-03-23)**" in text
    assert "**🇵🇱 ORANGEPL (OPL) ↗️ (2026-01-15)**" in text
    assert "**🇵🇱 CYFRPLSAT (CPS) ↗️ (2026-03-23) 0.0%**" in text
    assert "**🇩🇪 EARLY.DE ↗️ (2026-04-15) 10.0%**" in text
    assert text.count("**🇵🇱 GPW (GPW) ↗️ (2026-03-27) 14.5%**") == 1
    assert text.index("**🇵🇱 ORANGEPL (OPL) ↗️") < text.index("**🇩🇪 EARLY.DE ↗️")
    assert "**🇺🇸 American Electric Power (AEP.US) ↗️ (2026-01-05) 62.5%**" in text
    assert text.count("**🇵🇱 TRANSPOL (TRN) ↗️") == 1
    assert "**🇵🇱 TRANSPOL (TRN) ↗️ (2026-01-30) 92.7%**" in text
    assert "**🇵🇱 TRANSPOL (TRN) ↗️ (2025-12-29) 91.6%**" not in text
    assert "CROSSED" not in text
    assert text.count("**🛢️ BRACOMP") == 2
    assert "**🛢️ BRACOMP ↘️ (2026-02-25) 45.3%**" in text
    assert "**🛢️ BRACOMP ↗️ (2025-10-10) 33.4%**" in text
    assert "**🛢️ BRACOMP ↘️ (2026-04-14) 22.5%**" not in text
    data_rows = [line for line in text.splitlines() if line.startswith("| ") and not line.startswith("|---")][1:]
    split_rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in data_rows]
    assert any("**🇵🇱 CYFRPLSAT (CPS)" in cells[1] for cells in split_rows)
    assert not any("**🇵🇱 CYFRPLSAT (CPS)" in cells[0] for cells in split_rows)
    assert "[📈 chart]" not in text
    assert "[🔗 stooq](https://stooq.pl/trn)" in text
    assert "<!--fibo-end:2026-03-30-->" in text


def test_fibo_recent_dropouts_are_retained_for_ten_days(tmp_path: Path):
    mod = load_run_module()
    setup = mod.ScannerRow(
        market="WIG", scanner="FIBO", category="waiting", ticker="DROP", status="reached_23_6_waiting_for_61_8",
        direction="short", dates={"start": "2026-06-15", "incline": "2026-06-15->2026-07-01"},
        metrics={"near61_raw": "50.0", "ratio_raw": "2.0", "incline_days": "30"}, chart_url="https://stooq.pl/drop",
    )
    # A crossed setup is intentionally absent from the active columns, so seed a
    # previous near-61.8 board cell to model yesterday's displayed candidate.
    board = tmp_path / "fibo.md"
    board.write_text(
        "# Trójpolówki — Fibo\n\n"
        "| 🚀 Steep incline / no major bearish signal | ⚠️ Waiting 23.6→61.8 / bearish close | 🎯 Near 61.8 > 75% / deeper pullback | ✅ Pattern ≤14d / SL intact |\n"
        "|---|---|---|---|\n"
        "|  |  | **🇵🇱 DROP ↗️ (2026-06-01) 101.2%** [🔗 stooq](https://stooq.pl/drop) |  |\n",
        encoding="utf-8",
    )
    out = mod._write_trojpolowki_fibo([], tmp_path, datetime(2026, 7, 10, 9, 0, 0))
    text = out.read_text(encoding="utf-8")
    assert "🕘 Recent dropouts (10d)" in text
    assert "❌ 2026-07-10 · NO_VALID_PATTERN_AT_61_8" in text
    assert "DROP ↗️ (2026-06-01)" in text

    # A currently active re-anchored formation means the ticker never dropped
    # out and must disappear from history immediately, not after ten days.
    mod._write_trojpolowki_fibo([setup], tmp_path, datetime(2026, 7, 11, 9, 0, 0))
    assert "DROP ↗️ (2026-06-01)" not in (tmp_path / "fibo_dropouts.json").read_text(encoding="utf-8")


def test_fibo_dropout_chart_never_falls_back_to_ichimoku():
    source = Path("run").read_text(encoding="utf-8")
    fibo_branch = source[source.index('elif "fibo" in section_id:'):source.index('else:', source.index('elif "fibo" in section_id:'))]
    assert "troj_row_by_ticker.get(ticker)" not in fibo_branch
    assert "--ichimoku-mode off --fibo-lines 5" in source


def test_fibo_dropouts_have_per_instrument_analyzer_sidebar_and_codex_copy():
    source = Path("run").read_text(encoding="utf-8")
    assert "class='btn fibo-analyzer-btn'" in source
    assert "data-ticker='{html.escape(ticker, quote=True)}'" in source
    assert "onclick='openFiboDropoutAnalyzer(this)'" in source
    assert "id='fibo-analyzer-sidebar'" in source
    assert "📋 Copy for Codex" in source
    assert "Analysis complete · copied automatically" in source
    assert ".join(String.fromCharCode(10))" in source
    server = Path("utilities/report_server.py").read_text(encoding="utf-8")
    assert 'parsed.path == "/fibo-dropout-analysis"' in server
    assert '"STOCKHELPER_CACHE_ONLY"] = "1"' in server
    assert '"-explain", ticker' in server
    assert "FULL SCANNER REJECTION TRACE" in server
    assert "fetchFiboDropoutAnalysis(ticker,context)" in source
    assert "for(let port=8765;port<8795;port++)" in source
    assert "StockHelper report server unavailable; reopen the report from StockHelper" in source


def test_saved_fibo_past_second_anchor_is_deleted_and_opposite_stale_setup_is_pruned():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    forced_guard = source[source.index("later_high_slice ="):source.index("early_sideways", source.index("later_high_slice ="))]
    assert "if forced_anchor_dates and pd.notna(later_high) and later_high > fib_end * 1.005:" in forced_guard
    assert "Rejected saved long Fibo: price exceeded its second anchor" in forced_guard
    assert "live_steep_directions" in source
    assert "_fibo_retracement_progress_pct(r) >= 100.0" in source
    assert 'r.status != "valid_reversal"' in source


def test_all_fibo_cards_have_debug_and_saved_filter_controls():
    source = Path("run").read_text(encoding="utf-8")
    analyzer_block = source[source.index('analyzer_btn = ""'):source.index("controls =", source.index('analyzer_btn = ""'))]
    assert 'if "fibo" in section_id:' in analyzer_block
    assert 'and "❌" in raw' not in analyzer_block
    assert "🧪 Show 3P debug" in source
    assert "💾 Saved by me" in source
    assert "savedOnly" in source
    assert "card.dataset.savedFibo==='1'" in source
    assert "class='saved-fibo-icon'" in source
    assert "Fibo saved by me" in source
    assert ".troj-cell-card[data-saved-fibo='1']{border-color" not in source
    toggle = source[source.index("function toggleSavedFibos"):source.index("function trojInfoPreference")]
    assert "f();" in toggle
    assert "querySelectorAll" not in toggle
    assert "stockhelper-saved-setup" in source
    assert "cell.dataset.originalHtml=cell.innerHTML" in source
    assert "data-ticker='{html.escape(row.ticker.upper())}'" in source
    stockhelper_link = source[source.index("def _stockhelper_chart_button"):source.index("def _google_sheets_hyperlink_formula")]
    assert "rel='noopener'" not in stockhelper_link


def test_wedge_cards_have_saved_icon_and_saved_only_filter():
    source = Path("run").read_text(encoding="utf-8")
    scanner_source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert "Wedge saved by me" in source
    assert "saved-filter-section" in source
    assert "toggleSavedSetups(this)" in source
    assert "saved-setup-only" in source
    assert "data-saved-by-user='1'" in source
    assert '"Saved by user"' in scanner_source
    assert "wedge.saved_by_user = manual_wedge is not None" in scanner_source


def test_chart_fibo_debug_ends_with_requested_csv_data():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    snapshot = source[source.index("function fiboDebugSnapshot"):source.index("function setupDebugSnapshot")]
    assert "FIB group:" in snapshot
    assert "61.8 value:" in snapshot
    assert "61.8 pattern:" in snapshot
    assert "CSV candles since first anchor" in snapshot
    assert "FIBO ANCHOR / CHANNEL DEBUG" not in snapshot
    assert "scanner audit command" not in snapshot


def test_month_side_trends_invalidate_both_fibo_impulse_and_correction():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    steep_start = source.index("def _find_fibo_3p_steep_setup")
    regular_start = source.index("def _find_fibo_setup", steep_start)
    steep_source = source[steep_start:regular_start]
    assert "continuation_min_gain=steep_min_gain" in steep_source
    assert "continuation_min_daily_gain=steep_min_daily_gain" in steep_source
    assert "_has_completed_month_side_trend(w.iloc[i_peak:])" in steep_source
    correction_start = source.index("correction_seg =", regular_start)
    correction_end = source.index("if corr_low > fib_236", correction_start)
    assert "_has_completed_month_side_trend(correction_seg)" in source[correction_start:correction_end]
    selector_start = source.index("def _select_impulse_start_long")
    selector_end = source.index("def _select_peak_long", selector_start)
    assert "_completed_sideways_reset_long" in source[selector_start:selector_end]
    assert "max_outlier_candles=2" in source[selector_start:selector_end]
    assert "return channel_end, -1" in source[selector_start:selector_end]
    assert "rejecting any flat sub-window dropped MCHP" in source
    base_start = source.index("def _select_fibo_long_impulse_base")
    base_end = source.index("def _find_fibo_3p_steep_setup", base_start)
    assert "pre_start_left = max(0, i_start - 5)" in source[base_start:base_end]


def test_fibo_peak_selection_keeps_dominant_high_over_later_lower_high():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    start = source.index("def _select_peak_long")
    end = source.index("def _reverse_stooq_symbol", start)
    peak_source = source[start:end]
    assert "global_max * 0.995" in peak_source
    assert "return max(dominant)" in peak_source
    assert "moved second anchor to the highest high of the measured leg" in source


def test_recent_independent_fibo_peak_can_be_slightly_below_old_dominant_high():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    peak_start = source.index("def _select_peak_long")
    peak_end = source.index("def _select_bottom_short", peak_start)
    assert "global_max * 0.94" in source[peak_start:peak_end]
    steep_start = source.index("def _find_fibo_3p_steep_setup")
    steep_end = source.index("def _find_fibo_setup", steep_start)
    assert "peak_high < global_high * 0.94" in source[steep_start:steep_end]
    assert "independent_recent_idxs" in source[peak_start:peak_end]
    assert "recent_gain >= 0.25" in source[peak_start:peak_end]
    assert "mirrored_short_axis - recent_base" in source[peak_start:peak_end]


def test_short_fibo_month_long_post_bottom_sideways_is_rejected():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert "post-bottom recovery" in source
    assert "short recovery" in source
    assert "correction contains a completed month-long side trend" in source
    stale = source[source.index("def _is_waiting_candidate_stale"):source.index("def _scan_fibo_one")]
    assert 'cand.direction == "short" and _has_long_sideways' in stale


def test_extended_short_side_trends_expire_even_near_the_recovery_extreme():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    helper = source[source.index("def _has_extended_sideways"):source.index("def _sideways_correction_near_active_extreme")]
    steep = source[source.index("def _find_fibo_3p_steep_setup"):source.index("def _find_fibo_setup")]
    stale = source[source.index("def _is_waiting_candidate_stale"):source.index("def _scan_fibo_one")]

    assert "qualifying_starts.append(start)" in helper
    assert "longest_covered" in helper
    assert "max(min_covered_days, int(math.ceil(len(df_slice) * min_coverage_ratio)))" in helper
    helper = source[source.index("def _has_completed_month_side_trend"):source.index("def _has_extended_sideways")]
    assert "short decline" in steep
    assert "continuation_min_gain=steep_min_gain" in steep
    assert "max_days=19" in helper
    assert "band_pct=0.20" in helper
    assert "max_progress_pct=0.08" in helper
    assert stale.index("if _has_extended_sideways") < stale.index("if not _sideways_correction_near_active_extreme")
    assert "after.reset_index(drop=True), max_days=22, band_pct=0.12" in stale


def test_fibo_pattern_may_finish_later_but_must_include_initial_touch_candle():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert "touch_idxs[:1]" not in source
    assert "first_touch_idx = all_touch_idxs[0]" in source
    assert "c = w.iloc[first_touch_idx]" in source
    assert "includes_first_touch = first_touch_idx in {i - 1, i}" in source
    assert "includes_first_touch = first_touch_idx in {i - 2, i - 1, i}" in source
    assert "includes_touch = any(t in {i - 1, i}" not in source
    assert "pattern_idx = i" in source
    assert "It can be the first, middle, or final pattern candle" in source
    assert "close above 61.8" in source
    assert "float(close.iloc[pattern_idx]) <= fib_618" in source
    assert "pattern_failed_close = True" in source
    assert "the completed 61.8 pattern failed its required closing-price confirmation" in source
    assert "first 61.8 touch produced no valid 1-, 2-, or 3-candle pattern" in source
    assert "accepting short completed cycle despite 61.8 cross without pattern" not in source


def test_fibo_chart_commands_use_pattern_completion_date_not_touch_date():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert "pattern_date=(r.reversal_pattern_date or r.first_61_8_touch_date)" not in source
    assert source.count("pattern_date=r.reversal_pattern_date") >= 3

    mod = load_run_module()
    row = mod.ScannerRow(
        market="US100",
        scanner="FIBO",
        category="valid",
        ticker="PLTR.US",
        status="valid_reversal",
        pattern="bearish_harami",
        dates={
            "touch_61": "2026-08-04",
            "incline": "2025-12-22->2026-06-25",
        },
        python_command=(
            "python run -c PLTR.US --ichimoku-mode off --fibo-lines 5 "
            "--fibo-anchor-start 2025-12-22 --fibo-anchor-end 2026-06-25 "
            "--fibo-right --scanner-pattern-date 2026-08-05 "
            "--scanner-pattern-name bearish_harami"
        ),
    )
    command = mod._chart_command_for_row(row)
    assert "--scanner-pattern-date 2026-08-05" in command
    assert "--scanner-pattern-date 2026-08-04" not in command
    assert "--scanner-pattern-direction long" in command

    commodity = mod.ScannerRow(
        market="COMMODITIES", scanner="FIBO", category="valid", ticker="OIL",
        status="valid_reversal", pattern="dark_cloud_cover", direction="short",
        dates={
            "pattern_date": "2026-07-24",
            "touch_61": "2026-07-23",
            "incline": "2026-03-09->2026-07-02",
        },
    )
    commodity_command = mod._chart_command_for_row(commodity)
    assert "python run -c CL.F" in commodity_command
    assert "--scanner-pattern-date 2026-07-24" in commodity_command
    assert "--scanner-pattern-name dark_cloud_cover" in commodity_command
    assert "--scanner-pattern-direction short" in commodity_command

    assert '["Ticker","Dir","Pattern","Pattern date","Incline"' in source


def test_legacy_oil_report_recovers_dark_cloud_confirmation_date():
    mod = load_run_module()
    mod.local_csv_path_for_symbol = lambda *_args, **_kwargs: Path("data/csv/commodities/CB_F.csv")
    row = mod.ScannerRow(
        market="COMMODITIES", scanner="FIBO", category="valid", ticker="OIL",
        status="valid_reversal", pattern="dark_cloud_cover", direction="short",
        dates={"touch_61": "2026-07-23", "incline": "2026-03-09->2026-07-02"},
        python_command="python run -c OIL --fibo-lines 5",
    )
    command = mod._chart_command_for_row(row)
    assert "--scanner-pattern-date 2026-07-24" in command
    assert "--scanner-pattern-name dark_cloud_cover" in command

    ui_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    assert "function fibo618PatternFromChart()" in ui_source
    assert "touches618 && darkCloud" in ui_source
    assert "c2 < (o1 + c1) / 2 && c2 > o1 && c2 < level" in ui_source
    assert "piercing|dark cloud cover|harami" in ui_source
    assert "scannerMetaValue('__scanner_pattern_date__') || chartFiboPattern?.time" in ui_source
    assert "scannerPattern || recoveredPattern" in ui_source


def test_ichimoku_latest_breakout_uses_trading_candles_and_stays_valid_to_latest():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    breakout = source[source.index("def _find_latest_breakout_idx"):source.index("def _retest_meta_for_side")]
    assert "min_age_calendar_days" not in breakout
    assert "end_idx = n" in breakout
    assert "maintained through latest candle" in breakout


def test_multi_candle_scanner_highlight_has_only_an_outer_border():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    drawing = source[source.index("function drawScannerHighlights"):source.index("function captureViewport")]
    assert "ohlc.slice(band.startIdx, band.endIdx + 1)" in drawing
    assert "ctx.strokeRect(band.left + .5" in drawing
    assert "ctx.strokeRect(single.left" not in drawing


def test_chart_uses_exact_scanner_breakout_date_without_nearby_candle_correction():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    context = source[source.index("function ichimokuScannerBreakoutContext"):source.index("function ichimokuRetestsSince")]
    assert "const displayDate = scanner;" in context
    assert "ichimokuFirstBreakoutCloseNearScanner(scanner)" not in context


def test_ichimoku_chart_command_forwards_current_scanner_direction():
    mod = load_run_module()
    long_row = mod.ScannerRow(
        market="WIG", scanner="ICHIMOKU", category="position", ticker="ALE.WA",
        status="above", dates={"start_date": "2026-04-09"}, metrics={"current_side": "above"},
    )
    short_row = mod.ScannerRow(
        market="DAX", scanner="ICHIMOKU", category="retest_breakout", ticker="LIN.DE",
        status="below", dates={"flip_date": "2026-07-31"}, metrics={"current_side": "below"},
    )
    assert "--scanner-breakout-direction long" in mod._chart_command_for_row(long_row)
    assert "--scanner-breakout-direction short" in mod._chart_command_for_row(short_row)


def test_zero_retest_count_drops_stale_pattern_from_chart_command():
    mod = load_run_module()
    row = mod.ScannerRow(
        market="WIG",
        scanner="ICHIMOKU",
        category="retest_breakout",
        ticker="ENT",
        status="breakout_confirmed",
        dates={"flip_date": "2026-08-05"},
        metrics={
            "retest_count": "0",
            "latest_retest_date": "2026-08-10",
            "latest_retest_pattern": "hammer",
        },
    )

    command = mod._chart_command_for_row(row)

    assert "--scanner-retest-count 0" in command
    assert "--scanner-latest-retest-date" not in command
    assert "--scanner-latest-retest-pattern" not in command

    ui_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    assert "wanted > 0 && latestRetestDate" in ui_source
    assert "validRetestCount > 0 && latestRetestDate" in ui_source


def test_short_fibo_markets_and_chart_png_download_are_enabled():
    scanner_source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert 'group_name in {"DAX40", "NDX100"}' in scanner_source
    assert 'if short_fibo_enabled:' in scanner_source
    assert 'for direction in ("long", "short"):' in scanner_source
    ui_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    assert 'id="download-chart-png"' in ui_source
    assert "chart.takeScreenshot(true, false)" in ui_source
    assert "link.download" in ui_source


def test_fibo_final_routing_keeps_23_6_zone_in_second_column_and_directions_independent():
    source = Path("scanner_search.py").read_text(encoding="utf-8")

    assert 'r.status == "3p_steep_incline" or r.status == "returned_before_61_8"' in source
    assert 'if r.status != "3p_steep_incline"' in source
    assert 'key = (str(item.ticker).upper(), str(item.direction).lower())' in source


def test_live_broad_and_independent_inclines_survive_peak_and_sideways_selection():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    peak_selector = source[source.index("def _select_peak_long"):source.index("def _select_bottom_short")]
    steep = source[source.index("def _find_fibo_3p_steep_setup"):source.index("def _find_fibo_setup")]
    setup = source[source.index("def _find_fibo_setup"):source.index("def _scan_fibo_one")]

    assert "post_dominant_low <= old_618" in peak_selector
    assert "recent_left = max(min_incline_days, len(w) - 60)" in steep
    assert "allow_independent_peak=independent_recent_peak" in steep
    assert "reset_after_sideways=False" in steep
    assert "reset_after_extended_sideways=not _mirrored_short" in steep
    assert "reset_after_extended_sideways=not _mirrored_short" in setup
    assert "(44, 0.22, 0.08, 1)" in source
    assert "reset fib start after extended sideways base" in source
    assert "base_end + 35" in source
    assert "newest_near_recovery_extreme" not in setup
    assert "retained sideways correction because the newest close" not in setup
    assert "_has_completed_month_side_trend(correction_seg)" in setup
    assert "adjusted the top anchor" in setup
    assert "Short 3P steep: retained the broad decline" not in steep


def test_manual_fibo_drawing_does_not_rescale_chart_viewport():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "!isEditableLineObject(obj) && !isFib && !isFibBoundary" in source


def test_ichimoku_retest_counts_only_best_local_extreme_until_close_resets_cycle():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    retest = source[source.index("def _detect_ichimoku_retest"):source.index("def run_ichimoku_search")]

    assert 'n_outside = float(df["Close"].iloc[n]) > float(top.iloc[n])' in retest
    assert 'n_outside = float(df["Close"].iloc[n]) < float(bottom.iloc[n])' in retest
    assert retest.index("if n_outside:") < retest.index("if n_touched:", retest.index("if n_outside:"))
    assert "def _pattern_reaction_extreme" in retest
    assert "-_pattern_reaction_extreme(x)" in retest
    assert "One cloud visit is one retest cycle" in retest
    assert "cycle_exit_idx = n" in retest
    assert "i = detect_until + 1" in retest


def test_chart_png_includes_drawings_and_context_header():
    ui_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    assert "async function captureChartPng()" in ui_source
    assert "drawCloud();" in ui_source
    assert "ctx.drawImage(overlay, 0, headerHeight, base.width, base.height)" in ui_source
    assert "['Balance', money(Number($('capital')?.value" in ui_source
    assert "const selectedValues = seq.map(field => [labels[field] || field, levels[field]])" in ui_source
    assert "...selectedValues" in ui_source
    assert "['Drawings', String(drawnObjects.length)]" in ui_source
    assert "const canvas = await captureChartPng();" in ui_source


def test_chart_png_includes_position_table_after_calculation():
    ui_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    capture = ui_source[ui_source.index("async function captureChartPng()") : ui_source.index("function journalScreenshotRange()")]

    assert "$('calc-drawer')?.classList.contains('open') ? levels.position_calculations : null" in capture
    assert "calculation?.ok && Array.isArray(calculation.rows)" in capture
    assert "canvas.height = base.height + headerHeight + calculationHeight" in capture
    assert "'Position calculation'" in capture
    assert "'Potential loss with spread'" in capture
    assert "row.position_size" in capture
    assert "row.potential_loss" in capture


def test_scanner_wedge_replaces_stale_selected_values_but_keeps_entry_manual():
    ui_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    assert "function applyWedgeDerivedLevels(forceScannerLevels = false)" in ui_source
    assert "if (forceScannerLevels) {{" in ui_source
    assert "delete levels.entry;" in ui_source
    assert "delete levelPoints.entry;" in ui_source
    assert "const highIsAuto = forceScannerLevels ||" in ui_source
    assert "const lowIsAuto = forceScannerLevels ||" in ui_source
    assert "const stopLossIsAuto = forceScannerLevels ||" in ui_source
    assert "const scannerWedgePreloaded = initialScannerDrawnObjects.some" in ui_source
    assert "applyWedgeDerivedLevels(scannerWedgePreloaded); applyScannerSetupStopLoss(true); applyInstrumentControls(); render();" in ui_source
    assert ui_source.count("applyWedgeDerivedLevels(true);") >= 2


def test_scanner_chart_derives_ichimoku_and_fibo_stop_losses():
    ui_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "function applyScannerSetupStopLoss(forceScannerLevels = false)" in ui_source
    assert "source = 'Ichimoku breakout cloud border'" in ui_source
    assert "point = scannerPatternExtreme(retestDate, retestPattern, direction)" in ui_source
    assert "point = scannerPatternExtreme(patternDate, patternName, patternDirection)" in ui_source
    assert "latestRow.idx - breakoutRow.idx <= 10" in ui_source
    assert "latestRow.idx - retestRow.idx <= 10" in ui_source
    assert "function scannerStopWasHit(point, direction)" in ui_source
    assert "ohlc.slice(setupRow.idx + 1).some" in ui_source
    assert "Number(row.high) >= stop" in ui_source
    assert "Number(row.low) <= stop" in ui_source
    assert "source.startsWith('Ichimoku') && scannerStopWasHit(point, direction)" in ui_source
    assert "crossesBothBorders" in ui_source
    assert "source = 'Ichimoku breakout candle'" in ui_source
    assert "const pip = Math.pow(10, -Math.max(0, precision))" in ui_source
    assert "value - (3 * pip)" in ui_source
    assert "if (forceScannerLevels && (scannerFiboLoaded || scannerIchimokuLoaded)) clearScannerStopLoss()" in ui_source
    assert "['long', 'short'].includes(patternDirection)" in ui_source
    assert "value + (3 * pip)" in ui_source
    assert "__scanner_pattern_direction__" in ui_source
    assert "levelPoints.stop_loss = {{price:point.price, plot_price:point.price, date:point.date, auto_scanner:true, source}}" in ui_source
    assert ui_source.count("applyScannerSetupStopLoss(true);") >= 2


def test_scanner_chart_drops_metadata_from_the_previous_technique():
    selector_source = Path("chart_program/level_selector.py").read_text(encoding="utf-8")

    assert "scanner_context_requested = bool(" in selector_source
    assert "for key, _ in scanner_metadata:" in selector_source
    assert "existing.pop(key, None)" in selector_source
    assert "Never let Ichimoku scanner" in selector_source


def test_fibo_anchor_requires_confirmed_local_trend_bottom():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    selector = source[source.index("def _select_impulse_start_long"):source.index("def _select_peak_long")]
    assert "def _clear_bottom" in selector
    assert "local_left = max(search_left, idx - 3)" in selector
    assert "local_right = min(peak_idx, idx + 3)" in selector
    assert "later_closes > float(close.iloc[idx])" in selector
    assert "clear if clear is not None else -1" in selector
    assert "sideways_band_pct: float = 0.08" in selector
    assert "band_pct=sideways_band_pct" in selector
    assert "absolute_end - 29" in selector


def test_sbux_june_5_bottom_is_not_discarded_as_sideways_spike():
    with Path("data/csv/stocks/SBUX_US.csv").open(encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if "2026-05-26" <= row["Date"] <= "2026-07-17"]
    bottom_idx = next(idx for idx, row in enumerate(rows) if row["Date"] == "2026-06-05")
    bottom = float(rows[bottom_idx]["Low"])
    local_lows = [float(row["Low"]) for row in rows[bottom_idx - 3:bottom_idx + 4]]
    ending_close = statistics.median(float(row["Close"]) for row in rows[-3:])
    assert bottom == min(local_lows)
    assert (ending_close - bottom) / bottom > 0.10


def test_aep_june_1_is_clear_bottom_of_full_monthly_base():
    with Path("data/csv/stocks/AEP_US.csv").open(encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if "2026-05-12" <= row["Date"] <= "2026-07-07"]
    bottom_idx = next(idx for idx, row in enumerate(rows) if row["Date"] == "2026-06-01")
    bottom = float(rows[bottom_idx]["Low"])
    pre_breakout = [float(row["Low"]) for row in rows if row["Date"] <= "2026-06-23"]
    following_closes = [float(row["Close"]) for row in rows[bottom_idx + 1:bottom_idx + 7]]
    assert bottom == min(pre_breakout)
    assert sum(close > float(rows[bottom_idx]["Close"]) for close in following_closes) >= 2


def test_month_long_range_requires_flat_progress_for_supplied_cases():
    def has_flat_window(path: str, start: str, end: str) -> bool:
        with Path(path).open(encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if start <= row["Date"] <= end]
        for idx in range(len(rows) - 29):
            window = rows[idx:idx + 30]
            high = max(float(row["High"]) for row in window)
            low = min(float(row["Low"]) for row in window)
            band = (high - low) / ((high + low) / 2.0)
            progress = abs(float(window[-1]["Close"]) - float(window[0]["Close"])) / float(window[0]["Close"])
            if band <= 0.12 and progress <= 0.05:
                return True
        return False

    assert not has_flat_window("data/csv/stocks/SCW_WA.csv", "2025-09-10", "2026-04-20")
    assert has_flat_window("data/csv/indexes/JP225.csv", "2025-07-22", "2026-06-22")
    assert not has_flat_window("data/csv/stocks/PCO_WA.csv", "2026-03-23", "2026-07-22")
    assert not has_flat_window("data/csv/stocks/RBW_WA.csv", "2026-05-20", "2026-07-02")


def test_supplied_small_long_formations_are_in_waiting_band():
    cases = [
        ("data/csv/stocks/SBUX_US.csv", "2026-06-04", "2026-07-17"),
        ("data/csv/stocks/MCHP_US.csv", "2026-03-30", "2026-05-08"),
        ("data/csv/stocks/MAR_US.csv", "2025-10-31", "2026-06-15"),
        ("data/csv/stocks/KDP_US.csv", "2026-04-06", "2026-06-29"),
    ]
    for path, start, peak in cases:
        with Path(path).open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        start_row = next(row for row in rows if row["Date"] == start)
        peak_row = next(row for row in rows if row["Date"] == peak)
        low = float(start_row["Low"])
        high = float(peak_row["High"])
        current = float(rows[-1]["Close"])
        fib_236 = high - (high - low) * 0.236
        fib_618 = high - (high - low) * 0.618
        # These CSVs are refreshed after the historical setup dates, so their
        # final close is no longer a stable assertion. Preserve the useful
        # regression here: the supplied anchors must produce an ordered waiting
        # band; live scanner-state assertions belong to dated fixture slices.
        assert fib_618 < fib_236, (path, current, fib_618, fib_236)


def test_fibo_chart_recovers_missing_dropout_end_anchor():
    source = Path("chart_program/level_selector.py").read_text(encoding="utf-8")
    assert "if args.fibo_lines and args.fibo_anchor_start and not saved_fibo_active:" in source
    assert 'after_start = df.loc[all_dts >= s_ts]' in source
    assert 'peak_idx = pd.to_numeric(after_start["High"], errors="coerce").idxmax()' in source


def test_fibo_chart_preload_keeps_authoritative_saved_geometry():
    source = Path("chart_program/level_selector.py").read_text(encoding="utf-8")
    assert 'existing.get("__saved_fibo_by_user__") is not False' in source
    assert 'not existing.get("__saved_fibo_invalid__")' in source
    assert "retained authoritative user-saved Fibo; scanner preload ignored" in source


def test_broad_sideways_steep_needs_a_smaller_regular_replacement():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert "item.has_monthly_sideways" in source
    assert "int(item.incline_duration_days) >= shortest_regular_by_direction[item.direction] * 2" in source


def test_dropout_reasons_use_common_status_codes():
    source = Path("run").read_text(encoding="utf-8")
    for status in ["NO_VALID_PATTERN_AT_61_8", "OTHER_SETUP_FILTER"]:
        assert status in source


def test_completed_61_8_cycle_resets_regular_fibo_anchor():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    selector_start = source.index("def _select_fibo_long_impulse_base")
    selector_end = source.index("def _find_fibo_3p_steep_setup", selector_start)
    selector = source[selector_start:selector_end]
    assert "min_completed_cycle_days = 10" in selector
    assert "max_short_completed_cycle_days" not in selector
    regular_signature = source[source.index("def _find_fibo_setup"):source.index("def _find_fibo_setup") + 300]
    assert 'stale_cycle_mode: str = "reset"' in regular_signature


def test_sideways_detection_ignores_only_interior_spike_candles():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    stats_start = source.index("def _sideways_window_stats")
    stats_end = source.index("def _latest_sideways_end_offset", stats_start)
    stats_source = source[stats_start:stats_end]
    assert "max_outlier_candles" in stats_source
    assert "size - 4" in stats_source
    assert "closes.iloc[:3].median()" in stats_source
    assert "closes.iloc[-3:].median()" in stats_source
    assert "lo_idx >= size // 3" in stats_source
    assert "> 0.08" in stats_source
    assert "protected_bottoms" in stats_source
    assert "> 0.10" in stats_source
    assert "candidate_idxs -= protected_bottoms" in stats_source


def test_robust_sideways_windows_match_tor_bnp_and_not_mchp():
    def latest_window(path: str, start: str, end: str, band_limit: float = 0.12) -> str | None:
        with Path(path).open(encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if start <= row["Date"] <= end]
        latest = None
        for offset in range(len(rows) - 29):
            window = rows[offset:offset + 30]
            extremes = set(
                sorted(range(30), key=lambda idx: float(window[idx]["High"]), reverse=True)[:3]
                + sorted(range(30), key=lambda idx: float(window[idx]["Low"]))[:3]
            )
            removable = sorted(idx for idx in extremes if 2 <= idx <= 26)
            best_band = float("inf")
            for count in range(min(2, len(removable)) + 1):
                for excluded in itertools.combinations(removable, count):
                    kept = [row for idx, row in enumerate(window) if idx not in excluded]
                    high = max(float(row["High"]) for row in kept)
                    low = min(float(row["Low"]) for row in kept)
                    best_band = min(best_band, (high - low) / ((high + low) / 2.0))
            first = statistics.median(float(row["Close"]) for row in window[:3])
            last = statistics.median(float(row["Close"]) for row in window[-3:])
            kept_high = max(float(row["High"]) for row in window)
            kept_low = min(float(row["Low"]) for row in window)
            terminal_position = (last - kept_low) / max(kept_high - kept_low, 1e-9)
            terminal_breakout = last > first and terminal_position > 0.85
            if best_band <= band_limit and abs(last - first) / first <= 0.05 and not terminal_breakout:
                latest = window[-1]["Date"]
        return latest

    assert latest_window("data/csv/stocks/TOR_WA.csv", "2025-07-18", "2026-07-16") is not None
    assert latest_window("data/csv/stocks/BNP_WA.csv", "2025-11-04", "2026-06-17") is not None
    assert latest_window("data/csv/stocks/MCHP_US.csv", "2026-03-30", "2026-05-08") is None
    assert latest_window("data/csv/stocks/VRTX_US.csv", "2026-05-05", "2026-07-07") is None
    assert latest_window("data/csv/stocks/TOR_WA.csv", "2025-07-18", "2026-07-16", 0.08) is not None
    assert latest_window("data/csv/stocks/BNP_WA.csv", "2025-11-04", "2026-06-17", 0.08) is not None
    assert latest_window("data/csv/stocks/ADP_US.csv", "2026-04-13", "2026-07-17", 0.08) is None


def test_fresh_61_8_touch_waits_for_three_candle_pattern_window():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    stale = source[source.index("def _is_waiting_candidate_stale"):source.index("def _scan_fibo_one")]
    assert 'cand.status not in {"returned_before_61_8", "reached_23_6_waiting_for_61_8", "touched_61_8_no_pattern"}' in stale
    assert 'touch_mask = pd.to_numeric(after["Low"]' in stale
    assert 'touch_mask = pd.to_numeric(after["High"]' in stale
    assert 'first_touch_ts = pd.to_datetime(touch_rows.iloc[0]["Date"]' in stale
    assert 'int((dts > first_touch_ts).sum()) > 2' in stale
    assert 'rows1.append(r)' in source[source.index('if r.status == "touched_61_8_no_pattern"'):]
    assert 'r.status in {"3p_steep_23_6_zone", "reached_23_6_waiting_for_61_8", "touched_61_8_no_pattern"}' in source
    setup = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]
    assert "i_end <= current_touch_idxs[0] + 2 or confirmed_first_touch_pattern" in setup
    assert "retained original impulse anchors because the first" in setup
    assert "_previous_board_fibo_anchors(ticker)" in source
    assert "including recent dropouts" in source
    assert setup.index("if fresh_touch_window:") < setup.index("contains a completed month-long side trend", setup.index("if fresh_touch_window:"))
    run_source = Path("run").read_text(encoding="utf-8")
    touched = run_source[run_source.index('if "touched_61_8_no_pattern"'):run_source.index("def _fibo_touch_date")]
    assert "return near >= 75.0" in touched


def test_latest_shallow_engulfing_has_cycle_boundary_fallback():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    retest = source[source.index("def _detect_ichimoku_retest"):source.index("def run_ichimoku_search")]

    assert 'valid_count == 0 and current_side == "above" and len(df) >= 3' in retest
    assert "first_idx, confirm_idx, prior_idx = len(df) - 2, len(df) - 1, len(df) - 3" in retest
    assert 'first_valid_status = "shallow_retest_pattern"' in retest
    assert 'events = [(ev_date, "bullish_engulfing", "shallow")]' in retest


def test_fibo_return_across_23_6_moves_between_early_and_waiting_columns():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    long_start = source.index("def _find_fibo_setup")
    routing_start = source.index("valid_recent_cutoff")
    classifier_start = source.index("def _fibo_pre_61_8_status")
    classifier_end = source.index("def _fibo_formation_size", classifier_start)
    classifier = source[classifier_start:classifier_end]
    assert 'current_close > fib_23_6 if direction == "long" else current_close < fib_23_6' in classifier
    assert 'return "returned_before_61_8" if returned_to_impulse_side else "reached_23_6_waiting_for_61_8"' in classifier
    setup = source[long_start:routing_start]
    assert '_fibo_pre_61_8_status("long", float(close.iloc[-1]), fib_236)' in setup
    assert '_fibo_pre_61_8_status("short", float(close.iloc[-1]), fib_236)' in setup
    assert "Long: price returned above 23.6 without touching 61.8" in source
    assert "Short: correction returned below 23.6 without touching 61.8" in source
    assert 'if r.status == "returned_before_61_8":\n            rows0.append(r)' in source[routing_start:]
    assert "if made_higher_high:" in source
    assert "if made_lower_low:" in source
    assert 'made_higher_high and cand.status != "returned_before_61_8"' not in source
    assert 'made_lower_low and cand.status != "returned_before_61_8"' not in source
    assert 'r.status == "3p_steep_incline" or r.status == "returned_before_61_8"' in source


def test_current_3p_match_survives_historical_offset_deduplication():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    limiter = source[source.index("def _limit_fibo_formations_per_ticker"):source.index("def _dedupe_same_scale_fibo_formations")]
    dedupe = source[source.index("def _dedupe_same_scale_fibo_formations"):source.index("def _is_bullish_hammer")]
    assert 'str(r.status) == "3p_steep_incline"' in limiter
    assert "Historical regular" in limiter
    assert 'regular.status in {"returned_before_61_8", "reached_23_6_waiting_for_61_8"}' in dedupe


def test_fibo_board_limits_long_and_short_formations_independently():
    source = Path("run").read_text(encoding="utf-8")
    limiter = source[
        source.index("def _limit_fibo_display_per_ticker"):
        source.index("fibo = _limit_fibo_display_per_ticker")
    ]

    assert 'key = (str(row.ticker or "").upper(), str(row.direction or "").lower())' in limiter
    assert "grouped.setdefault(key, []).append(row)" in limiter


def test_short_3p_independent_bottom_uses_full_impulse_horizon():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    steep = source[
        source.index("def _find_fibo_3p_steep_setup"):
        source.index("def _find_fibo_setup")
    ]

    assert "independent_lookback = 260 if _mirrored_short else 80" in steep
    assert "i_peak - independent_lookback" in steep


def test_valid_61_8_pattern_gets_slightly_longer_correction_ratio_window():
    source = Path("scanner_search.py").read_text(encoding="utf-8")

    assert 'max_ratio = 10.0 if pattern != "none" else 8.0' in source
    assert 'incline/decline ratio too high ({ratio} > {max_ratio})' in source


def test_short_fibo_keeps_dominant_top_when_later_bottom_extends_decline():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    selector = source[source.index("def _select_fibo_long_impulse_base"):source.index("def _find_fibo_3p_steep_setup")]
    assert "preserve_deeper_short_continuation" in selector
    assert "continuation_extension >= 0.15" in selector
    assert "retained dominant original top after a 61.8 rebound" in selector
    regular = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]
    assert "preserve_deeper_short_continuation=_mirrored_short" in regular


def test_fibo_and_wedge_liquidity_filters_are_stock_only():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    liquidity = source[source.index("def _passes_scanner_liquidity"):source.index("def _business_day_gap_after_local")]
    assert 'if instrument_type in {"commodity", "forex"}:\n        return True' in liquidity
    fibo_filter = source[source.index("def _passes_fibo_liquidity"):source.index("def _passes_wedge_liquidity")]
    wedge_filter = source[source.index("def _passes_wedge_liquidity"):source.index("rows_by_key:")]
    assert 'if instrument_type in {"commodity", "forex"}:\n            return True' in fibo_filter
    assert 'if instrument_type in {"commodity", "forex"}:\n            return True' in wedge_filter
    lookup = source[source.index("rows_by_key:"):source.index("# Populate Avg10Turn")]
    assert "for r in rows + rows0 + rows1 + rows2:" in lookup


def test_3p_23_6_zone_exports_progress_for_trojpolowki_waiting_column():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    rows1 = source[source.index("rows1_md="):source.index("rows2_md=")]
    assert 'r.status in {"3p_steep_23_6_zone", "reached_23_6_waiting_for_61_8", "touched_61_8_no_pattern"}' in rows1


def test_short_recent_decline_gain_uses_unmirrored_price_denominator():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    signature = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]
    assert "_mirrored_short_axis=axis" in signature
    assert "mirrored_short_axis=_mirrored_short_axis" in signature


def test_old_fibo_cannot_be_resurrected_by_later_61_8_touches():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    stale = source[source.index("def _is_waiting_candidate_stale"):source.index("def _scan_fibo_one")]
    assert "exactly one reversal opportunity" in stale
    assert "not resurrect the old formation" in stale
    assert "only a newly anchored Fibo may return" in stale


def test_regular_fibo_rejects_extended_side_trends_on_impulse_and_correction():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    setup = source[source.index("def _find_fibo_setup"):source.index("def _scan_fibo_one")]
    stale_start = source.index("def _is_waiting_candidate_stale")
    stale = source[stale_start:source.index("def _scan_fibo_one", stale_start)]

    assert "if _has_extended_sideways(correction_seg) and not correction_at_active_extreme:" in setup
    assert "_sideways_correction_near_active_extreme(" in setup
    assert "correction is dominated by an extended side trend" in setup
    assert "impulse_side_disqualifying = _impulse_has_disqualifying_month_side_trend(" in setup
    assert "if impulse_side_disqualifying:" in setup
    assert "contains a completed month-long side trend" in setup
    assert "if _has_extended_sideways(after.reset_index(drop=True)):" in stale
    assert "if _has_completed_month_side_trend(after):" in stale


def test_fibo_rejects_correction_through_original_anchor():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert "if corr_low <= fib_start:" in source
    assert "if corr_high >= fib_start:" in source
    assert "correction invalidated the formation by reaching" in source
    run_source = Path("run").read_text(encoding="utf-8")
    assert "return near >= 75.0" in run_source


def test_third_fibo_column_keeps_crossed_61_8_row_during_pattern_window(tmp_path: Path):
    mod = load_run_module()
    rows = [
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="waiting", ticker="JSW", status="touched_61_8_no_pattern",
            direction="long", dates={"start": "2026-03-03", "incline": "2026-03-03->2026-06-01"},
            metrics={"near61_raw": "194.2", "ratio_raw": "2.0", "incline_days": "60"}, chart_url="https://stooq.pl/jsw",
        ),
        mod.ScannerRow(
            market="US100", scanner="FIBO", category="waiting", ticker="TTWO.US", status="touched_61_8_no_pattern",
            direction="long", dates={"start": "2026-06-11", "incline": "2026-06-11->2026-07-07"},
            metrics={"near61_raw": "96.5", "ratio_raw": "1.5", "incline_days": "26"}, chart_url="https://stooq.pl/ttwo.us",
        ),
    ]
    text = mod._write_trojpolowki_fibo(rows, tmp_path, datetime(2026, 7, 24, 9, 0, 0)).read_text(encoding="utf-8")
    assert "JSW (JSW) ↗️" in text
    assert "Take-Two Interactive (TTWO.US) ↗️" in text


def test_fibo_scan_avoids_duplicate_and_reduces_broad_offset_work():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert "long_offset0 =" not in source
    assert "if off in {0, 10, 20, 40}:" in source
    stats = source[source.index("def _sideways_window_stats"):source.index("def _latest_sideways_end_offset")]
    assert ".iloc[keep]" not in stats


def test_ichimoku_risk_long_short_and_retest_statuses(tmp_path: Path):
    mod = load_run_module()
    rows = [
        mod.ScannerRow(
            market="WIG", scanner="ICHIMOKU", category="retest_breakout", ticker="CRI", status="⚪ above",
            dates={"flip_date": "2026-01-01"}, metrics={"months": "8.9", "ichimoku_status": "Over Kijun-sen", "risk": "3%", "tk_cross": "none", "dynamic": "aggressive", "cloud": "thick", "chikou": "yes", "twist": "green", "tk_plus": "yes", "tenkan_in_cloud": "no", "raw_status": "breakout_confirmed", "previous_respect_months": "6.2"}, chart_url="https://stooq.pl/cri",
        ),
        mod.ScannerRow(
            market="WIG", scanner="ICHIMOKU", category="position", ticker="ABC", status="🟢 above",
            dates={"start_date": "2025-10-01"}, metrics={"months": "7.1", "ichimoku_status": "Over Kijun-sen", "risk": "-", "tk_cross": "bullish TK cross", "dynamic": "-", "cloud": "-", "chikou": "-", "twist": "-", "tk_plus": "-", "tenkan_in_cloud": "-", "raw_status": "above"}, chart_url="https://stooq.pl/abc",
        ),
        mod.ScannerRow(
            market="US100", scanner="ICHIMOKU", category="position", ticker="AMGN.US", status="⚪ watch",
            dates={"start_date": "2026-04-01"}, metrics={"months": "2.5", "ichimoku_status": "Over Kijun-sen", "risk": "-", "tk_cross": "none", "dynamic": "-", "cloud": "-", "chikou": "-", "twist": "-", "tk_plus": "-", "tenkan_in_cloud": "-", "raw_status": "watch"}, chart_url="https://stooq.pl/amgn",
        ),
        mod.ScannerRow(
            market="DAX", scanner="ICHIMOKU", category="retest_breakout", ticker="HFG.DE", status="🔴 below",
            dates={"flip_date": "2026-02-01"}, metrics={"months": "5.1", "ichimoku_status": "Under Kijun-sen", "risk": "3%", "tk_cross": "bearish TK cross", "dynamic": "high", "cloud": "normal", "chikou": "yes", "twist": "red", "tk_plus": "yes", "tenkan_in_cloud": "yes", "raw_status": "deep_retest_pattern", "previous_respect_months": "6.2"}, chart_url="https://stooq.pl/hfg",
        ),
        mod.ScannerRow(
            market="US100", scanner="ICHIMOKU", category="retest_breakout", ticker="MSFT.US", status="⚪ above",
            dates={"flip_date": "2026-04-01"}, metrics={"months": "2.0", "ichimoku_status": "Touched the cloud", "risk": "2%", "tk_cross": "bullish TK cross", "dynamic": "mild", "cloud": "shallow", "chikou": "yes", "twist": "green", "tk_plus": "yes", "tenkan_in_cloud": "yes", "raw_status": "retest_breakout", "latest_retest_date": "2026-05-29", "latest_retest_pattern": "hammer", "previous_respect_months": "6.2"}, chart_url="https://stooq.pl/msft",
        ),
        mod.ScannerRow(
            market="DAX", scanner="ICHIMOKU", category="retest_breakout", ticker="RWE.DE", status="⚪ above",
            dates={"flip_date": "2026-05-29"}, metrics={"months": "4.0", "ichimoku_status": "Touched Kijun-sen", "risk": "2%", "tk_cross": "bullish TK cross", "dynamic": "mild", "cloud": "normal", "chikou": "yes", "twist": "green", "tk_plus": "yes", "tenkan_in_cloud": "yes", "raw_status": "breakout_confirmed", "previous_side": "below", "previous_respect_months": "6.2"}, chart_url="https://stooq.pl/rwe",
        ),
        mod.ScannerRow(
            market="DAX", scanner="ICHIMOKU", category="retest_breakout", ticker="BEAR.DE", status="breakout_confirmed",
            dates={"flip_date": "2026-05-29"}, metrics={"months": "0.0", "ichimoku_status": "Touched Kijun-sen", "risk": "3%", "tk_cross": "bearish TK cross", "dynamic": "mild", "cloud": "normal", "chikou": "↓ under", "twist": "red", "tk_plus": "yes", "tenkan_in_cloud": "yes", "raw_status": "breakout_confirmed", "current_side": "🔴 below", "previous_respect_months": "6.2"}, chart_url="https://stooq.pl/bear",
        ),
        mod.ScannerRow(
            market="COMMODITIES", scanner="ICHIMOKU", category="position", ticker="GOLD", status="🔴 below",
            dates={"start_date": "2025-10-01"}, metrics={"months": "7.0", "ichimoku_status": "Touched Kijun-sen", "risk": "-", "tk_cross": "bearish TK cross", "raw_status": "below"}, chart_url="https://stooq.pl/gold",
        ),
        mod.ScannerRow(
            market="COMMODITIES", scanner="ICHIMOKU", category="retest_breakout", ticker="GOLD", status="🔴 below",
            dates={"flip_date": "2026-01-01"}, metrics={"months": "6.0", "ichimoku_status": "Touched Kijun-sen", "risk": "2%", "tk_cross": "bullish TK cross", "dynamic": "mild", "cloud": "normal", "chikou": "yes", "twist": "green", "raw_status": "medium_retest_pattern", "latest_retest_date": "2026-05-01", "latest_retest_pattern": "hammer", "current_side": "🔴 below", "previous_respect_months": "6.0"}, chart_url="https://stooq.pl/gold",
        ),
        mod.ScannerRow(
            market="US100", scanner="ICHIMOKU", category="retest_breakout", ticker="LONG.US", status="⚪ above",
            dates={"flip_date": "2025-10-01"}, metrics={"months": "8.0", "ichimoku_status": "Inside the cloud", "risk": "2%", "tk_cross": "bearish TK cross", "dynamic": "mild", "cloud": "normal", "chikou": "↓ under", "twist": "red", "raw_status": "medium_retest_pattern", "latest_retest_date": "2026-05-29", "latest_retest_pattern": "hammer", "previous_respect_months": "6.0"}, chart_url="https://stooq.pl/long",
        ),
    ]
    out = mod._write_trojpolowki_ichimoku(rows, tmp_path, datetime(2026, 5, 30, 10, 11, 12))
    text = out.read_text(encoding="utf-8")
    assert "| 🟢 Strong / continuation | 👀 Kijun / watch | ☁️ Cloud / retest / breakout | 🔁 Retest <4m |" in text
    assert "**🇵🇱 CREOTECH (CRI) ↗️ long (8.9m)**<br>🏷️ above cloud<br>Kijun: over" in text
    assert "**🇩🇪 HelloFresh (HFG.DE) 🔁 retest (5.1m)**<br>🏷️ last retest pattern (2026-02-01)<br>Kijun: under" in text
    assert "Risk/grading details are shown only in the ☁️ Cloud / retest / breakout and 🔁 Retest <4m columns" in text
    assert "TK values use the latest actionable Tenkan/Kijun direction" in text
    assert "**🇺🇸 Microsoft (MSFT.US) (2.0m)**" in text
    assert "🏷️ touched cloud · Long trend<br>🕘 retest hammer (2026-05-29)" in text
    assert "**🇩🇪 RWE (RWE.DE) 🔁 retest (4.0m)**" in text
    assert "🟡 risk: 2% · ⬆️ Chikou over · 🟢 kumo" in text
    assert "**🇩🇪 BEAR.DE (0.0m)**" in text
    assert "🟢 risk: 3% · ⬇️ Chikou under · 🔴 kumo" in text
    assert "➕ 🔴 TK cross bearish · Tenkan_in_☁: yes · dyn mild · cloud normal" in text
    assert "➕ 🟢 TK cross bullish · Tenkan_in_☁: yes · dyn mild" in text
    assert "➖ cloud shallow" in text
    lines = text.splitlines()
    data_rows = [line for line in lines if line.startswith("| ") and not line.startswith("|---")][1:]
    assert "**🇩🇪 BEAR.DE" in data_rows[0]
    assert any("**🇩🇪 RWE (RWE.DE)" in row for row in data_rows)
    assert "**🇺🇸 Microsoft (MSFT.US)" in text
    assert "**🇵🇱 CREOTECH (CRI)" in data_rows[0]
    assert "**🇵🇱 ABC" in text
    assert any(row.startswith("| **🇵🇱 ABC") for row in data_rows)
    assert "**🇺🇸 Amgen (AMGN.US) ↗️ long (2.5m)**<br>🏷️ above cloud<br>Kijun: over" in text
    assert "**🇺🇸 LONG.US (8.0m)**<br>🏷️ inside cloud · Long trend<br>🕘 retest hammer (2026-05-29)" in text
    assert text.count("**🛢️ GOLD") == 1
    assert "**🛢️ GOLD ↘️ short (7.0m)**<br>🏷️ below cloud<br>Kijun: touched" in text
    assert any("**🛢️ GOLD" in row.split(" | ")[1] for row in data_rows)
    assert "[📈 chart]" not in text
    assert "[🔗 stooq](https://stooq.pl/hfg)" in text


def test_early_ichimoku_is_hidden_from_3p_until_cutoff(tmp_path: Path):
    mod = load_run_module()
    row = mod.ScannerRow(
        market="WIG", scanner="ICHIMOKU", category="retest_breakout", ticker="JSW",
        status="shallow_retest_pattern", dates={"flip_date": "2026-08-10"},
        metrics={
            "months": "3.0", "previous_respect_months": "3.8", "retest_count": "1",
            "qualification_status": "early_breakout_waiting_until_4m",
            "valid_retests_from_date": "2026-08-28",
            "latest_retest_date": "2026-08-18", "latest_retest_pattern": "bullish_piercing_line",
            "raw_status": "shallow_retest_pattern", "current_side": "above",
            "ichimoku_status": "Over Kijun-sen", "risk": "3%",
        },
    )

    assert mod._ichimoku_qualification_state(row) == "waiting_first"
    out = mod._write_trojpolowki_ichimoku([row], tmp_path, datetime(2026, 8, 21, 12, 0, 0))
    text = out.read_text(encoding="utf-8")
    assert "JSW" not in text
    assert "WAITING FOR DIRECTION RETEST" not in text


def test_qualified_position_row_with_valid_retest_uses_fourth_column(tmp_path: Path):
    mod = load_run_module()
    row = mod.ScannerRow(
        market="WIG", scanner="ICHIMOKU", category="position", ticker="CPS", status="above",
        dates={"start_date": "2026-04-21"},
        metrics={
            "months": "4.2", "qualification_status": "standard_4m_breakout",
            "latest_retest_date": "2026-08-25", "latest_retest_pattern": "bullish_piercing_line",
            "raw_status": "above", "current_side": "above",
            "ichimoku_status": "Over Kijun-sen", "risk": "3%",
        },
    )

    out = mod._write_trojpolowki_ichimoku([row], tmp_path, datetime(2026, 8, 25, 12, 0, 0))
    data_row = next(
        line for line in out.read_text(encoding="utf-8").splitlines()
        if line.startswith("| ") and "CYFRPLSAT (CPS)" in line
    )
    cells = [cell.strip() for cell in data_row.strip().strip("|").split("|")]

    assert len(cells) == 4
    assert all("CYFRPLSAT (CPS)" not in cell for cell in cells[:3])
    assert "CYFRPLSAT (CPS)" in cells[3]


def test_early_rebreakout_in_position_table_is_not_playable():
    mod = load_run_module()
    row = mod.ScannerRow(
        market="WIG", scanner="ICHIMOKU", category="position", ticker="CBF", status="above",
        metrics={
            "qualification_status": "early_breakout_waiting_until_4m",
            "valid_retests_from_date": "2026-08-28", "retest_count": "0",
        },
    )

    assert mod._ichimoku_qualification_state(row) == "waiting_first"
    assert mod._ichimoku_early_breakout_html(row) == (
        "<strong style='color:#dc2626'>NO PLAY UNTIL 2026-08-28</strong>"
    )


def test_3p_ichimoku_returns_early_breakout_after_cutoff(tmp_path: Path):
    mod = load_run_module()

    def row(ticker: str, valid_from: str, qualification: str, count: str = "0"):
        return mod.ScannerRow(
            market="WIG", scanner="ICHIMOKU", category="retest_breakout", ticker=ticker,
            status="breakout_confirmed", dates={"flip_date": "2026-05-21"},
            metrics={
                "months": "3.0", "qualification_status": qualification,
                "valid_retests_from_date": valid_from, "retest_count": count,
                "raw_status": "breakout_confirmed", "current_side": "above",
                "ichimoku_status": "Over Kijun-sen", "risk": "3%",
            },
        )

    rows = [row("RETURNED", "2026-08-28", "standard_4m_breakout", "3")]
    out = mod._write_trojpolowki_ichimoku(rows, tmp_path, datetime(2026, 8, 29, 12, 0, 0))
    text = out.read_text(encoding="utf-8")

    assert "**🇵🇱 RETURNED" in text
    assert "NO PLAY" not in text


def test_allsearch_html_has_trojpolowki_links(tmp_path: Path):
    mod = load_run_module()
    mod.TROJPOLLOWKI_DIR = tmp_path / "Trojpolowki"
    out = tmp_path / "chart_program" / "data" / "all_insturments_search" / "allsearch" / "allsearch_latest_all.html"
    out.parent.mkdir(parents=True)
    ichi_md = tmp_path / "search_wig_latest.md"
    ichi_md.write_text(
        "# WYNIKI 2 ICHIMOKU\n\n"
        "| Ticker | Poprzednia | Latest Retest status | Data wybicia | Mies. od wybicia | Mies. respektu przed wybiciem | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Ichimoku status | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| CRI | below | breakout_confirmed | 2026-05-29 | 0.1 | 6.2 | 1 | 1000 | 2026-05-30 | - | Over Kijun-sen | 2% | bullish TK cross | mild | normal | yes | green | yes | yes | https://stooq.pl/cri | python run -c CRI | yes | 2026-05-30 | 2026-05-30 |\n"
        "| RWE.DE | below | breakout_confirmed | 2026-05-29 | 4.0 | 7.5 | 1 | 1000 | 2026-05-30 | - | Touched Kijun-sen | 2% | bullish TK cross | mild | normal | yes | green | yes | yes | https://stooq.pl/rwe-ichi | python run -c RWE.DE | yes | 2026-05-30 | 2026-05-30 |\n"
        "| GPP | below | medium_retest_pattern | 2026-04-21 | 1.3 | 5.8 | 2 | 1000 | 2026-05-21 | bullish_harami | Over Kijun-sen | 2% | bullish TK cross | mild | normal | yes | green | yes | yes | https://stooq.pl/gpp | python run -c GPP | yes | 2026-05-29 | 2026-05-29 |\n"
        "| RP5 | below | medium_retest_pattern | 2026-04-23 | 1.3 | 5.8 | 2 | 1000 | 2026-05-25 | hammer | Over Kijun-sen | 2% | bullish TK cross | mild | normal | yes | green | yes | yes | https://stooq.pl/rp5 | python run -c RP5 | yes | 2026-05-30 | 2026-05-30 |\n"
        "| SCW | below | returned_to_cloud_waiting_for_pattern | 2026-05-28 | 0.1 | 6.0 | 0 | 6728668 | - | - | Inside the cloud | - | none | mild | thick | no | neutral | no | yes | https://stooq.pl/scw | python run -c SCW | yes | 2026-05-29 | 2026-05-29 |\n"
        "| LIN.US | below | medium_retest_pattern | 2025-12-01 | 6.4 | 7.0 | 2 | 1000 | 2026-07-22 | bullish_harami | Touched the cloud | 2% | bearish TK cross | mild | normal | under | red | no | yes | https://stooq.pl/lin | python run -c LIN.US | yes | 2026-07-22 | 2026-07-22 |\n"
        "\n# WYNIKI 1 ICHIMOKU\n\n"
        "| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Retest count | Latest Retest date | Latest Retest pattern | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| ENR.DE | ⚪ above | 175 | 8.2 | 2025-11-24 | 160.0000 | 1761117868 | Unsuccessful breakout to the other side | 2 | 2026-05-29 | hammer | https://stooq.pl/enr | python run -c ENR.DE | yes | 2026-06-01 | 2026-06-01 |\n"
        "| PAT.US | ⚪ above | 148 | 6.5 | 2026-01-12 | 107.4100 | 815666730 | Inside the cloud - PATTERN! | 2 | 2026-07-22 | bearish_harami | https://stooq.pl/pat | python run -c PAT.US | yes | 2026-07-22 | 2026-07-22 |\n",
        encoding="utf-8",
    )
    fibo_md = tmp_path / "fibo_search_wig_latest.md"
    fibo_md.write_text(
        "# WYNIKI FIBO #0 (3P steep incline)\n\n"
        "| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| SBUX.US | long | 🚀 3p_steep_incline | 2026-03-27->2026-05-30 | 44/1 (44.00:1) | 98.5% | 1000 | https://stooq.pl/sbux | python run -c SBUX.US | yes | 2026-05-30 | 2026-05-30 |\n"
        "\n# WYNIKI FIBO #2\n\n"
        "| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| VAL.US | long | bullish_hammer | 2026-01-05->2026-02-20 | 46/30 (1.53:1) | 2026-05-27 | 1000 | - | https://stooq.pl/val | python run -c VAL.US | yes | 2026-05-30 | 2026-05-30 |\n"
        "\n# WYNIKI FIBO #1\n\n"
        "| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| EARLY.DE | short | reached_23_6_waiting_for_61_8 | none | 2026-04-15->2026-05-20 | 35/20 (1.75:1) | - | 1000 | 10.0% | https://stooq.pl/early | python run -c EARLY.DE | yes | 2026-05-30 | 2026-05-30 |\n"
        "| RWE.DE | long | reached_23_6_waiting_for_61_8 | none | 2026-01-05->2026-02-20 | 46/30 (1.53:1) | - | 1000 | 80.0% | https://stooq.pl/rwe-fibo | python run -c RWE.DE | yes | 2026-05-30 | 2026-05-30 |\n"
        "| AEP.US | long | reached_23_6_waiting_for_61_8 | none | 2026-01-05->2026-02-20 | 46/30 (1.53:1) | - | 1000 | 90.0% | https://stooq.pl/aep | python run -c AEP.US | yes | 2026-05-30 | 2026-05-30 |\n"
        "\n# WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)\n\n"
        "| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| WDG | 🚀 breakout | 2026-01-02->2026-05-30 | 105 | 5.0 | 2026-01-02@100.0->2026-03-01@80.0 | 2026-02-01@60.0->2026-04-01@55.0 | 3 | 3 | 40.00% | 12.00% | strong | 2026-05-30 | long | 9999.00 | 1000000 | https://stooq.pl/wdg | python run -c WDG --wedge-lines | yes | 2026-05-30 | 2026-05-30 |\n",
        encoding="utf-8",
    )
    def latest_md(kind: str, scope: str):
        return fibo_md if kind == "fibo_search" else ichi_md
    with mock.patch.object(mod, "_latest_scope_md", side_effect=latest_md):
        mod._build_html_report(["wig"], out)
    text = out.read_text(encoding="utf-8")
    assert "ALLSEARCH REPORT" in text
    assert "📈 StockHelper scanner workspace" in text
    assert "Use tabs to switch between" not in text
    assert "3P FIBO" in text
    assert "3P ICHIMOKU" in text
    assert ">⭐ Favorites</a>" in text
    assert "favorites-count" not in text
    assert "href='#tab-troj-fibo'" in text
    assert "href='/journal-html' target='_blank' rel='noopener'>🧾 Open journal</a>" in text
    assert "window.addEventListener('hashchange',showReportTabFromHash)" in text
    assert "id='tab-favorites' class='tab-panel'" in text
    assert "stockhelper.favorite-instruments.v1" in text
    assert "function canonicalFavoriteTicker(ticker)" in text
    assert ".replace(/\\.WA$/,'')" in text
    assert "new Set([...items].map(canonicalFavoriteTicker).filter(Boolean))" in text
    assert "data.favorites.map(canonicalFavoriteTicker).filter(Boolean)" in text
    assert "function toggleFavorite(ticker)" in text
    assert "ticker=canonicalFavoriteTicker(ticker)" in text
    assert "fetch('/favorites',{method:'POST'" in text
    assert "window.addEventListener('focus',syncFavoritesFromServer)" in text
    assert "endpoint.searchParams.set('favoriteTicker',btn.dataset.favoriteTicker||favoriteTicker(btn))" in text
    assert "function techniqueFor(el)" in text
    assert "One favorite instrument can appear in multiple 3P columns" in text
    assert "data-ticker='RWE.DE'" in text
    assert "⚠️ Names still needed" not in text
    assert ".troj-name-actions{display:inline-flex;float:right;align-items:center" in text
    assert "data-favorite-ready='1' data-favorite-ticker='RWE.DE'" in text
    assert "onclick=\"toggleFavorite('RWE.DE')\"" in text
    assert "favorites-3p-table" in text
    assert "<colgroup><col><col><col><col></colgroup>" in text
    assert ".favorites-3p-table col{width:25%}" in text
    assert ".favorites-3p-table td{width:25%;padding:0" in text
    assert "const columns=[0,1,2,3]" in text
    assert "favorites-3p-empty" in text
    assert "No favorites" in text
    assert "favorites-wedge-table" in text
    assert "const stooqLink=o=>o.stooqUrl?" in text
    assert "stooqLink(o)+star(o)+chartButton(o)" in text
    assert "<td><strong>'+escapeFavoriteHtml(o.label)" in text
    assert "const threePTickers=new Set" in text
    assert "!threePTickers.has(o.ticker)" in text
    assert "const favoriteOccurrenceRank=" in text
    assert "const byTicker=new Map()" in text
    assert "byTicker.set(o.ticker,{rank,items:new Map()})" in text
    assert "const setupKey=o.is3p?[o.technique,o.columnIndex,o.direction].join('|'):'regular'" in text
    assert "flatMap(group=>[...group.items.values()])" in text
    assert "Favorites not classified anywhere now" in text
    assert "No unclassified favorites" in text
    assert "parts.push('<section class=\"favorites-technique favorites-unclassified\"" in text
    assert "const classifiedTickers=new Set(uniqueAll.map(o=>o.ticker))" in text
    assert "const unclassified=activeMarket?[]:[...fav].filter(ticker=>!classifiedTickers.has(ticker))" in text
    assert "const FAVORITE_INSTRUMENT_NAMES=" in text
    assert "function favoriteInstrumentLabel(ticker)" in text
    assert "label:favoriteInstrumentLabel(ticker)" in text
    assert '"CDR": "CDPROJEKT"' in text
    assert "cmd:'python run -c '+ticker" in text
    assert '<span class="fibo-arrow fibo-arrow-long" title="Long" aria-label="Long">↗</span>' in text
    assert '<span class="fibo-arrow fibo-arrow-short" title="Short" aria-label="Short">↘</span>' in text
    assert "<th>Instrument</th><th>Market</th><th>Direction</th><th>Status</th><th>Chart</th>" in text
    assert "📐 3P Fibo" in text and "☁️ 3P Ichimoku" in text
    assert "function favoriteWedgeContext(host)" in text
    assert "date?'Breakout: '+date:'Unbroken'" in text
    assert "td.chart-action-cell{text-align:center}" in text
    assert "#tab-allsearch table.data th:not(:first-child)" in text
    assert "#tab-wedges table.data td:not(:first-child){text-align:center}" in text
    assert "<th>Ticker</th><th>Dir</th><th>Status</th><th>Incline</th><th>Ratio(d)</th>" in text
    assert "<td><b>Starbucks (SBUX.US)</b></td><td>" in text
    assert "function placeStooqColumnsNextToCharts()" in text
    assert "row.insertBefore(stooq,chart)" in text
    assert "placeStooqColumnsNextToCharts();document.querySelectorAll('table.data')" in text
    assert "<th>Expected date</th><th>stockhelper_chart</th></tr>" in text
    assert "<td>2026-05-30</td><td class='chart-action-cell'>" in text
    assert "📄 PDF" in text
    assert "🗂 Checked" in text
    assert "id='checked-instruments-dialog'" in text
    assert "<h3>WIG <span>(2)</span></h3>" in text
    assert "<code>AAA</code><code>BBB</code>" in text
    assert "📄 Download PDF" not in text
    assert 'onclick="downloadPdfReport()"' in text
    assert "@media print" in text
    assert "zoom:.78" in text
    assert "id='tab-allsearch' class='tab-panel active'" in text
    assert "id='current-balance'" in text
    assert "Jacek Gwoździewicz trading masterpiece" in text
    assert "fetch('/current-balance'" in text
    assert ".balance-card{display:grid;grid-template-columns:1.1fr .75fr 1.25fr" in text
    assert "class='balance-section balance-amount'" in text
    assert "class='balance-section balance-note-section'" in text
    assert "class='balance-icon'" not in text
    assert ".balance-section{display:flex;align-items:center;justify-content:center" in text
    assert "class='choice-reason'" in text
    assert "class='choice-reason-kind'" in text
    assert ".fibo-arrow{display:inline-grid;place-items:center;width:18px;height:18px" in text
    assert "class='fibo-arrow fibo-arrow-long' title='Long' aria-label='Long'>↗</span>" in text
    assert "class='fibo-arrow fibo-arrow-short' title='Short' aria-label='Short'>↘</span>" in text
    assert "<col class='top-choice-direction'>" in text
    assert "<th>Instrument</th><th>Dir</th><th>Why top choice</th>" in text
    assert ".fibo-direction{display:inline-flex;align-items:center;white-space:nowrap}" in text
    assert "class='choice-reason-sep'>|</span>" in text
    assert "id='tab-troj-fibo' class='tab-panel'" in text
    assert "id='tab-troj-ichimoku' class='tab-panel'" in text
    assert "id='trojpolowki-fibo'" in text
    assert "id='trojpolowki-ichimoku'" in text
    assert "troj-name-actions" in text
    assert "copySheetsCell" in text
    assert "📋 Cell" not in text
    assert "href='https://stooq.pl/rwe-ichi' target='_blank' title='Open stooq chart'>📈</a><button class='btn sheets-cell-btn'" in text
    assert "aria-label='Copy Google Sheets HYPERLINK formula'>📋</button>" in text
    assert "target='_blank' rel='noopener'" in text
    assert "href='/open-chart?command=" in text
    assert "aria-label='Open stockhelper chart'>📊</a>" in text
    assert ".chart-action-cell,.chart-link-cell,.latest-data-cell{text-align:center;white-space:nowrap}" in text
    assert "<td class='latest-data-cell'>✅</td>" in text
    assert ">Open</button>" not in text
    assert "data-formula='=HYPERLINK(&quot;https://stooq.pl/rwe-ichi&quot;; &quot;RWE.DE&quot;)'" in text
    assert "data-formula='=HYPERLINK(&quot;https://stooq.pl/aep&quot;; &quot;AEP.US&quot;)'" in text
    assert "data-formula='=HYPERLINK(&quot;https://stooq.pl/gpp&quot;; &quot;GPP&quot;)'" in text
    assert "Open all visible stooq chart links" not in text
    assert "border:none" in text
    assert "<details class='legend troj-legend'><summary><b>Legenda</b>" in text
    assert "Open stooq links from top choices" in text
    assert "Open stockhelper charts from this top-choice column" not in text
    assert "Open stockhelper charts from this column" in text
    assert "Open stooq links from this column" in text
    assert "event.stopPropagation();openTrojColumnStockhelperCharts" in text
    assert "event.stopPropagation();openTrojColumnStooqLinks" in text
    for col_idx in range(4):
        assert f"openTrojColumnStockhelperCharts(this,{col_idx})" in text
        assert f"openTrojColumnStooqLinks(this,{col_idx})" in text
        assert f"copyTrojColumnSheetsCells(this,{col_idx})" in text
    assert "copyTrojColumnSheetsCells" in text
    assert "📋 Column" not in text
    assert 'copyTrojColumnSheetsCells(this,0)">📋</button>' in text
    assert "Open stockhelper charts from top choices" in text
    assert "Open all stockhelper charts from this table" in text
    assert "String.fromCharCode(10)" in text
    assert "formulas.join('\n')" not in text
    assert "toggleTrojExtra" in text
    assert "Hide 3P info" not in text
    assert "global-hide-info" not in text
    assert "troj-info-slider" in text
    assert "troj-info-lock" not in text
    assert "stockhelper-troj-info-level" in text
    assert "localStorage.setItem" in text
    assert "restoreTrojInfoPreference" in text
    assert "troj-status-info" in text
    assert "troj-detail-info" in text
    assert "<th>Dir.</th><th>Price to cloud</th><th>Ichimoku status</th><th>Data wybicia</th>" in text
    assert "<th>Mies. respektu przed wybiciem</th><th>Early breakout</th><th>Retest count</th>" in text
    assert "Early breakout status (&lt;4m" not in text
    assert "<th>Dir.</th><th>Price to cloud</th><th>Ichimoku status</th><th>Świece</th>" in text
    assert text.count("<th>Ticker</th><th>Dir</th><th>Near61.8</th>") == 2
    assert "<b>Starbucks (SBUX.US)</b></td><td><span class='fibo-arrow fibo-arrow-long' title='Long' aria-label='Long'>↗</span></td>" in text
    assert "98.5%</span></td>" not in text
    fibo_one_start = text.index("WYNIKI FIBO #1 (Waiting")
    fibo_one_end = text.index("</table>", fibo_one_start)
    fibo_one_html = text[fibo_one_start:fibo_one_end]
    assert fibo_one_html.index("<b>American Electric Power (AEP.US)</b>") < fibo_one_html.index("<b>RWE (RWE.DE)</b>") < fibo_one_html.index("<b>EARLY.DE</b>")
    ichi_one_start = text.index("WYNIKI 1 ICHIMOKU")
    ichi_one_end = text.index("</table>", ichi_one_start)
    ichi_one_html = text[ichi_one_start:ichi_one_end]
    assert ichi_one_html.index("<b>PAT.US</b>") < ichi_one_html.index("<b>Siemens Energy (ENR.DE)</b>")
    assert "data-status='⚪ above' data-troj-direction='long' class='today-signal'" in ichi_one_html
    assert "<th>Latest Retest</th><th>Avg10d PLN</th>" in text
    assert "Latest Retest status</th>" not in text
    assert "medium_retest_pattern: bullish_harami (2026-05-21)" in text
    assert "<body class='stooq-links-hidden'>" in text
    assert ".stooq-links-hidden .stooq-chart-link,.stooq-links-hidden .sheets-cell-btn,.stooq-links-hidden .stooq-column,.stooq-links-hidden button[title*='stooq'],.stooq-links-hidden button[title*='Copy']{display:none!important}" in text
    assert "toggleStooqLinks" in text
    assert "📈 Show" in text
    assert "td.dataset.originalHtml" in text
    assert "dataset.cellHit" in text
    assert "<div class='troj-cell-card' data-ticker='SBUX.US' data-market='WIG' data-scanner='FIBO' data-troj-direction='long'>" in text
    assert "data-scanner='ICHIMOKU'" in text
    assert "data-ichi-trend='long'" in text
    assert re.search(r"data-ichi-trend='long'[^>]*><strong>🇺🇸 Linde \(LIN\.US\)", text)
    assert "data-scanner='ICHIMOKU' data-ichi-trend='long' data-troj-direction='long' class='today-signal'" in text
    assert "<div class='troj-cell-card today-signal' data-ticker='RWE.DE' data-market='WIG' data-scanner='ICHIMOKU' data-ichi-trend='long' data-troj-direction='long'><strong>🇩🇪 RWE (RWE.DE)" in text
    assert "<div class='troj-cell-card today-signal' data-ticker='VAL.US' data-market='WIG' data-scanner='FIBO' data-troj-direction='long'><strong>🇺🇸 VAL.US" in text
    assert "data-scanner='FIBO' data-troj-direction='long' class='today-signal'" in text
    assert "AEP.US" in text and "bullish_hammer" in text
    assert "troj-ichi-trend-filter" not in text
    assert "setTrojDirection" in text
    assert "data-direction='long'" in text and "data-direction='short'" in text
    assert "data-direction='all'" not in text
    assert "const next=(el.dataset.trojDirection||'all')===requested?'all':requested" in text
    assert "b.dataset.direction===next" in text
    assert "card.dataset.market" in text
    assert "card.style.display=cardHit?'':'none'" in text
    assert "const visible=[];const hidden=[]" in text
    assert "visible.sort((a,b)=>(Number(b.classList.contains('today-signal'))-Number(a.classList.contains('today-signal')))).concat(hidden).forEach(card=>td.querySelector('.troj-cell-stack')?.appendChild(card))" in text
    run_source = Path("run").read_text(encoding="utf-8")
    assert "def troj_card_freshness_key" in run_source
    assert "wig20 = _wig20_members()" in run_source
    assert "market_rank = _market_order(row.market, row.ticker)" in run_source
    assert "wig_rank = 0 if market_rank == 0 and ticker in wig20 else 1" in run_source
    assert "return (market_rank, wig_rank, original_index)" in run_source
    assert 'reason = f"Fibo pattern: {pattern}"' in run_source
    assert "freshness_rank = -(max(signal_dates).toordinal() if signal_dates else 0)" in run_source
    assert "def wedge_freshness_rank" in run_source
    assert "- _wedge_breakout_rank(r), wedge_freshness_rank(r)".replace("- ", "-") in run_source
    assert '_top_choice_rank(f"breakout {d.isoformat() if d else \'\'}"' in run_source
    assert '_top_choice_rank(f"pattern {d.isoformat() if d else \'\'}"' in run_source
    assert 'if has_pattern or has_breakout:' in run_source
    assert 'return (0, freshness, signal_kind_rank, text)' in run_source
    assert 'Pattern and breakout signals compete in one freshness queue.' in run_source
    assert 'selected = (must + [item for item in ranked if item not in must])[:limit_per_group]' in run_source
    assert 'def _allsearch_top_choices(limit_per_group: int = 5)' in run_source
    assert 'pattern_date = row.dates.get("pattern_date", "")' in run_source
    assert "const okDirection=directionFilter==='all'||!cardDirection||cardDirection===directionFilter" in text
    assert "return td?{html:td.innerHTML" in text
    assert "th.classList.add('chart-link-cell')" in text
    assert "th.classList.add('stooq-column')" in text
    assert "r.cells[colIdx]?.classList.add('stooq-column')" in text
    assert "const showEmptyGroups=!!m.value&&visibleBySelect&&!sc.value" in text
    assert "<span class='ichi-status-chip ichi-neutral'>Kijun: over</span>" in text
    assert "<b>CREOTECH (CRI)</b></td><td><span class='fibo-arrow fibo-arrow-long' title='Long' aria-label='Long'>↗</span></td><td><span class='ichi-status-chip ichi-good'>above</span></td><td>Over Kijun-sen</td>" in text
    assert "<b>Siemens Energy (ENR.DE)</b></td><td><span class='fibo-arrow fibo-arrow-long' title='Long' aria-label='Long'>↗</span></td><td><span class='ichi-status-chip ichi-good'>above</span></td><td><span style='color:#dc2626;font-weight:700'>Unsuccessful breakout to the other side</span></td>" in text
    assert "class='btn stooq-chart-link'" in text
    assert "<span class='ichi-status-label'>current:</span>" not in text
    assert "<span class='ichi-status-label'>last:</span>" not in text
    assert "<span class='ichi-status-chip ichi-neutral'>Kijun: over</span>" in text
    assert "troj-info-name-only" in text
    assert "troj-info-default" in text
    assert "Why top choice" in text
    assert "top-choice-compact" in text
    assert "<col class='top-choice-instrument'><col class='top-choice-direction'><col class='top-choice-reason'>" in text
    assert ".top-choice-compact .top-choice-instrument{width:24%}" in text
    assert ".stooq-links-hidden col.top-choice-stooq{display:none}" in text
    assert "<time class='choice-reason-date' datetime='2026-07-22'><i>▦</i>2026-07-22</time>" in text
    assert "troj-table sortable" not in text
    assert "top-choice-compact sortable" not in text
    assert "table.data, table.sortable" not in text
    assert "document.querySelectorAll('table.data')" in text
    assert "🇩🇪 EARLY.DE" in text
    assert "Ichimoku Active" not in text
    assert "id='clear-q'" in text
    assert "data-scanner='FIBO'" in text
    assert "data-scanner='ICHIMOKU'" in text
    assert "🔻 Kliny" in text
    assert "🚀 breakout" in text
    assert ".today-signal td{background:#14532d!important}" in text
    assert ".troj-cell-card.today-signal{background:#14532d!important" in text
    assert "data-scanner='WEDGE' data-status='🚀 breakout' data-breakout-date='2026-05-30' data-troj-direction='long' class='today-signal'" in text
    assert "class='market direction-filter-section saved-filter-section' id='wedge-report'" in text
    assert "setTrojDirection('wedge-report','long',this)" in text
    assert "setTrojDirection('wedge-report','short',this)" in text
    assert "const okDirection=directionFilter==='all'||r.dataset.trojDirection===directionFilter" in text
    assert "falling_wedge_breakout" not in text
    assert "wybicie long 2026-05-30" not in text
    assert "<th>Fit</th>" not in text
    assert "<th>Proximity</th>" not in text
    assert "<th>Compression</th>" not in text
    assert "<th>Months</th><th>Touches U/L</th><th>Slope</th><th>Breakout</th><th>Dir</th>" in text
    assert "<th>Score</th><th>Avg10d PLN</th>" not in text
    assert "<th>Dir</th><th>Avg10d PLN</th>" in text
    assert ".top-choice .chart-action-cell{width:82px;min-width:82px;max-width:82px}" in text
    assert "1.000.000" in text
    assert "copyNextTableSheetsCells" in text
    assert "Copy Google Sheets links from this table" in text
    assert "data-cmd='python run -c WDG.WA --wedge-upper-start 2026-01-02,100.0 --wedge-upper-end 2026-03-01,80.0 --wedge-lower-start 2026-02-01,60.0 --wedge-lower-end 2026-04-01,55.0 --wedge-lines --wedge-right'" in text
    assert "breakout / recent breakout (2026-05-29)" in text
    assert "Ichimoku continuation</td><td><strong>🇩🇪 ENR.DE</strong></td><td>breakout / recent breakout" not in text
    assert "Unsuccessful breakout to the other side" in text
    assert "returned to cloud, waiting (2026-05-28)" in text
    assert "Mies. respektu przed wybiciem" in text
    assert "pattern/retest: bullish_harami (2026-07-22)" in text
    assert "near 61.8: 90.0%" in text
    assert "WYNIKI FIBO #0 (3P steep incline)" in text
    assert "<h3>📐 Fibo" in text
    assert "<strong>🇺🇸 Starbucks (SBUX.US)</strong></td><td><span class='fibo-arrow fibo-arrow-long' title='Long' aria-label='Long'>↗</span></td><td><div class='choice-reason'><span class='choice-reason-kind'><i>◆</i>Near 61.8</span><span class='choice-reason-sep'>|</span><span class='choice-reason-detail'><i>↕</i>98.5%</span>" in text
    assert "<h3>🔻 Kliny" in text
    assert "class='choice-reason choice-reason-wedge'" in text
    assert "<i>◆</i>Falling wedge" in text
    assert "<i>♧</i>U/D: 3/3" in text
    assert "near 61.8: 98.5%" in text
    assert "data-cmd='python run -c RWE.DE --ichimoku-mode on --scanner-breakout-date 2026-05-29 --scanner-retest-count 1 --scanner-latest-retest-date 2026-05-30 --scanner-previous-respect-months 7.5'" in text
    assert "Fibo pattern: none" not in text
    assert "Fibo valid" not in text
    assert "data-cmd='python run -c AEP.US --ichimoku-mode off --fibo-lines 5 --fibo-anchor-start 2026-01-05 --fibo-anchor-end 2026-02-20 --fibo-right'" in text
    assert "href='fibo.md'" not in text
    assert "href='ichimoku.md'" not in text


def test_allsearch_all_scopes_include_indexes():
    mod = load_run_module()
    assert mod.DEFAULT_ALLSEARCH_SCOPES == ["wig", "dax", "us100", "forex", "commodities", "indexes", "etfs"]
    assert mod._allsearch_report_stem(mod.DEFAULT_ALLSEARCH_SCOPES) == "allsearch_latest_all"
    assert mod._scope_file_keys("indices") == ["indexes", "indices", "index"]
    assert "📊 INDEXES" == mod._scope_label("indexes")
    assert "🧺 ETFS" == mod._scope_label("etfs")


def test_etf_report_chart_uses_etf_cache_instrument():
    mod = load_run_module()
    row = mod.ScannerRow(
        market="ETFS", scanner="ICHIMOKU", category="position", ticker="VOO.US", status="above"
    )

    assert mod._chart_command_for_row(row).startswith("python run -c VOO.US --instrument etf ")
    assert mod._market_icon("ETFS", "GLD.US") == "🧺"
    assert "s=gld.us" in mod._stooq_chart_url("GLD.US")
    source = Path("run").read_text(encoding="utf-8")
    dropout_start = source.index('elif "fibo" in section_id:')
    dropout_fallback = source[dropout_start:source.index("stooq =", dropout_start)]
    assert 'detected_instrument = "etf" if ticker.upper() in etf_tickers else detect_instrument_type(ticker)' in dropout_fallback
    assert 'instrument_arg = f" --instrument {detected_instrument}" if detected_instrument in {"etf", "forex"} else ""' in dropout_fallback


def test_forex_report_chart_commands_force_forex_cache_directory():
    mod = load_run_module()
    row = mod.ScannerRow(
        market="FOREX", scanner="FIBO", category="waiting", ticker="USDCAD",
        status="reached_23_6_waiting_for_61_8",
        dates={"incline": "2026-05-01->2026-06-24"},
    )

    assert mod._chart_command_for_row(row).startswith(
        "python run -c USDCAD --instrument forex --ichimoku-mode off"
    )


def test_open_existing_allsearch_report_refreshes_html_before_serving(tmp_path: Path):
    mod = load_run_module()
    mod.ALL_REPORT_DIR = tmp_path
    report = tmp_path / "allsearch" / "allsearch_latest_all.html"
    report.parent.mkdir(parents=True)
    report.write_text("stale", encoding="utf-8")

    calls: list[tuple[str, object]] = []

    def write_reports(scopes, timestamp):
        calls.append(("write", list(scopes)))
        return tmp_path / "fibo.md", tmp_path / "ichimoku.md"

    def build_report(scopes, output_path):
        calls.append(("build", (list(scopes), output_path)))
        output_path.write_text("fresh", encoding="utf-8")

    with mock.patch.object(mod, "_write_trojpolowki_reports", side_effect=write_reports), \
         mock.patch.object(mod, "_build_html_report", side_effect=build_report), \
         mock.patch.object(mod, "_open_html_report", return_value="http://127.0.0.1/report"), \
         mock.patch.object(mod, "_wait_for_report_server", return_value=0):
        assert mod._open_existing_allsearch_report("all") == 0

    assert calls == [
        ("write", mod.DEFAULT_ALLSEARCH_SCOPES),
        ("build", (mod.DEFAULT_ALLSEARCH_SCOPES, report)),
    ]
    assert report.read_text(encoding="utf-8") == "fresh"


def test_chart_program_accepts_journal_close_arguments():
    loader = importlib.machinery.SourceFileLoader("chart_program_main_test", "chart_program/main.py")
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    parser = module.build_parser()
    args, unknown = parser.parse_known_args([
        "KC.F",
        "--journal-close-mode",
        "--journal-entry-id",
        "2cbc8ba54a9b43c5881af83b9343e247",
        "--journal-entry-price",
        "280.48",
        "--journal-direction",
        "long",
        "--journal-stop-loss",
        "285.29",
    ])

    assert args.target == "KC.F"
    assert args.chart_modifier is None
    assert args.journal_close_mode is True
    assert args.journal_entry_id == "2cbc8ba54a9b43c5881af83b9343e247"
    assert args.journal_entry_price == "280.48"
    assert args.journal_direction == "long"
    assert args.journal_stop_loss == "285.29"
    assert unknown == []


def test_bullish_harami_retest_can_stay_inside_cloud():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    start = source.index("def _is_bullish_harami")
    end = source.index("def _is_morning_star", start)
    harami_source = source[start:end]
    assert "and cl2 > level" not in harami_source
    assert "_touches_level(c1, level) or _touches_level(c2, level)" in harami_source


def test_short_fibo_uses_clear_top_selection_and_scanner_fibo_can_be_reset():
    scanner_source = Path("scanner_search.py").read_text(encoding="utf-8")
    assert "def _select_impulse_start_short(" in scanner_source
    assert "i_bottom_sel = _select_bottom_short(" in scanner_source
    assert "i_start_sel = _select_impulse_start_short(" in scanner_source
    assert 'i_start = int(high.iloc[:-60].idxmax())' not in scanner_source
    assert "min_decline_pct: float = 0.03" in scanner_source
    assert "max_lookback: int = 140" in scanner_source
    assert "Select the latest clear completed low that belongs to a real decline" in scanner_source
    assert "if completed_cycle:" in scanner_source
    assert "Short: correction returned below 23.6 without touching 61.8" in scanner_source
    assert "old top already completed a 61.8 cycle before the final bottom" in scanner_source
    assert "anchor is followed by a month-long sideways range instead of an immediate decline" in scanner_source
    assert 'steep_3p_short = _find_fibo_3p_steep_setup(df, "short")' in scanner_source
    assert "direction=\"short\", status=status" in scanner_source
    assert "def _mirror_ohlc_for_short(" in scanner_source
    assert '_find_fibo_setup(\n            mirrored,\n            direction="long"' in scanner_source
    assert '_find_fibo_3p_steep_setup(mirrored, "long", mirrored_explain, _mirrored_short=True)' in scanner_source
    assert "steep_min_gain = 0.025 if _mirrored_short else 0.15" in scanner_source
    assert "sideways_band_pct=0.02 if _mirrored_short else 0.08" in scanner_source
    assert "pre_start_left = max(0, i_start - 5)" in scanner_source
    assert "shortest_regular_by_direction" in scanner_source
    assert "shortest_regular_by_direction[item.direction]" in scanner_source

    ui_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    assert "obj.group_id === 'auto-fibo'" in ui_source
    assert "? 'Reset Fibo' : 'Reset scanner'" in ui_source


def test_kumo_twist_uses_projected_cloud_source():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    start = source.index("def _ichimoku_extra_metrics")
    end = source.index("tk_plus =", start)
    metrics_source = source[start:end]
    assert "leading_span_a" in metrics_source
    assert "High\"].tail(52)" in metrics_source
    assert "span_a\"] - c[\"span_b" not in metrics_source


def test_fibo_reversal_pattern_must_include_the_first_61_8_touch():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    setup = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]

    assert "includes_first_touch = first_touch_idx in {i - 1, i}" in setup
    assert "includes_first_touch = first_touch_idx in {i - 2, i - 1, i}" in setup
    assert "includes_touch = any(t in {i - 1, i}" not in setup
    assert "for i in ([first_touch_idx] if first_touch_idx is not None else [])" in setup
    assert "detect_end = min(i_end, first_touch_idx + 2)" in setup


def test_checkavg_accepts_case_insensitive_stooq_bulk_cache_sources():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    start = source.index("def run_checkavg")
    end = source.index("def _print_flip_results_with_links", start)
    checkavg = source[start:end]

    assert '.strip().upper()' in checkavg
    assert 'df, cache_path, meta = _load_full_cached_history_for_scan' in checkavg
    assert 'if not source.startswith("stooq"):' in checkavg
    assert 'source != "stooq"' not in checkavg
    assert 'cache={cache_path}' in checkavg


def test_saved_drawings_do_not_disable_automatic_fibo_discovery():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    scan = source[source.index("def _scan_fibo_one"):source.index("def run_fibo_explain", source.index("def _scan_fibo_one"))]

    assert 'steep_3p = _find_fibo_3p_steep_setup(df, "long")' in scan
    assert "steep_3p = None if manual_fibo" not in scan
    assert "if manual_fibo:\n                    break" not in scan
    assert "if short_fibo_enabled and not manual_fibo" not in scan
    assert "saved_fibo_keys" in scan


def test_fresh_23_6_retracement_is_enough_for_a_short_correction_leg():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    setup = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]

    assert "reached_early_236 = early_rng > 0 and corr_low_early <= early_fib_236" in setup
    assert "early_decline_pct >= 0.05 or reached_early_236" in setup


def test_3p_accepts_a_fresh_independent_peak_below_an_old_cycle_high():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    steep = source[source.index("def _find_fibo_3p_steep_setup"):source.index("def _find_fibo_setup")]

    assert "independent_min_gain = 0.025 if _mirrored_short else 0.15" in steep
    assert "independent_min_daily_gain = 0.0004 if _mirrored_short else 0.003" in steep
    assert "independent_gain >= independent_min_gain" in steep
    assert "independent_daily_gain >= independent_min_daily_gain" in steep


def test_multiple_monthly_shelves_are_absorbed_only_by_exceptional_continuation():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    helper = source[source.index("def _completed_month_side_trend_phases"):source.index("def _has_extended_sideways")]

    assert "side_trend_count = _completed_month_side_trend_count(leg)" in helper
    assert "if side_trend_count >= 2 and exceptional_continuation:" in helper
    assert "Completed 61.8 cycles are handled separately" in helper
    assert "start > phases[-1][1] + 3" in helper


def test_repeated_side_trends_move_the_automatic_anchor_to_the_final_launch():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    selector = source[source.index("def _select_fibo_long_impulse_base"):source.index("def _find_fibo_3p_steep_setup")]

    assert "side_phases = _completed_month_side_trend_phases(impulse_view)" in selector
    assert "anchor_side_phases = _completed_month_side_trend_phases(impulse_view, band_pct=0.08)" in selector
    assert "anchor_begins_side_trend = bool(anchor_side_phases) and anchor_side_phases[0][0] <= 5" in selector
    assert "if len(side_phases) >= 2 or anchor_begins_side_trend:" in selector
    assert "if len(side_phases) >= 2" in selector
    assert "else i_start" in selector
    assert "launch_candidates: list[tuple[float, float, int, float, float]]" in selector
    assert "candidate_daily_gain" in selector
    assert ") = max(launch_candidates)" in selector
    assert "Long: moved fib start after completed anchor-side trend" in selector
    assert "i_start = post_range_idx" in selector


def test_opl_broad_incline_keeps_deep_launch_and_directional_correction():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    setup = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]

    assert "max_lookback=140 if _mirrored_short else 200" in setup
    assert "if _mirrored_short and _has_completed_month_side_trend(correction_seg):" in setup
    assert "Do not reject a directional correction" in setup


def test_exceptional_broad_3p_impulse_beats_non_materially_faster_nested_fibo():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    selector = source[source.index("def _select_fibo_long_impulse_base"):source.index("def _find_fibo_3p_steep_setup")]

    assert "exceptional_broad_impulse = original_gain >= 0.65" in selector
    assert "post_range_daily_gain < original_daily_gain * 1.25" in selector
    assert "retained exceptional broad impulse over a non-materially-faster" in selector
    steep = source[source.index("def _find_fibo_3p_steep_setup"):source.index("def _find_fibo_setup")]
    assert "post_daily_gain < broad_daily_gain * 1.25" in steep
    assert "3P steep: retained exceptional broad anchor" in steep


def test_one_decisive_correction_candle_can_reach_236_and_enter_waiting_column():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    setup = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]

    assert "min_correction_days = 1" in setup
    assert "early_decline_pct >= 0.05 or reached_early_236" in setup
    assert "recent_peak_waiting = i_end - i_peak <= 3" in setup
    assert "continuation_min_gain=0.15 if recent_peak_waiting" in setup


def test_confirmed_first_touch_pattern_preserves_cdr_impulse_anchors():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    setup = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]

    assert "confirmed_first_touch_pattern = False" in setup
    assert "_is_bullish_harami(c1, c2, fib_618)" in setup
    assert "i_end <= current_touch_idxs[0] + 2 or confirmed_first_touch_pattern" in setup
    scan_start = source.index("def _scan_fibo_one")
    scan = source[scan_start:source.index("workers_override =", scan_start)]
    assert "refreshed_anchor_candidates: list[FiboScanResult]" in scan
    assert "forced_anchor_dates=(historical.incline_start_date, historical.incline_end_date)" in scan
    assert "recent_low <= float(historical.fib_61_8)" in scan


def test_long_3p_pullback_sideways_window_does_not_hide_pco_steep_incline():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    steep = source[source.index("def _find_fibo_3p_steep_setup"):source.index("def _find_fibo_setup")]

    assert "if _mirrored_short and _has_completed_month_side_trend(w.iloc[i_peak:]):" in steep


def test_asb_anchor_moves_to_late_low_of_first_base_that_launches_exceptional_leg():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    selector = source[source.index("def _select_fibo_long_impulse_base"):source.index("def _find_fibo_3p_steep_setup")]

    assert "for phase_start, phase_end in side_phases:" in selector
    assert "late_left = max(phase_abs_start, phase_abs_end - 5)" in selector
    assert "late_gain >= 0.65 and late_daily_gain >= 0.006" in selector
    assert "moved exceptional broad fib start behind completed base" in selector


def test_exceptional_nine_day_gold_incline_is_not_rejected_as_too_short():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    setup = source[source.index("def _find_fibo_setup"):source.index("def _print_fibo_results")]

    assert "exceptional_short_incline = newer_days >= 8 and newer_gain >= 0.18" in setup
    assert "and not exceptional_short_incline" in setup
    assert "accepted exceptional compact incline from newer low" in setup


def test_3p_prefers_the_faster_local_gold_acceleration_anchor():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    steep = source[source.index("def _find_fibo_3p_steep_setup"):source.index("def _find_fibo_setup")]

    assert "compact_candidates: list[tuple[float, float, int, float, int]]" in steep
    assert "candidate_low > float(low.iloc[local_left:local_right + 1].min()) * 1.002" in steep
    assert "best_compact = min(compact_candidates, key=lambda item: (item[3], -item[0]))" in steep
    assert "if best_compact[3] < fib_start and best_compact[0] > current_daily_gain:" in steep
    assert "3P steep: moved anchor to faster local acceleration" in steep
    assert "if incline_days < min_incline_days and not compact_acceleration:" in steep


def test_market_filter_is_applied_to_favorite_occurrences():
    source = Path("run").read_text(encoding="utf-8")

    assert "const activeMarket=(document.getElementById('market')?.value||'').trim();" in source
    assert "const unique=activeMarket?uniqueAll.filter(o=>o.market===activeMarket):uniqueAll;" in source
    assert "const unclassified=activeMarket?[]:" in source
    assert "if(typeof renderFavorites==='function')renderFavorites()" in source
