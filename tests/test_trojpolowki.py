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
    loader_mod.local_csv_path_for_symbol = lambda *args, **kwargs: Path("data/fake.csv")
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
    assert "**🇵🇱 TPE ↗️ (2026-03-23)**" in text
    assert "**🇵🇱 OPL ↗️ (2026-01-15)**" in text
    assert "**🇵🇱 CPS ↗️ (2026-03-23) 0.0%**" in text
    assert "**🇩🇪 EARLY.DE ↗️ (2026-04-15) 10.0%**" in text
    assert text.count("**🇵🇱 GPW ↗️ (2026-03-27) 14.5%**") == 1
    assert text.index("**🇵🇱 OPL ↗️") < text.index("**🇩🇪 EARLY.DE ↗️")
    assert "**🇺🇸 AEP.US ↗️ (2026-01-05) 62.5%**" in text
    assert text.count("**🇵🇱 TRN ↗️") == 1
    assert "**🇵🇱 TRN ↗️ (2026-01-30) 92.7%**" in text
    assert "**🇵🇱 TRN ↗️ (2025-12-29) 91.6%**" not in text
    assert "CROSSED" not in text
    assert text.count("**🛢️ BRACOMP") == 2
    assert "**🛢️ BRACOMP ↘️ (2026-02-25) 45.3%**" in text
    assert "**🛢️ BRACOMP ↗️ (2025-10-10) 33.4%**" in text
    assert "**🛢️ BRACOMP ↘️ (2026-04-14) 22.5%**" not in text
    data_rows = [line for line in text.splitlines() if line.startswith("| ") and not line.startswith("|---")][1:]
    split_rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in data_rows]
    assert any("**🇵🇱 CPS" in cells[1] for cells in split_rows)
    assert not any("**🇵🇱 CPS" in cells[0] for cells in split_rows)
    assert "[📈 chart]" not in text
    assert "[🔗 stooq](https://stooq.pl/trn)" in text


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
    ]
    out = mod._write_trojpolowki_ichimoku(rows, tmp_path, datetime(2026, 5, 30, 10, 11, 12))
    text = out.read_text(encoding="utf-8")
    assert "| 🟢 Strong / continuation | 👀 Kijun / watch | ☁️ Cloud / retest / breakout | 🔁 Retest <4m |" in text
    assert "**🇵🇱 CRI ↗️ long (8.9m)**<br>🏷️ above cloud<br>Kijun: over" in text
    assert "**🇩🇪 HFG.DE (5.1m)**<br>🏷️ below cloud · Kijun: under · Short trend<br>🕘 last retest pattern (2026-02-01)<br>🟢 risk: 3% · ⬇️ Chikou under · 🔴 kumo" in text
    assert "Risk/grading details are shown only in the ☁️ Cloud / retest / breakout and 🔁 Retest <4m columns" in text
    assert "TK values use the latest actionable Tenkan/Kijun direction" in text
    assert "**🇺🇸 MSFT.US (2.0m)**" in text
    assert "🏷️ touched cloud · Long trend<br>🕘 retest hammer (2026-05-29)" in text
    assert "**🇩🇪 RWE.DE (4.0m)**" in text
    assert "🟡 risk: 2% · ⬆️ Chikou over · 🟢 kumo" in text
    assert "➕ 🔴 TK cross bearish · Tenkan_in_☁: yes · dyn high · cloud normal" in text
    assert "**🇩🇪 BEAR.DE (0.0m)**" in text
    assert "🟢 risk: 3% · ⬇️ Chikou under · 🔴 kumo" in text
    assert "➕ 🔴 TK cross bearish · Tenkan_in_☁: yes · dyn mild · cloud normal" in text
    assert "➕ 🟢 TK cross bullish · Tenkan_in_☁: yes · dyn mild" in text
    assert "➖ cloud shallow" in text
    lines = text.splitlines()
    data_rows = [line for line in lines if line.startswith("| ") and not line.startswith("|---")][1:]
    assert "**🇩🇪 HFG.DE" in data_rows[0]
    assert "**🇩🇪 BEAR.DE" in data_rows[0]
    assert any("**🇩🇪 RWE.DE" in row for row in data_rows)
    assert "**🇺🇸 MSFT.US" in text
    assert "**🇵🇱 CRI" in data_rows[0]
    assert "**🇵🇱 ABC" in text
    assert any(row.startswith("| **🇵🇱 ABC") for row in data_rows)
    assert "**🇺🇸 AMGN.US ↗️ long (2.5m)**<br>🏷️ above cloud<br>Kijun: over" in text
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
        "| SCW | below | returned_to_cloud_waiting_for_pattern | 2026-05-28 | 0.1 | 6.0 | 0 | 6728668 | - | - | Inside the cloud | - | none | mild | thick | no | neutral | no | yes | https://stooq.pl/scw | python run -c SCW | yes | 2026-05-29 | 2026-05-29 |\n"
        "\n# WYNIKI 1 ICHIMOKU\n\n"
        "| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Retest count | Latest Retest date | Latest Retest pattern | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| ENR.DE | ⚪ above | 175 | 8.2 | 2025-11-24 | 160.0000 | 1761117868 | Unsuccessful breakout to the other side | 2 | 2026-05-29 | hammer | https://stooq.pl/enr | python run -c ENR.DE | yes | 2026-06-01 | 2026-06-01 |\n",
        encoding="utf-8",
    )
    fibo_md = tmp_path / "fibo_search_wig_latest.md"
    fibo_md.write_text(
        "# WYNIKI FIBO #0 (3P steep incline)\n\n"
        "| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| SBUX.US | long | 🚀 3p_steep_incline | 2026-03-27->2026-05-30 | 44/1 (44.00:1) | 98.5% | 1000 | https://stooq.pl/sbux | python run -c SBUX.US | yes | 2026-05-30 | 2026-05-30 |\n"
        "\n# WYNIKI FIBO #1\n\n"
        "| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| AEP.US | long | reached_23_6_waiting_for_61_8 | none | 2026-01-05->2026-02-20 | 46/30 (1.53:1) | - | 1000 | 90.0% | https://stooq.pl/aep | python run -c AEP.US | yes | 2026-05-30 | 2026-05-30 |\n"
        "| RWE.DE | long | reached_23_6_waiting_for_61_8 | none | 2026-01-05->2026-02-20 | 46/30 (1.53:1) | - | 1000 | 80.0% | https://stooq.pl/rwe-fibo | python run -c RWE.DE | yes | 2026-05-30 | 2026-05-30 |\n"
        "| EARLY.DE | long | reached_23_6_waiting_for_61_8 | none | 2026-04-15->2026-05-20 | 35/20 (1.75:1) | - | 1000 | 10.0% | https://stooq.pl/early | python run -c EARLY.DE | yes | 2026-05-30 | 2026-05-30 |\n"
        "\n# WYNIKI FIBO #2\n\n"
        "| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| TPE | long | hammer | 2026-01-05->2026-02-20 | 46/30 (1.53:1) | 2026-05-16 | 1000 | https://stooq.pl/tpe | python run -c TPE | yes | 2026-05-30 | 2026-05-30 |\n"
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
    assert "copySheetsCell" in text
    assert "📋 Cell" not in text
    assert "href='https://stooq.pl/rwe-ichi' target='_blank' title='Open stooq chart'>📈</a><button class='btn sheets-cell-btn'" in text
    assert "aria-label='Copy Google Sheets HYPERLINK formula'>📋</button>" in text
    assert "aria-label='Open stockhelper chart'>📊</button>" in text
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
    assert "troj-status-info" in text
    assert "troj-detail-info" in text
    assert "<th>Ichimoku status</th><th>Data wybicia</th>" in text
    assert "<th>Latest Retest</th><th>Avg10d PLN</th>" in text
    assert "Latest Retest status</th>" not in text
    assert "medium_retest_pattern: bullish_harami (2026-05-21)" in text
    assert "<body class='stooq-links-hidden'>" in text
    assert ".stooq-links-hidden .stooq-chart-link,.stooq-links-hidden .sheets-cell-btn,.stooq-links-hidden .stooq-column,.stooq-links-hidden button[title*='stooq'],.stooq-links-hidden button[title*='Copy']{display:none!important}" in text
    assert "toggleStooqLinks" in text
    assert "📈 Show" in text
    assert "td.dataset.originalHtml" in text
    assert "dataset.cellHit" in text
    assert "<div class='troj-cell-card' data-market='WIG' data-scanner='FIBO'>" in text
    assert "<div class='troj-cell-card' data-market='WIG' data-scanner='ICHIMOKU'>" in text
    assert "card.dataset.market" in text
    assert "card.style.display=cardHit?'':'none'" in text
    assert "const visible=[];const hidden=[]" in text
    assert "visible.concat(hidden).forEach(card=>td.querySelector('.troj-cell-stack')?.appendChild(card))" in text
    assert "return td?{html:td.innerHTML" in text
    assert "th.classList.add('chart-link-cell')" in text
    assert "th.classList.add('stooq-column')" in text
    assert "r.cells[colIdx]?.classList.add('stooq-column')" in text
    assert "const showEmptyGroups=!!m.value&&visibleBySelect&&!sc.value" in text
    assert "<span class='ichi-status-chip ichi-neutral'>Kijun: over</span> <br><span class='ichi-status-chip ichi-good'>Long trend</span>" in text
    assert "<b>ENR.DE</b></td><td><span class='ichi-status-chip ichi-good'>above cloud</span></td>" in text
    assert "class='btn stooq-chart-link'" in text
    assert "<span class='ichi-status-label'>current:</span>" not in text
    assert "<span class='ichi-status-label'>last:</span>" not in text
    assert "<span class='ichi-status-chip ichi-neutral'>Kijun: over</span>" in text
    assert "troj-info-name-only" in text
    assert "troj-info-default" in text
    assert "Why top choice" in text
    assert "top-choice-compact" in text
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
    assert "data-scanner='WEDGE' data-status='🚀 breakout' class='today-signal'" in text
    assert "data-scanner='FIBO' data-status='valid_reversal' class='today-signal'" in text
    assert "data-scanner='ICHIMOKU' data-status='breakout_confirmed' class='today-signal'" in text
    assert "<div class='troj-cell-card today-signal' data-market='WIG' data-scanner='FIBO'>" in text
    assert "<div class='troj-cell-card today-signal' data-market='WIG' data-scanner='ICHIMOKU'>" in text
    assert "falling_wedge_breakout" not in text
    assert "wybicie long 2026-05-30" not in text
    assert "<th>Fit</th>" not in text
    assert "<th>Proximity</th>" not in text
    assert "<th>Compression</th>" not in text
    assert "<th>Months</th><th>Touches U/L</th><th>Slope</th><th>Breakout</th><th>Dir</th>" in text
    assert "<th>Score</th><th>Avg10d PLN</th>" not in text
    assert "<th>Dir</th><th>Avg10d PLN</th>" in text
    assert ".top-choice .chart-action-cell{width:68px;min-width:68px;max-width:68px}" in text
    assert "1.000.000" in text
    assert "copyNextTableSheetsCells" in text
    assert "Copy Google Sheets links from this table" in text
    assert "data-cmd='python run -c WDG.WA --wedge-upper-start 2026-01-02,100.0 --wedge-upper-end 2026-03-01,80.0 --wedge-lower-start 2026-02-01,60.0 --wedge-lower-end 2026-04-01,55.0 --wedge-lines --wedge-right'" in text
    assert "breakout / recent breakout (2026-05-29)" in text
    assert "Ichimoku continuation</td><td><strong>🇩🇪 ENR.DE</strong></td><td>breakout / recent breakout" not in text
    assert "Unsuccessful breakout to the other side" in text
    assert "returned to cloud, waiting (2026-05-28)" in text
    assert "Mies. respektu przed wybiciem" in text
    assert "pattern/retest: bullish_harami" not in text
    assert "near 61.8: 90.0%" in text
    assert "WYNIKI FIBO #0 (3P steep incline)" in text
    assert "<h3>📐 Fibo" in text
    assert "<strong>🇺🇸 SBUX.US</strong></td><td>near 61.8: 98.5%" in text
    assert "<h3>🔻 Kliny" in text
    assert "near 61.8: 98.5%" in text
    assert "data-cmd='python run -c RWE.DE --ichimoku-mode on --scanner-breakout-date 2026-05-29 --scanner-retest-count 1 --scanner-latest-retest-date 2026-05-30 --scanner-previous-respect-months 7.5'" in text
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


def test_kumo_twist_uses_projected_cloud_source():
    source = Path("scanner_search.py").read_text(encoding="utf-8")
    start = source.index("def _ichimoku_extra_metrics")
    end = source.index("tk_plus =", start)
    metrics_source = source[start:end]
    assert "leading_span_a" in metrics_source
    assert "High\"].tail(52)" in metrics_source
    assert "span_a\"] - c[\"span_b" not in metrics_source
