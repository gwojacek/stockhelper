from __future__ import annotations

import ast
from pathlib import Path


def test_chart_instrument_catalog_contains_cached_market_data():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LightweightChartLevelSelectorUI")
    method = next(node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == "_instrument_catalog")
    method.decorator_list = []
    module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"Path": Path, "__file__": str(Path("chart_program/lightweight_chart_ui.py").resolve())}
    exec(compile(module, "chart_program/lightweight_chart_ui.py", "exec"), namespace)

    catalog = namespace["_instrument_catalog"]()
    by_symbol = {item["symbol"]: item["type"] for item in catalog}

    assert by_symbol["XTB.WA"] == "stock"
    assert by_symbol["EURPLN"] == "forex"
    assert by_symbol["KC.F"] == "commodity"
    assert by_symbol["US100"] == "index"


def test_chart_html_has_searchable_instrument_switcher():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert 'type="search" list="instrument-options"' in source
    assert 'id="instrument-switch-btn"' not in source
    assert "function setupInstrumentSwitcher()" in source
    assert "input.addEventListener('input', openSelected)" in source
    assert "url.searchParams.set('command', `python run -c ${{selected.symbol}}`)" in source


def test_chart_has_save_and_save_close_actions():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert 'id="save-btn"' in source
    assert '<span>Save &amp; Close</span>' in source
    assert "$('save-btn').onclick = () => saveChart(false)" in source
    assert "$('finish-btn').onclick = () => saveChart(true)" in source
    assert '@app.route("/save", methods=["POST"])' in source


def test_scanner_pattern_and_breakout_candles_are_highlighted():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "function drawScannerHighlights(ctx)" in source
    assert "__scanner_pattern_date__" in source
    assert "__scanner_latest_retest_date__" in source
    assert "__scanner_breakout_date__" in source
    assert "scannerCandleBand(event.date, event.candles)" in source
    assert "scanner-highlight-tooltip" in source
    assert "addScannerHighlightLegend()" in source
    assert "scannerPatternSpan" in source
    assert "scanner-highlight-legend" in source
    assert "hiddenLegendKeys.has(event.key)" in source
    assert "idx - (span - 1)" in source
    assert "shooting[ _-]?star|hammer|doji|pin[ _-]?bar" in source
    assert "#a855f7', 'below', scannerPatternSpan(fibPattern)" in source
    assert "function ichimokuHighlightBreakoutDate" in source
    assert "ichimokuScannerBreakoutContext(scanner).displayDate || scanner" in source
    assert "side === 'inside_cloud'" in source
    assert "function ichimokuCloudSideForDate" in source
    assert "String(retestDate) > String(breakoutDate)" in source
