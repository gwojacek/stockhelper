from pathlib import Path


UI_SOURCE = Path(__file__).resolve().parents[1] / "chart_program" / "lightweight_chart_ui.py"


def test_debug_tools_offer_technique_specific_choosers_and_shared_report_drawer():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "choose-sidetrends" in source
    assert "choose-fibo-anchors" in source
    assert "choose-wedge-anchors" in source
    assert "$('debug-tools').onclick = renderDebugChooser" in source
    assert "debugToolsBtn.style.display = ['Fibo', 'Kliny'].includes(tech)" in source
    assert "Sidetrend correction report" in source
    assert "Wedge'}} correction report" in source
    assert "Copy result" in source


def test_sidetrend_debug_editor_draws_and_allows_date_or_validity_corrections():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "function detectedMonthlySidetrends()" in source
    assert "function renderSidetrendEditor()" in source
    assert "function drawDebugSidetrends(ctx)" in source
    assert 'type="checkbox"' in source
    assert 'type="date"' in source
    assert "debug-add-sidetrend" in source
    assert "bestWidth <= 0.185" in source
    assert "Math.abs(last-first)" in source


def test_chart_debug_reports_include_ticker_and_full_name():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "function debugTickerText()" in source
    assert "function debugInstrumentLines()" in source
    assert "`Ticker: ${{debugTickerText()}}`" in source
    assert "`Full name: ${{P.sourceName || '-'}}`" in source
    assert "lines.push(...debugInstrumentLines());" in source
    assert '<dt>Ticker</dt>' in source
    assert '<dt>Full name</dt>' in source


def test_debug_editors_use_comparison_tables_and_save_sidetrends():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert 'Date (scanner)' in source
    assert 'Price (scanner)' in source
    assert '<th>Use</th><th>#</th><th>From</th><th>To</th><th>Days</th><th>Scanner</th>' in source
    assert "levels.__saved_sidetrends__=" in source
    assert "debugReportMode==='sidetrend'" in source
    assert "Fibo formation containing the sidetrend" in source
    assert "renderGeometryEditor(debugCorrectionKind, true)" in source
    assert "'No changes':after" in source
    assert "reportHeaders=mode==='sidetrend'?['#','From','To','Days','Scanner','Status']" in source
    assert "rows.push(['Anchor A'" in source
    assert "rows.push(['Anchor B'" in source
    assert "rows.push(['Length (calendar days)'" in source
    assert "Complete Fibo candle data" in source
    assert "COMPLETE FIBO DATA" in source


def test_debug_dialog_can_be_dragged_by_its_header():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "handle?.addEventListener('pointerdown'" in source
    assert "handle?.addEventListener('pointermove'" in source
    assert "dialog.style.left=" in source
    assert "dialog.style.top=" in source


def test_anchor_debug_keeps_scanner_geometry_and_creates_colored_correction_copy():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "group_id:'debug-fibo-correction'" in source
    assert "group_id:'debug-wedge-correction'" in source
    assert "live.color='#f43f5e'" in source
    assert "color:'#22d3ee'" in source
    assert "label:`My ${{wedgeSide(o)}} wedge`" in source


def test_debug_report_newline_is_escaped_for_generated_javascript():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "text.indexOf('\\\\n',at)" in source


def test_debug_corrections_are_kept_only_by_explicit_report_action():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "keep-debug-correction" in source
    assert "function restoreUnkeptDebugCorrection()" in source
    assert "requestAnimationFrame(()=>$('saved-fibo-status')?.click())" in source
    assert "<th>Action</th>" not in source
    assert "navigator.clipboard.writeText(copyText)" in source
    assert "drawer.classList.add('debug-report-mode')" in source


def test_sidetrends_fit_chart_and_have_draggable_edge_handles():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "function beginSidetrendDrag(ev)" in source
    assert "function moveSidetrendDrag(ev)" in source
    assert "function endSidetrendDrag(ev)" in source
    assert "chart.timeScale().fitContent()" not in source[source.index("function renderSidetrendEditor"):source.index("function renderGeometryEditor")]
    assert "activeTool='sidetrend-add'" in source
    assert "Click first candle" in source
    assert "debug-toggle-all" in source
    assert "Delete ${{range.id}}" in source
    assert "debugShowSidetrends=mode==='sidetrend'" in source
    assert "debugShowSidetrends=false; restoreUnkeptDebugCorrection(); drawCloud()" in source


