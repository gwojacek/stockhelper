from pathlib import Path


UI_SOURCE = Path(__file__).resolve().parents[1] / "chart_program" / "lightweight_chart_ui.py"
I18N_SOURCE = Path(__file__).resolve().parents[1] / "utilities" / "web_i18n.py"
SCANNER_SOURCE = Path(__file__).resolve().parents[1] / "scanner_search.py"
LEVEL_SELECTOR_SOURCE = Path(__file__).resolve().parents[1] / "chart_program" / "level_selector.py"


def test_debug_tools_offer_technique_specific_choosers_and_shared_report_drawer():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "choose-sidetrends" in source
    assert "choose-fibo-anchors" in source
    assert "choose-wedge-anchors" in source
    assert "$('debug-tools').onclick = () =>" in source
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


def test_sidetrend_scanner_grows_mean_reverting_month_scale_channels():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    detector = source[source.index("function detectedMonthlySidetrends()") : source.index("function sidetrendNearFibo")]

    assert "minSessions=19" in detector
    assert "maxChannelWidth=0.185" in detector
    assert "maxRegressionMove=0.03" in detector
    assert "maxTrendFit=0.35" in detector
    assert "trendFit<=maxTrendFit" in detector
    assert "if(!score(ohlc.slice(start,end+1)))continue" in detector
    assert "score(ohlc.slice(start,candidate+1))" in detector
    assert "days < 30" not in detector
    assert "bestWidth <= 0.185" not in detector


def test_chart_debug_reports_include_ticker_and_full_name():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "function debugTickerText()" in source
    assert "function debugInstrumentLines()" in source
    assert "`Ticker: ${{debugTickerText()}}`" in source
    assert "`Full name: ${{P.sourceName || '-'}}`" in source
    assert "lines.push(...debugInstrumentLines());" in source
    assert 'id="debug-report-identity" class="debug-report-identity"' in source
    assert "classList.add('debug-instrument')" in source
    assert 'id="calc-head"' not in source
    assert "left:50%; top:50%" in source
    assert "transform:translate(-50%,-50%)" in source


def test_debug_editors_use_comparison_tables_and_save_sidetrends():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert 'Date (scanner)' in source
    assert 'Price (scanner)' in source
    assert '<th>Use</th><th>#</th><th>From</th><th>To</th><th>Days</th><th>Scanner</th>' in source
    assert "levels.__saved_sidetrends__=" in source
    assert "debugReportMode==='sidetrend'" in source
    assert "Fibo formation containing the sidetrend" in source
    assert "renderGeometryEditor(debugCorrectionKind, true)" in source
    assert "correctedCells=same?['-','-','-','-']" in source
    assert "reportHeaders=mode==='sidetrend'?['#','From (scanner)','To (scanner)','Days (scanner)','From (corrected)','To (corrected)','Days (corrected)','Difference','Status']" in source
    assert "rows.push(['Anchor A'" in source
    assert "rows.push(['Anchor B'" in source
    assert "rows.push(['Length (calendar days)'" in source
    assert "Complete Fibo candle data" in source
    assert "COMPLETE FIBO DATA" in source
    assert "['Item','Date (scanner)','Date (corrected)','Price (scanner)','Price (corrected)']" in source
    assert "<th>Point</th><th>Date (scanner)</th><th>Date (yours)</th><th>Price (scanner)</th><th>Price (yours)</th>" in source
    assert "['Item','Start date (scanner)','Start date (corrected)','End date (scanner)','End date (corrected)','Start price (scanner)','Start price (corrected)','End price (scanner)','End price (corrected)']" in source
    assert "scannerCells[0],correctedCells[0],scannerCells[2],correctedCells[2]" in source
    assert "scannerCells[1],correctedCells[1],scannerCells[3],correctedCells[3]" in source
    assert "same?'-':String(afterValue?.x0" in source
    assert "#calc-table.debug-report > table th:not(:first-child)" in source


