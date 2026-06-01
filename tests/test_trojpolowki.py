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
            market="DAX", scanner="FIBO", category="waiting", ticker="EARLY.DE", status="reached_23_6_waiting_for_61_8",
            direction="long", dates={"start": "2026-04-15", "incline": "2026-04-15->2026-05-20"},
            metrics={"near61_raw": "10.0", "ratio_raw": "9.9", "incline_days": "35"}, chart_url="https://stooq.pl/early",
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
    assert "**🇩🇪 EARLY.DE ↗️ (2026-04-15)**" in text
    assert text.index("**🇵🇱 TPE ↗️") < text.index("**🇩🇪 EARLY.DE ↗️")
    assert "**🇺🇸 AEP.US ↗️ (2026-01-05) 62.5%**" in text
    assert "**🇵🇱 TRN ↗️ (2026-01-30) 93.2%**" in text
    assert "[📈 chart]" not in text
    assert "[🔗 stooq](https://stooq.pl/trn)" in text


def test_ichimoku_risk_long_short_and_retest_statuses(tmp_path: Path):
    mod = load_run_module()
    rows = [
        mod.ScannerRow(
            market="WIG", scanner="ICHIMOKU", category="retest_breakout", ticker="CRI", status="⚪ above",
            dates={"flip_date": "2026-01-01"}, metrics={"months": "8.9", "ichimoku_status": "Over Kijun-sen", "risk": "3%", "tk_cross": "none", "dynamic": "aggressive", "cloud": "thick", "chikou": "yes", "twist": "green", "tk_plus": "yes", "tenkan_in_cloud": "no", "raw_status": "breakout_confirmed"}, chart_url="https://stooq.pl/cri",
        ),
        mod.ScannerRow(
            market="WIG", scanner="ICHIMOKU", category="position", ticker="ABC", status="🟢 above",
            dates={"start_date": "2025-10-01"}, metrics={"months": "7.1", "ichimoku_status": "Over Kijun-sen", "risk": "-", "tk_cross": "-", "dynamic": "-", "cloud": "-", "chikou": "-", "twist": "-", "tk_plus": "-", "tenkan_in_cloud": "-", "raw_status": "above"}, chart_url="https://stooq.pl/abc",
        ),
        mod.ScannerRow(
            market="US100", scanner="ICHIMOKU", category="position", ticker="AMGN.US", status="⚪ watch",
            dates={"start_date": "2026-04-01"}, metrics={"months": "2.5", "ichimoku_status": "Over Kijun-sen", "risk": "-", "tk_cross": "none", "dynamic": "-", "cloud": "-", "chikou": "-", "twist": "-", "tk_plus": "-", "tenkan_in_cloud": "-", "raw_status": "watch"}, chart_url="https://stooq.pl/amgn",
        ),
        mod.ScannerRow(
            market="DAX", scanner="ICHIMOKU", category="retest_breakout", ticker="HFG.DE", status="🔴 below",
            dates={"flip_date": "2026-02-01"}, metrics={"months": "5.1", "ichimoku_status": "Under Kijun-sen", "risk": "3%", "tk_cross": "bearish TK cross", "dynamic": "high", "cloud": "normal", "chikou": "yes", "twist": "red", "tk_plus": "yes", "tenkan_in_cloud": "yes", "raw_status": "deep_retest_pattern"}, chart_url="https://stooq.pl/hfg",
        ),
        mod.ScannerRow(
            market="US100", scanner="ICHIMOKU", category="retest_breakout", ticker="MSFT.US", status="⚪ above",
            dates={"flip_date": "2026-04-01"}, metrics={"months": "2.0", "ichimoku_status": "Touched the cloud", "risk": "2%", "tk_cross": "bullish TK cross", "dynamic": "mild", "cloud": "shallow", "chikou": "yes", "twist": "green", "tk_plus": "yes", "tenkan_in_cloud": "yes", "raw_status": "retest_breakout"}, chart_url="https://stooq.pl/msft",
        ),
        mod.ScannerRow(
            market="DAX", scanner="ICHIMOKU", category="retest_breakout", ticker="RWE.DE", status="⚪ above",
            dates={"flip_date": "2026-05-29"}, metrics={"months": "4.0", "ichimoku_status": "Touched Kijun-sen", "risk": "2%", "tk_cross": "bullish TK cross", "dynamic": "mild", "cloud": "normal", "chikou": "yes", "twist": "green", "tk_plus": "yes", "tenkan_in_cloud": "yes", "raw_status": "breakout_confirmed", "previous_side": "below"}, chart_url="https://stooq.pl/rwe",
        ),
    ]
    out = mod._write_trojpolowki_ichimoku(rows, tmp_path, datetime(2026, 5, 30, 10, 11, 12))
    text = out.read_text(encoding="utf-8")
    assert "| 🟢 Strong / continuation | 👀 Kijun / watch | ☁️ Cloud / retest / breakout | 🔁 Retest <4m |" in text
    assert "**🇵🇱 CRI ↗️ long (8.9m)**<br>Kijun: over<br>🏷️ above cloud" in text
    assert "**🇩🇪 HFG.DE 🔁 retest (5.1m)**<br>🟢 risk: 3% · ✅ Chikou under · 🔴 kumo" in text
    assert "Risk/grading details are shown only in the ☁️ Cloud / retest / breakout and 🔁 Retest <4m columns" in text
    assert "TK cross values are shown as bullish / bearish / no cross yet" in text
    assert "**🇺🇸 MSFT.US 🔁 retest (2.0m)**" in text
    assert "**🇩🇪 RWE.DE 🔁 retest (4.0m)**" in text
    assert "🟡 risk: 2% · ✅ Chikou over · 🟢 kumo" in text
    assert "➕ 🟢 TK cross bullish · Tenkan_in_☁: yes · dyn mild" in text
    assert "➖ cloud shallow" in text
    lines = text.splitlines()
    data_rows = [line for line in lines if line.startswith("| ") and not line.startswith("|---")][1:]
    assert "**🇩🇪 HFG.DE" in data_rows[0]
    assert "**🇩🇪 RWE.DE" in data_rows[0]
    assert "**🇺🇸 MSFT.US" in text
    assert "**🇵🇱 CRI" in data_rows[0]
    assert "**🇵🇱 ABC" in text
    assert "**🇺🇸 AMGN.US ↗️ long (2.5m)**<br>Kijun: over" not in text
    assert "[📈 chart]" not in text
    assert "[🔗 stooq](https://stooq.pl/hfg)" in text


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
        "| SCW | below | returned_to_cloud_waiting_for_pattern | 2026-05-28 | 0.1 | 6.0 | 0 | 6728668 | - | - | Inside the cloud | - | none | mild | thick | no | neutral | no | yes | https://stooq.pl/scw | python run -c SCW | yes | 2026-05-29 | 2026-05-29 |\n",
        encoding="utf-8",
    )
    fibo_md = tmp_path / "fibo_search_wig_latest.md"
    fibo_md.write_text(
        "# WYNIKI FIBO #1\n\n"
        "| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| AEP.US | long | reached_23_6_waiting_for_61_8 | none | 2026-01-05->2026-02-20 | 46/30 (1.53:1) | - | 1000 | 90.0% | https://stooq.pl/aep | python run -c AEP.US | yes | 2026-05-30 | 2026-05-30 |\n"
        "| RWE.DE | long | reached_23_6_waiting_for_61_8 | none | 2026-01-05->2026-02-20 | 46/30 (1.53:1) | - | 1000 | 80.0% | https://stooq.pl/rwe-fibo | python run -c RWE.DE | yes | 2026-05-30 | 2026-05-30 |\n"
        "| EARLY.DE | long | reached_23_6_waiting_for_61_8 | none | 2026-04-15->2026-05-20 | 35/20 (1.75:1) | - | 1000 | 10.0% | https://stooq.pl/early | python run -c EARLY.DE | yes | 2026-05-30 | 2026-05-30 |\n",
        encoding="utf-8",
    )
    def latest_md(kind: str, scope: str):
        return fibo_md if kind == "fibo_search" else ichi_md
    with mock.patch.object(mod, "_latest_scope_md", side_effect=latest_md):
        mod._build_html_report(["wig"], out)
    text = out.read_text(encoding="utf-8")
    assert "ALLSEARCH REPORT" in text
    assert "🌈🐱 Scanner workspace" in text
    assert "3P FIBO" in text
    assert "3P ICHIMOKU" in text
    assert "📄 PDF" in text
    assert "📄 Download PDF" not in text
    assert 'onclick="downloadPdfReport()"' in text
    assert "@media print" in text
    assert "zoom:.78" in text
    assert "id='tab-allsearch' class='tab-panel active'" in text
    assert "id='tab-troj-fibo' class='tab-panel'" in text
    assert "id='tab-troj-ichimoku' class='tab-panel'" in text
    assert "id='trojpolowki-fibo'" in text
    assert "id='trojpolowki-ichimoku'" in text
    assert "troj-name-actions" in text
    assert "Open all visible stooq chart links" not in text
    assert "border:none" in text
    assert "<details class='legend troj-legend'><summary><b>Legenda</b>" in text
    assert "Open stooq links from top choices" in text
    assert "Open stooq links from this column" in text
    assert "event.stopPropagation();openTrojColumnStooqLinks" in text
    assert "toggleTrojExtra" in text
    assert "Hide additional info" in text
    assert "troj-extra-info" in text
    assert "Why top choice" in text
    assert "top-choice-compact" in text
    assert "troj-table sortable" in text
    assert "table.data, table.sortable" in text
    assert "🇩🇪 EARLY.DE" in text
    assert "Ichimoku Active" not in text
    assert "id='clear-q'" in text
    assert "data-scanner='FIBO'" in text
    assert "data-scanner='ICHIMOKU'" in text
    assert "breakout / recent breakout (2026-05-29)" in text
    assert "returned to cloud, waiting (2026-05-28)" in text
    assert "Mies. respektu przed wybiciem" in text
    assert "pattern/retest: bullish_harami" not in text
    assert "near 61.8: 90.0%" in text
    assert "data-cmd='python run -c RWE.DE --ichimoku-mode on'" in text
    assert "Fibo pattern: none" not in text
    assert "Fibo valid" not in text
    assert "data-cmd='python run -c AEP.US --ichimoku-mode off --fibo-lines 5 --fibo-anchor-start 2026-01-05 --fibo-anchor-end 2026-02-20 --fibo-right'" in text
    assert "href='fibo.md'" not in text
    assert "href='ichimoku.md'" not in text


def test_allsearch_all_scopes_include_indexes():
    mod = load_run_module()
    assert mod.DEFAULT_ALLSEARCH_SCOPES == ["wig", "dax", "us100", "forex", "commodities", "indexes"]
    assert mod._allsearch_report_stem(mod.DEFAULT_ALLSEARCH_SCOPES) == "allsearch_latest_all"
    assert mod._scope_file_keys("indices") == ["indexes", "indices", "index"]
    assert "📊 INDEXES" == mod._scope_label("indexes")


def test_bullish_harami_retest_can_stay_inside_cloud():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    start = source.index("def _is_bullish_harami")
    end = source.index("def _is_morning_star", start)
    harami_source = source[start:end]
    assert "and cl2 > level" not in harami_source
    assert "_touches_level(c1, level) or _touches_level(c2, level)" in harami_source


def test_kumo_twist_uses_projected_cloud_source():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    start = source.index("def _ichimoku_extra_metrics")
    end = source.index("tk_plus =", start)
    metrics_source = source[start:end]
    assert "leading_span_a" in metrics_source
    assert "High\"].tail(52)" in metrics_source
    assert "span_a\"] - c[\"span_b" not in metrics_source
