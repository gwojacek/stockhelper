from __future__ import annotations

import importlib.machinery
import importlib.util
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
    scanner = types.ModuleType("scanner_search")
    scanner.COMMODITIES_SEARCH_TICKERS = []
    sys.modules["chart_program.instrument_detector"] = detector
    sys.modules["chart_program.chart_loader"] = loader_mod
    sys.modules["scanner_search"] = scanner

    loader = importlib.machinery.SourceFileLoader("stockhelper_run_test", "run")
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def test_fibo_columns_are_compact_and_without_chart_links(tmp_path: Path):
    mod = load_run_module()
    rows = [
        mod.ScannerRow(
            market="WIG", scanner="FIBO", category="waiting", ticker="TRN", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2026-01-30", "incline": "2026-01-30->2026-03-30"},
            metrics={"near61_raw": "93.2", "ratio_raw": "2.0", "incline_days": "59"}, chart_url="https://stooq.pl/trn",
        ),
        mod.ScannerRow(
            market="US100", scanner="FIBO", category="waiting", ticker="AEP.US", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2026-01-05", "incline": "2026-01-05->2026-02-20"},
            metrics={"near61_raw": "62.5", "ratio_raw": "1.5", "incline_days": "46"}, chart_url="https://stooq.pl/aep",
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
    assert "**🇵🇱 TPE ↗️ (2026-03-23)**" in text
    assert "**🇺🇸 AEP.US ↗️ (2026-01-05) 62.5%**" in text
    assert "**🇵🇱 TRN ↗️ (2026-01-30) 93.2%**" in text
    assert "[📈 chart]" not in text
    assert "[🔗 stooq]" not in text


def test_ichimoku_risk_long_short_and_retest_statuses(tmp_path: Path):
    mod = load_run_module()
    rows = [
        mod.ScannerRow(
            market="WIG", scanner="ICHIMOKU", category="retest_breakout", ticker="CRI", status="⚪ above",
            dates={"flip_date": "2026-01-01"}, metrics={"months": "8.9", "ichimoku_status": "Over Kijun-sen", "risk": "3%", "tk_cross": "none", "dynamic": "aggressive", "cloud": "thick", "chikou": "yes", "twist": "green", "tk_plus": "yes", "tenkan_in_cloud": "no", "raw_status": "breakout_confirmed"}, chart_url="https://stooq.pl/cri",
        ),
        mod.ScannerRow(
            market="DAX", scanner="ICHIMOKU", category="retest_breakout", ticker="HFG.DE", status="🔴 below",
            dates={"flip_date": "2026-02-01"}, metrics={"months": "5.1", "ichimoku_status": "Under Kijun-sen", "risk": "3%", "tk_cross": "bearish TK cross", "dynamic": "high", "cloud": "normal", "chikou": "yes", "twist": "red", "tk_plus": "yes", "tenkan_in_cloud": "yes", "raw_status": "deep_retest_pattern"}, chart_url="https://stooq.pl/hfg",
        ),
    ]
    out = mod._write_trojpolowki_ichimoku(rows, tmp_path, datetime(2026, 5, 30, 10, 11, 12))
    text = out.read_text(encoding="utf-8")
    assert "|  | **🇵🇱 CRI 🔁 retest (8.9m, risk 3%)**<br>🟢 above cloud |  | Kijun: Over Kijun-sen<br>TK: none · dyn: aggressive · cloud: thick" in text
    assert "|  | **🇩🇪 HFG.DE 🔁 retest (5.1m, risk 3%)**<br>🔴 below cloud |  | Kijun: Under Kijun-sen<br>TK: bearish TK cross · dyn: high · cloud: normal" in text
    assert "Legenda: 🟢 above cloud" in text
    assert "[🔗 stooq](https://stooq.pl/hfg)" in text


def test_allsearch_html_has_trojpolowki_links(tmp_path: Path):
    mod = load_run_module()
    mod.TROJPOLLOWKI_DIR = tmp_path / "Trojpolowki"
    out = tmp_path / "chart_program" / "data" / "all_insturments_search" / "allsearch" / "allsearch_latest_all.html"
    out.parent.mkdir(parents=True)
    with mock.patch.object(mod, "_latest_scope_md", return_value=None):
        mod._build_html_report(["wig"], out)
    text = out.read_text(encoding="utf-8")
    assert "Trójpolówki Fibo" in text
    assert "Trójpolówki Ichimoku" in text
    assert "fibo.md" in text and "ichimoku.md" in text