def test_debug_tools_and_reports_have_polish_translations():
    source = UI_SOURCE.read_text(encoding="utf-8")
    i18n_source = I18N_SOURCE.read_text(encoding="utf-8")

    translated_labels = [
        "Debug tools — Fibo anchors",
        "Debug tools — Wedge anchors",
        "Fibo anchor correction report",
        "Wedge correction report",
        "Sidetrend correction report",
        "Start date (scanner)",
        "Start date (corrected)",
        "End date (scanner)",
        "End date (corrected)",
        "Date (yours)",
        "Price (yours)",
        "Show report",
        "Show unselected",
        "A (low)",
        "B (high)",
        "Wedge anchors",
        "Correct the scanner upper and lower wedge lines.",
        "Ordinary line",
        "Save wedge",
    ]
    for label in translated_labels:
        assert f'"{label}":' in i18n_source
    source_labels = [label for label in translated_labels if label not in {
        "Fibo anchor correction report", "Wedge correction report", "Sidetrend correction report", "Show unselected"
    }]
    for label in source_labels:
        assert label in source


def test_manual_wedge_line_tool_draws_two_colored_lines_and_saves_them():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert 'id="line-tool-group"' in source
    assert "$('line-tool-group').classList.toggle('kind-open')" in source
    assert "if(!scannerWedgeAvailable)" in source
    assert "activeTool='manual-wedge'" in source
    assert "side=manualWedgeStep===0?'upper':'lower'" in source
    assert "color:side==='upper'?'#dc2626':'#2563eb'" in source
    assert "group_id:'auto-wedge'" in source
    assert "manualWedgeStep < 2" in source
    assert 'id="save-manual-wedge"' in source
    save_actions = source[source.index('<div class="chart-save-actions">'):source.index('</div></div><div class="legend-row">')]
    assert save_actions.index('id="save-manual-wedge"') < save_actions.index('id="saved-fibo-status"') < save_actions.index('id="download-chart-png"')
    assert "manualPrice=manualWedgeStep===0?Number(row.high):Number(row.low)" in source
    assert "$('save-manual-wedge').classList.add('ready')" in source
    assert "#save-manual-wedge.ready" in source
    assert "anchor_x:[lineAnchor.x,time], anchor_y:[lineAnchor.y,price]" in source
    assert "obj.anchor_x=[x0,x1]" in source
    assert "obj.anchor_y=[y0,y1]" in source
    assert "futureTimes[Math.min(59,futureTimes.length-1)]" in source
    assert "__saved_manual_wedges__:wedgeObjects,__saved_wedge_by_user__:true" in source
    assert "wedgeOnlySavedForScanner=Array.isArray(levels.__saved_manual_wedges__)" in source
    assert "const wedgeOnlySaveVisible = wedgeOnlySavedForScanner" in source
    assert "levels.__journal_source_technique__ === 'Kliny'" in source
    assert "savedWedgeByUser = wedgeOnlySaveVisible ||" in source
    assert "!wedgeOnlySavedForScanner || initialWedgeGeometry !== '[]'" in source
    save_function = source[source.index("async function saveManualWedge()"):source.index("function forgetLevelSeries")]
    assert "collectLevelsForSave" not in save_function
    assert "savedWedgeByUser=true" not in save_function
    assert "levels.__saved_manual_wedges__=wedgeObjects" in save_function
    assert "wedgeOnlySavedForScanner=true" in save_function
    assert "The wedge is ready to save." not in source
    assert "body:JSON.stringify({{levels:payload,screenshot:null}})" in source
    scanner_source = SCANNER_SOURCE.read_text(encoding="utf-8")
    assert 'state.get("__saved_manual_wedges__")' in scanner_source
    assert 'len(state["__saved_manual_wedges__"]) >= 2' in scanner_source
    assert "def _idx_anchor(raw: tuple[str, float], *, allow_nearest: bool = False)" in scanner_source
    assert "up1 = _idx_anchor(upper_raw[1], allow_nearest=True)" in scanner_source
    assert "lo1 = _idx_anchor(lower_raw[1], allow_nearest=True)" in scanner_source
    assert "const isExtreme=side==='upper'?isHigh:isLow" in source
    assert "const target=Math.min(rows.length-2,nearest(date).idx)" in source
    assert "if(isExtreme(i))return i" in source
    assert "manualWedgeDraftIds=replacement.map(obj=>obj.id)" in source
    assert "const scannerWedges=initialScannerDrawnObjects.filter(isWedgeLineObject)" in source
    assert "if (scannerWedges.length < 2) return false" in source
    assert "__saved_wedge_by_user__:savedWedgeByUser||wedgeOnlySavedForScanner" in source
    assert "payload.__saved_wedge_by_user__ = wedgeOnlySavedForScanner" in source
    assert "wedge:wedgeOnlySavedForScanner" in source


