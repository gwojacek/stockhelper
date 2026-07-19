from pathlib import Path


UI_SOURCE = Path(__file__).resolve().parents[1] / "chart_program" / "lightweight_chart_ui.py"


def test_wedge_objects_have_native_series_fallback_for_manual_anchor_dragging():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "series = addLine(straightWedgeLineData(obj), color, 2" in source
    assert "if (series && isEditableLineObject(obj)) objectSeries.set(obj, series);" in source
    assert "series.setData(editableLineData(lineObjectDrag.obj))" in source