def test_sidetrends_are_sorted_and_distant_ranges_start_unselected():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "function sidetrendNearFibo(range)" in source
    assert "limit=62*86400000" in source
    assert "valid:sidetrendNearFibo(range)" in source
    assert "String(a.start).localeCompare(String(b.start))" in source
    assert "String(b.start).localeCompare(String(a.start))" in source
    assert ".filter(r=>r.valid).sort((a,b)=>String(b.start)" in source


def test_unselected_sidetrends_are_hidden_until_requested():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "let debugShowUnselected = false" in source
    assert "if(!range.valid&&!debugShowUnselected)return" in source
    assert 'id="debug-show-unselected"' in source
    assert "debugShowUnselected=!debugShowUnselected" in source


def test_each_sidetrend_uses_its_own_chart_and_table_color():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "function sidetrendColor(index)" in source
    assert "palette[index % palette.length]" in source
    assert "ctx.fillStyle=color.fill" in source
    assert "ctx.strokeStyle=color.stroke" in source
    assert "background:${{color.stroke}}" in source


def test_fibo_boundary_is_draggable_and_resynchronizes_group():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "obj.type === 'fib-boundary' || isWedgeLineObject(obj)" in source
    assert "function syncFibGroupFromBoundary(boundary)" in source
    assert "syncFibGroupFromBoundary(draggedObject);" in source


def test_fibo_anchor_drag_snaps_to_directional_candle_extremes():
    source = UI_SOURCE.read_text(encoding="utf-8")
    start = source.index("if (obj?.type === 'fib-boundary')")
    fib_drag = source[start:source.index("if (!x0 || !x1", start)]

    assert "const isShort = fibBoundaryIsShort(obj);" in fib_drag
    assert "y0 = Number(isShort ? candle.high : candle.low);" in fib_drag
    assert "y1 = Number(isShort ? candle.low : candle.high);" in fib_drag
    assert "candle.close" not in fib_drag


def test_scanner_wedges_use_anchor_geometry_and_not_a_native_series_fallback():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "series = addLine(straightWedgeLineData(obj), color, 2" not in source
    assert "let slope = (y1 - y0) / (x1 - x0);" in source
    assert "if (obj.free_extension && Number.isFinite(endSourceX)" in source


def test_manual_wedge_start_is_snapped_to_the_selected_candle_extreme():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "y0 = candleExtremeForDate(x0, side, y0);" in source
    assert "obj.anchor_y = [y0," in source


def test_wedge_start_can_overlap_the_second_anchor_without_hiding_the_line():
    source = UI_SOURCE.read_text(encoding="utf-8")

    start_drag = source[source.index("if (mode === 'start')"):source.index("else if (mode === 'end'")]
    wedge_renderer = source[source.index("function drawWedgeStraightLines"):source.index("function drawCloud")]

    assert "compareTime(x0, anchorsX[1]) >= 0" not in start_drag
    assert "if (x0 === x1)" in wedge_renderer
    assert "ctx.moveTo(x0, y0);" in wedge_renderer
    assert "ctx.lineTo(targetX, targetY);" in wedge_renderer
    assert "const coincidentAnchors = compareTime(anchors.x0, anchors.x1) === 0;" in source
    assert "(obj.free_extension || coincidentAnchors) ? rawY1" in source
    assert "compareTime(x0, anchorsX[1]) !== 0" in start_drag


def test_scanner_wedge_projection_is_capped_at_thirty_candles():
    selector_source = (UI_SOURCE.parent / "level_selector.py").read_text(encoding="utf-8")
    ui_source = UI_SOURCE.read_text(encoding="utf-8")

    assert "projection_limit = last_idx + 30" in selector_source
    assert "max_projection = last_idx + 30" in selector_source
    assert "let endIdx = maxIdx + 30;" in ui_source
    assert "Math.max(rows.length, 180)" not in ui_source[
        ui_source.index("function wedgeLineThroughExtremeObjects"):
        ui_source.index("function findAlternativeWedgeCandidate")
    ]