def test_wedge_only_save_geometry_is_hidden_from_non_wedge_charts():
    source = LEVEL_SELECTOR_SOURCE.read_text(encoding="utf-8")

    assert 'wedge_only_save = existing.get("__saved_manual_wedges__")' in source
    assert "if not args.wedge_lines and isinstance(wedge_only_save, list)" in source
    assert 'obj.get("type") == "wedge" or obj.get("group_id") == "auto-wedge"' in source


def test_saved_wedge_chart_loads_exact_user_geometry_after_allsearch():
    selector_source = LEVEL_SELECTOR_SOURCE.read_text(encoding="utf-8")
    scanner_source = SCANNER_SOURCE.read_text(encoding="utf-8")

    assert 'parser.add_argument("--wedge-saved-by-user", action="store_true")' in selector_source
    assert 'saved_flag = " --wedge-saved-by-user" if wedge.saved_by_user else ""' in scanner_source
    assert 'if args.wedge_saved_by_user and isinstance(dedicated_wedge, list)' in selector_source
    assert 'existing["drawn_objects"] = json.loads(json.dumps(dedicated_wedge))' in selector_source
    exact_load = selector_source.index('existing["drawn_objects"] = json.loads(json.dumps(dedicated_wedge))')
    auto_snap = selector_source.index('up0 = _snap_wedge_anchor(up0, "upper")')
    assert exact_load < auto_snap


def test_wedge_debug_button_opens_its_only_tool_directly():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "$('debug-tools').onclick = () => selectedJournalTechnique()==='Kliny'?renderGeometryEditor('wedge'):renderDebugChooser()" in source
    editor = source[source.index("function renderGeometryEditor"):source.index("function renderDebugChooser")]
    assert "$('debug-dialog').classList.add('open')" in editor


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
    assert "function debugGeometryValues(obj)" in source
    assert "obj.group_id === 'debug-wedge-correction' && wedgeSide(obj) === side" in source
    assert "scannerUpper=debugGeometryValues" in source
    assert "function showCorrectionReport(refreshOnly=false)" in source
    assert "refreshOpenDebugReport();" in source
    assert "geometryCells(before)" in source


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
    assert "const reportOpen=$('calc-drawer')?.classList.contains('open')&&$('calc-table')?.classList.contains('debug-report')" in source
    assert "if(!reportOpen) restoreUnkeptDebugCorrection();" in source
    assert "$('calc-close').onclick = () => {{ $('calc-drawer').classList.remove('open');" in source
    assert "debugShowSidetrends=false; restoreUnkeptDebugCorrection(); drawCloud()" in source


def test_sidetrends_are_sorted_and_distant_ranges_start_unselected():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "function sidetrendNearFibo(range)" in source
    assert "limit=62*86400000" in source
    assert "valid:sidetrendNearFibo(range)" in source
    assert "String(a.start).localeCompare(String(b.start))" in source
    assert "String(b.start).localeCompare(String(a.start))" in source
    assert ".filter(r=>(r.valid||r.markedInvalid)" in source


def test_unselected_sidetrends_are_hidden_until_requested():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "let debugShowUnselected = false" in source
    assert "if(!range.valid&&!range.markedInvalid&&!debugShowUnselected)return" in source
    assert 'id="debug-show-unselected"' in source
    assert "debugShowUnselected=!debugShowUnselected" in source
    assert "const reportSidetrends=[...(debugSideRanges||[])]" in source


def test_chart_reserves_space_below_the_lightweight_canvas_for_time_axis():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "#chart .tv-lightweight-charts {{ width:100% !important; height:calc(100% - 28px) !important; }}" in source
    assert "Math.floor(r.height - 28)" in source


