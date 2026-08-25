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


def test_chart_shows_saved_fibo_and_max_capital_context():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    assert 'id="chart-context-info"' in source
    assert 'id="max-capital-info"' in source
    assert "This Fibo formation is saved by you" in source
    assert "Max capital engagement:" in source
    assert "1% of 10-day average turnover" in source
    assert "['Fibo', '💾 SAVED BY USER']" in source
    assert "['Max capital (1% Avg10d)'" in source
    assert '"volume": float(row["Volume"])' in source
    assert "maxCapitalInSelectedCurrency" in source
    assert "FX_TO_PLN[native]" in source
    assert "money(converted,selected)" in source


def test_chart_sidebar_has_report_compatible_favorite_star_next_to_name():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert 'class="identity-row"><h2 id="identity"></h2><button id="favorite-star"' in source
    assert "const FAVORITES_KEY = 'stockhelper.favorite-instruments.v1'" in source
    assert "localStorage.setItem(FAVORITES_KEY" in source
    assert "render(); refreshFavoriteStar(); syncFavoritesFromReport();" in source
    assert "new URL('/favorites', P.reportServer)" in source
    assert "P.favoriteTicker || P.sourceTicker || P.symbol" in source
    assert "setInterval(syncFavoritesFromReport, 1500)" in source
    assert '"favoriteTicker": os.environ.get("STOCKHELPER_FAVORITE_TICKER", "")' in source



def test_position_calculation_displays_one_percent_avg10d_with_market_currency():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "max_capital = avg_turnover_10d * 0.01" in source
    assert '"max_capital_currency": _instrument_currency()' in source
    assert "Max capital to engage (1% Avg10d)" in source
    assert "money(b.max_capital, b.max_capital_currency || currency)" in source
