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


def test_chart_sidebar_has_report_compatible_favorite_star_next_to_name():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert 'class="identity-row"><h2 id="identity"></h2><button id="favorite-star"' in source
    assert "const FAVORITES_KEY = 'stockhelper.favorite-instruments.v1'" in source
    assert "localStorage.setItem(FAVORITES_KEY" in source
    assert "render(); refreshFavoriteStar();" in source