def test_chart_and_drawer_have_a_persisted_drag_splitter():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert 'id="calc-splitter" role="separator"' in source
    assert 'id="calc-drawer" class="chart-stage"' in source
    assert "DRAWER_HEIGHT_STORAGE_KEY='stockhelper_calc_drawer_height_v1'" in source
    assert "localStorage.setItem(DRAWER_HEIGHT_STORAGE_KEY" in source
    assert "splitter?.addEventListener('pointermove'" in source
    assert "setDrawerHeight(resize.height+(resize.y-ev.clientY))" in source
    assert "#calc-splitter::after" in source
    assert "splitter.classList.add('resizing')" in source
    splitter_css = source[source.index("#calc-splitter {{"):source.index("#calc-drawer {{")]
    assert "content:'↕'" in splitter_css
    assert "border:0; background:#071426; color:#94a3b8" in splitter_css
    assert "#ea580c" not in splitter_css
    assert "#f97316" not in splitter_css


def test_save_chart_and_png_buttons_have_identical_dimensions():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert ".chart-save-actions button {{ box-sizing:border-box; flex:0 0 150px; width:150px; height:34px; min-height:34px; padding:5px 10px; }}" in source


def test_png_export_crops_overlay_instead_of_rescaling_wedge_geometry():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "function drawChartOverlayForExport(ctx,overlay,base,destinationY=0)" in source
    assert "sourceWidth=Math.min(overlay.width,base.width)" in source
    assert "sourceHeight=Math.min(overlay.height,base.height)" in source
    assert "drawChartOverlayForExport(ctx,overlay,base,headerHeight)" in source
    assert "drawChartOverlayForExport(ctx,overlay,base,0)" in source


def test_sidetrend_report_orders_selected_data_before_complete_fibo_data():
    source = UI_SOURCE.read_text(encoding="utf-8")
    report = source[source.index("function showCorrectionReport"):source.index("function restoreUnkeptDebugCorrection")]

    selected_data = "const reportSidetrends=[...(debugSideRanges||[])]"
    assert report.index(selected_data) < report.index("Complete Fibo candle data")
    assert "copyData.push(`COMPLETE FIBO DATA" in report
    assert "<tr><td>Move (%)" not in source[source.index("const geometrySummary"):source.index("$('debug-dialog-body').innerHTML", source.index("const geometrySummary"))]


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


def test_sidetrend_can_be_explicitly_marked_invalid_and_saved():
    source = UI_SOURCE.read_text(encoding="utf-8")

    assert "range.markedInvalid=!range.markedInvalid" in source
    assert "Marked invalid" in source
    assert "levels.__saved_invalid_sidetrends__=" in source
    assert "Array.isArray(levels.__saved_invalid_sidetrends__)" in source


def test_changed_sidetrend_report_tab_excludes_all_fibo_data():
    source = UI_SOURCE.read_text(encoding="utf-8")
    report = source[source.index("function showCorrectionReport"):source.index("function restoreUnkeptDebugCorrection")]

    assert "Changed / invalid" in report
    assert "debugSidetrendReportFilter!=='changed'" in report
    assert "sidetrendChanged(r)" in report
    assert "if(boundary && debugSidetrendReportFilter!=='changed')" in report
    assert "mode==='sidetrend'&&debugSidetrendReportFilter!=='changed'&&fibStart>=0" in report


def test_corrected_sidetrend_report_uses_union_of_scanner_and_corrected_dates():
    source = UI_SOURCE.read_text(encoding="utf-8")
    report = source[source.index("function showCorrectionReport"):source.index("function restoreUnkeptDebugCorrection")]

    assert "function showCorrectionReport" in report
    assert "const sidetrendCoverage=r=>" in report
    assert "r.scannerStart<r.start?r.scannerStart:r.start" in report
    assert "r.scannerEnd>r.end?r.scannerEnd:r.end" in report
    assert "scannerCandlesCsv(500,coverage.start)" in report
    assert "line.slice(0,10)>coverage.end" in report
    assert "full coverage ${{coverage.start}} → ${{coverage.end}}" in report
    assert "sidetrendDateDifference(r)" in report
