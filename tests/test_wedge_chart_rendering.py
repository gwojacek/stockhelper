from pathlib import Path


UI_SOURCE = Path(__file__).resolve().parents[1] / "chart_program" / "lightweight_chart_ui.py"


def test_fibo_boundary_is_draggable_and_resynchronizes_group():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "obj.type === 'fib-boundary' || isWedgeLineObject(obj)" in source
    assert "function syncFibGroupFromBoundary(boundary)" in source
    assert "syncFibGroupFromBoundary(draggedObject);" in source


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
