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


def test_chart_uses_cursor_save_control_instead_of_sidebar_save_actions():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert 'id="save-btn"' not in source
    assert 'id="finish-btn"' not in source
    assert '<span>Save &amp; Close</span>' not in source
    assert "function saveChart(" not in source
    assert 'id="saved-fibo-status"' in source
    assert '@app.route("/save", methods=["POST"])' in source


def test_chart_controls_use_grouped_toolbar_with_contextual_scanner_reset():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    for label in ("Levels", "Analysis", "Tools", "Scanner", "Reset"):
        assert f'class="toolbar-label">{label}</span>' in source
    assert 'class="level-grid" id="level-buttons"' in source
    assert 'id="analysis-buttons"' in source
    assert "? 'Fibo' : 'Wedges'" in source
    assert "scannerToolbarGroup.style.display = hasWedgeObjects ? 'flex' : 'none'" in source
    assert 'aria-label="Find a new upper wedge line">↑</button>' in source
    assert 'aria-label="Find a new lower wedge line">↓</button>' in source
    assert source.index('id="reset-all"') < source.index('id="download-chart-png"')


def test_chart_ohlc_values_are_centered_and_individually_spaced():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "#cursor-box {{ min-height:52px; display:flex; align-items:center; padding:0 24px;" in source
    assert "#cursor-stats {{ flex:1 1 auto; display:flex; align-items:center; justify-content:center;" in source
    assert "gap:clamp(16px,2.2vw,34px)" in source
    assert "font-variant-numeric:tabular-nums" in source
    assert 'class="cursor-stat cursor-day"' in source
    assert 'class="cursor-label">CURSOR:</span>' in source


def test_line_color_menu_opens_upward_with_yellow_default():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert ".line-color-menu {{ display:none; position:absolute; z-index:100; top:auto; bottom:calc(100% + 6px); right:0;" in source
    assert ".line-color-picker #line-color-toggle" in source
    assert 'id="line-color-indicator"' in source
    assert "#line-color-indicator {{ width:15px; height:15px;" in source
    assert "background:#facc15" in source
    assert "$('line-color-indicator').style.background=b.dataset.color" in source
    assert "$('line-color-toggle').style.background=b.dataset.color" not in source
    assert "let lineColor = P.lineColors.gold" in source


def test_chart_shows_saved_fibo_and_max_capital_context():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    assert 'id="chart-context-info"' in source
    assert 'id="max-capital-info"' in source
    assert "💾 Chart saved:" in source
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
    assert '<button id="saved-fibo-status" type="button" title="Saves chart configuration until it becomes invalid"' in source
    assert '💾 Chart saved' in source
    assert '💾 Save chart' in source
    assert 'Chart configuration saved until it becomes invalid; click to remove' in source
    assert 'class="saved-remove"' in source
    toolbar = source[source.index('<div class="toolbar">'):source.index('<div id="cursor-box">')]
    cursor_box = source[source.index('<div id="cursor-box">'):source.index('<div class="legend-row">')]
    assert 'id="saved-fibo-status"' not in toolbar
    assert cursor_box.index('id="cursor-stats"') < cursor_box.index('id="saved-fibo-status"')
    assert "$('cursor-stats').innerHTML" in source
    assert "$('cursor-box').innerHTML" not in source
    assert '#saved-fibo-status' in source and 'color:inherit' in source
    assert "btn.classList.toggle('active',saved)" in source
    assert "if (!savedFiboByUser && !savedWedgeByUser)" in source
    assert "savedWedgeByUser" in source
    assert "type:'stockhelper-saved-setup'" in source
    assert "__saved_wedge_by_user__:savedWedgeByUser" in source
    assert "!levels.__saved_fibo_invalid__" in source
    assert "delete levels.__saved_fibo_invalid__" in source
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


def test_quick_chart_group_has_market_and_direction_filters():
    ui = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    server = Path("utilities/report_server.py").read_text(encoding="utf-8")
    report = Path("run").read_text(encoding="utf-8")

    assert 'id="chart-group-filters"' in ui
    assert "marketIcons = {{WIG:'🇵🇱',DAX:'🇩🇪',US100:'🇺🇸',FOREX:'💱',COMMODITIES:'🛢️',INDEXES:'📊',ETFS:'🧺'}}" in ui
    assert "addFilter('↗  BULLISH', 'direction', 'long'" in ui
    assert "addFilter('↘  BEARISH', 'direction', 'short'" in ui
    assert '"market": market' in server
    assert '"direction": direction if direction in {"long", "short"} else ""' in server
    assert "b.closest('[data-market]')?.dataset.market" in report
    assert "b.closest('[data-troj-direction]')?.dataset.trojDirection" in report


def test_quick_chart_filters_persist_and_are_visually_separated():
    ui = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    server = Path("utilities/report_server.py").read_text(encoding="utf-8")
    report = Path("run").read_text(encoding="utf-8")

    assert "chart-group-filter-label" in ui
    assert "chart-group-market-filters" in ui
    assert "chart-group-direction-filters" in ui
    assert ">Filter charts</span>" in ui
    assert "url.searchParams.set('groupMarket', chartGroupMarketFilter)" in ui
    assert "url.searchParams.set('groupDirection', chartGroupDirectionFilter)" in ui
    assert "chartGroup?.marketFilter" in ui
    assert '"marketFilter": group_market_filter' in server
    assert 'qs.get("groupMarket"' in server
    assert 'group_market_filter = _clean_group_text(payload.get("marketFilter")' in server
    assert 'first_query["groupMarket"] = group_market_filter' in server
    assert "def _troj_market_from_card_text" in report
    assert '("🇵🇱", "WIG")' in report
    assert "marketFilter:(typeof m!=='undefined'&&m?m.value:'')" in report
    assert "(!card||card.style.display!=='none')" in report
