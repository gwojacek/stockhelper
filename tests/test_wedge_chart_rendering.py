from pathlib import Path


UI_SOURCE = Path(__file__).resolve().parents[1] / "chart_program" / "lightweight_chart_ui.py"


def test_debug_tools_offer_technique_specific_choosers_and_shared_report_drawer():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "choose-sidetrends" in source
    assert "choose-fibo-anchors" in source
    assert "choose-wedge-anchors" in source
    assert "$('debug-tools').onclick = renderDebugChooser" in source
    assert "debugToolsBtn.style.display = ['Fibo', 'Kliny'].includes(tech)" in source
    assert "$('calc-title').textContent='Correction report'" in source
    assert "Copy result" in source


def test_sidetrend_debug_editor_draws_and_allows_date_or_validity_corrections():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "function detectedMonthlySidetrends()" in source
    assert "function renderSidetrendEditor()" in source
    assert "function drawDebugSidetrends(ctx)" in source
    assert 'type="checkbox"' in source
    assert 'type="date"' in source
    assert "debug-add-sidetrend" in source


def test_anchor_debug_keeps_scanner_geometry_and_creates_colored_correction_copy():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "group_id:'debug-fibo-correction'" in source
    assert "group_id:'debug-wedge-correction'" in source
    assert "live.color='#f43f5e'" in source
    assert "color:'#22d3ee'" in source
    assert "label:`My ${{wedgeSide(o)}} wedge`" in source


def test_debug_report_newline_is_escaped_for_generated_javascript():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "text.indexOf('\\\\n',markerAt)" in source


def test_debug_corrections_are_kept_only_by_explicit_report_action():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "keep-debug-correction" in source
    assert "function restoreUnkeptDebugCorrection()" in source
    assert "requestAnimationFrame(()=>$('saved-fibo-status')?.click())" in source
    assert "<th>Action</th>" not in source


def test_sidetrends_fit_chart_and_have_draggable_edge_handles():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "function beginSidetrendDrag(ev)" in source
    assert "function moveSidetrendDrag(ev)" in source
    assert "function endSidetrendDrag(ev)" in source
    assert "chart.timeScale().fitContent()" in source[source.index("function renderSidetrendEditor"):source.index("function renderGeometryEditor")]


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
