from utilities.web_i18n import COLUMN_POLISH_TRANSLATIONS, ENGLISH_NORMALIZATIONS, POLISH_TRANSLATIONS, language_controls_html
from pathlib import Path


def test_language_controls_are_in_report_toolbar_and_english_first():
    markup = language_controls_html()

    assert "reportHero.parentNode.insertBefore(languageControls,reportHero)" in markup
    assert "position:fixed" not in markup
    assert markup.index("🇬🇧 EN") < markup.index("🇵🇱 PL")
    assert "window.setStockhelperLanguage(savedLanguage(),false)" in markup
    assert "stockhelper-language=${value}" in markup
    assert "MutationObserver" in markup
    assert ".top-choice-compact .top-choice-direction{width:92px!important" in markup
    assert ".top-choice>h2,.top-choice>h3{margin:0;padding:13px 15px" in markup
    assert ".top-choice-compact col.top-choice-stooq{width:112px!important}" in markup
    assert ".top-choice-compact col.top-choice-chart{width:112px!important}" in markup
    assert ".top-choice-compact th.chart-link-cell,.top-choice-compact th.chart-action-cell{min-width:112px!important" in markup
    assert ".top-choice-compact td.chart-link-cell .btn" in markup
    assert "window.translateStockhelperNode=translateNode" in markup
    assert "window.stockhelperTranslateText=translate" in markup
    assert ".favorite-fibo-percent" in markup


def test_translation_tables_are_compiled_once_for_fast_polish_filter_updates():
    markup = language_controls_html()

    assert "const TO_EN_PATTERN=replacementPattern(Object.keys(TO_EN))" in markup
    assert "const PL_LONG_PATTERN=replacementPattern(Object.keys(PL_LONG))" in markup
    assert "output.replace(PL_LONG_PATTERN,source=>PL_LONG[source])" in markup
    assert "Object.entries(PL).sort" not in markup
    assert "node.__stockhelperLanguage===language" in markup


def test_polish_dictionary_covers_reports_journal_and_chart_columns():
    expected = {
        "Why top choice": "Dlaczego wybrano",
        "Breakout date": "Data wybicia",
        "Upper touches": "Górne dotknięcia",
        "StockHelper Transaction Journal": "Dziennik transakcji StockHelper",
        "Trade review": "Ocena transakcji",
        "Position calculator": "Kalkulator pozycji",
        "Download chart PNG": "Pobierz wykres PNG",
        "Unable to calculate position.": "Nie można obliczyć pozycji.",
        "Data required for calculation:": "Dane wymagane do obliczenia:",
        "Copy Google Sheets HYPERLINK formula": "Kopiuj formułę HYPERLINK do Arkuszy Google",
        "Open close-adjust chart": "Otwórz wykres korekty zamknięcia",
        "Accept closing screenshot": "Zatwierdź zrzut zamknięcia",
        "🟢 SOLD": "🟢 SPRZEDANO",
        "Closing screenshot saved. Closing chart...": "Zapisano zrzut zamknięcia. Zamykanie wykresu...",
        "Open stockhelper chart": "Otwórz wykres StockHelper",
        "Open stooq chart": "Otwórz wykres Stooq",
        "Ichimoku information": "Informacje Ichimoku",
        "Reports": "Raporty",
        "Quick access": "Szybki dostęp",
        "Display": "Widok",
        "Info": "Informacje",
        "Output & Style": "Eksport i wygląd",
        "Levels": "Poziomy",
        "Analysis": "Analiza",
        "Tools": "Narzędzia",
        "Reset": "Resetuj",
        "Export": "Eksport",
        "Choose a scanner workspace.": "Wybierz panel skanera.",
        "Your saved tools, ready anytime.": "Twoje zapisane narzędzia, zawsze pod ręką.",
        "Control what you see.": "Wybierz widoczne elementy.",
        "Report information.": "Informacje o raporcie.",
        "Export and customize output.": "Eksportuj i dostosuj wygląd.",
        "ALLSEARCH REPORT": "RAPORT ALLSEARCH",
        "Color instrument": "Pokoloruj",
        "Color instrument — click an instrument to toggle its color": "Pokoloruj instrument — kliknij instrument, aby włączyć lub wyłączyć jego kolor",
        "Choose instrument…": "Wybierz…",
        "Dropouts": "Odrzucone",
        "Show or hide recent Fibo dropouts": "Pokaż lub ukryj ostatnie odrzucone układy Fibo",
        "Debug": "Diagnostyka",
        "Show or hide Fibo debug controls": "Pokaż lub ukryj narzędzia diagnostyczne Fibo",
    }

    for english, polish in expected.items():
        assert POLISH_TRANSLATIONS[english] == polish
    assert ENGLISH_NORMALIZATIONS["Brak wyników."] == "No results."


def test_chart_calculation_error_explains_required_data_without_fetch_details():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "Data required for calculation:" in chart_source
    assert "For Forex and commodities also provide lot cost and pip value." in chart_source
    assert "Unable to calculate:</b>" not in chart_source
    assert "label:polishCloseMode ? 'SPRZEDANO' : 'SOLD'" in chart_source


def test_dynamic_favorites_are_translated_after_they_are_rendered():
    report_source = Path("run").read_text(encoding="utf-8")

    assert "window.translateStockhelperNode?.(root)" in report_source
    assert "favoriteUiText(unclassifiedHelp)" in report_source
    assert "stockhelper-favorite-i18n-fallback" in report_source
    assert POLISH_TRANSLATIONS[
        "Saved favorites that do not occur in the current Allsearch, 3P, or Kliny results."
    ].startswith("Zapisane ulubione")


def test_scanner_workspace_navigation_is_grouped_like_the_chart_toolbar():
    report_source = Path("run").read_text(encoding="utf-8")

    for label in ("Reports", "Quick access", "Display", "Info", "Output &amp; Style"):
        assert f"class='scanner-nav-label'>{label}</span>" in report_source
    assert "class='scanner-nav-actions'" in report_source
    assert ".scanner-nav-group{display:flex;flex-direction:column" in report_source
    assert "StockHelper scanner workspace</h2>" not in report_source
    assert ".scanner-nav-group:first-child{padding-left:0;border-left:0}" in report_source
    assert "Scan. Analyze." not in report_source


def test_colored_instruments_do_not_override_favorite_star_colors():
    report_source = Path("run").read_text(encoding="utf-8")

    assert "body .instrument-colored .favorite-star{color:#64748b!important}" in report_source
    assert "body .instrument-colored .favorite-star.active{color:#facc15!important}" in report_source
    assert "const containsInstrument=!!el.querySelector('[data-ticker]:not(button):not(a)')" in report_source
    assert "!containsInstrument&&colored.has" in report_source


def test_missing_fibo_patterns_use_a_dash_in_report_columns():
    report_source = Path("run").read_text(encoding="utf-8")

    assert 'text.lower() in {"", "none", "nan", "null"}' in report_source
    assert "html.escape(_display_pattern(r.pattern))" in report_source


def test_fibo_board_uses_short_actionable_column_names():
    report_source = Path("run").read_text(encoding="utf-8")

    assert '"| 🚀 Strong impulse | ⚠️ Waiting 23.6→61.8 |' in report_source
    assert 'return "🚀 Strong impulse"' in report_source
    assert 'return "⚠️ Waiting 23.6→61.8"' in report_source
    assert POLISH_TRANSLATIONS["Strong impulse"] == "Silny impuls"
    assert POLISH_TRANSLATIONS["Waiting 23.6→61.8"] == "Oczekujące 23,6→61,8"


def test_favorites_support_bulk_chart_open_clear_and_fibo_percentages():
    report_source = Path("run").read_text(encoding="utf-8")

    assert "Open favorite charts" in report_source
    assert "clearAllFavorites" in report_source
    assert "favorite-fibo-percent" in report_source
    assert "btn.dataset.favoriteTicker||favoriteTicker(btn)" in report_source
    assert "String(o.market).toUpperCase()===activeMarket.toUpperCase()" in report_source


def test_chart_has_two_candle_percent_difference_tool():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert 'id="tool-percent-diff"' in chart_source
    assert "activeTool === 'percent-diff'" in chart_source
    assert "Price difference" in chart_source
    assert "rising ? percentDiffAnchor.low : percentDiffAnchor.high" in chart_source
    assert "rising ? Number(row.high) : Number(row.low)" in chart_source
    assert "fxMicroBearishHarami" in chart_source
    assert 'id="line-color-toggle"' in chart_source
    assert 'class="line-color-menu"' in chart_source
    assert 'class="line-tool-group"' in chart_source


def test_chart_toolbar_labels_have_polish_translations():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    expected = {"Levels": "Poziomy", "Analysis": "Analiza", "Tools": "Narzędzia", "Scanner": "Skaner", "Reset": "Resetuj"}
    for english, polish in expected.items():
        assert f'class="toolbar-label">{english}</span>' in chart_source
        assert POLISH_TRANSLATIONS[english] == polish


def test_chart_toolbar_hints_and_button_tooltips_have_polish_translations():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    hints = {
        "Select key price levels": "Wybierz kluczowe poziomy cenowe",
        "Validate and confirm levels": "Sprawdź i potwierdź poziomy",
        "Drawing & measurement tools": "Narzędzia do rysowania i pomiarów",
        "Find chart patterns": "Znajdź formacje na wykresie",
        "Restore chart drawings": "Przywróć rysunki na wykresie",
    }
    for english, polish in hints.items():
        assert f'class="toolbar-hint">{english}</span>' in chart_source.replace("&amp;", "&")
        assert POLISH_TRANSLATIONS[english] == polish

    toolbar = chart_source[chart_source.index('<div class="toolbar">'):chart_source.index('<div id="close-mode-panel">')]
    literal_buttons = toolbar.split("<button ")[1:]
    assert literal_buttons
    assert all('title="' in button.split(">", 1)[0] for button in literal_buttons)
    assert "b.title=levelButtonTitles[field]" in chart_source
    for tooltip in (
        "Draw a line on the chart", "Line color", "Yellow", "Purple", "Green",
        "Draw Fibonacci 61.8 levels", "Set a half-distance stop loss",
        "Select two candles to calculate the price difference", "Show or hide the Ichimoku overlay",
        "Find a new upper wedge line", "Search for a larger valid alternative around the current wedge",
        "Find a new lower wedge line", "Restore the original scanner-created drawings and remove manual drawing changes",
        "Reset all chart values and drawings", "Download the current chart as a PNG image",
        "Saves chart configuration until it becomes invalid", "Select the high level", "Select the low level",
        "Select the entry level", "Select the stop-loss level", "Check the selected ZR level",
        "Select the line-cross level", "Select chart level",
    ):
        assert tooltip in chart_source
        assert tooltip in POLISH_TRANSLATIONS


def test_chart_save_control_has_complete_polish_translation():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    expected = {
        "Save chart": "Zapisz wykres",
        "Chart saved": "Wykres zapisany",
        "Saves chart configuration until it becomes invalid": "Zapisuje konfigurację wykresu do czasu, aż stanie się nieaktualna",
        "Chart configuration saved until it becomes invalid; click to remove": "Konfiguracja wykresu jest zapisana do czasu, aż stanie się nieaktualna; kliknij, aby usunąć",
        "Chart configuration saved until it becomes invalid.": "Konfiguracja wykresu została zapisana do czasu, aż stanie się nieaktualna.",
    }
    for english, polish in expected.items():
        assert english in chart_source
        assert POLISH_TRANSLATIONS[english] == polish


def test_setup_information_visibility_does_not_depend_on_translated_option_text():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert '<option value="Kliny">Kliny</option>' in chart_source
    assert '<option value="Ichimoku">Ichimoku</option>' in chart_source
    assert '<option value="Fibo">Fibo</option>' in chart_source
    assert '<option value="Manual">Manual</option>' in chart_source
    assert "const showInfo = ['Kliny', 'Ichimoku', 'Fibo'].includes(tech)" in chart_source


def test_instrument_card_toggle_is_global_and_other_card_toggles_are_local():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert chart_source.count('class="side-card-toggle"') == 3
    assert 'data-card="instrument-card"' in chart_source
    assert 'data-card="selected-card"' in chart_source
    assert 'data-card="manual-card"' in chart_source
    assert 'aria-controls="instrument-card-body"' in chart_source
    assert "setSideCardCollapsed" in chart_source
    assert "setAllSideCardsCollapsed" in chart_source
    assert "if(cardId==='instrument-card')" in chart_source
    assert "else{{\n        setSideCardCollapsed(cardId,collapsed);" in chart_source
    assert "stockhelper-side-card-collapsed-" in chart_source
    assert "rememberSideCardCollapsed" in chart_source
    assert "persistSideCardStates" in chart_source
    assert "fetch('/sidebar-card-state'" in chart_source
    assert '@app.route("/sidebar-card-state", methods=["GET", "POST"])' in chart_source
    assert '<section class="side-card instrument-switcher-card">' in chart_source
    assert POLISH_TRANSLATIONS["Collapse section"] == "Zwiń sekcję"
    assert POLISH_TRANSLATIONS["Expand section"] == "Rozwiń sekcję"


def test_stock_cfd_control_is_part_of_manual_inputs_card():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    instrument_body = chart_source.split('id="instrument-card-body"', 1)[1].split("</section>", 1)[0]
    manual_body = chart_source.split('id="manual-card-body"', 1)[1].split("</section>", 1)[0]
    assert 'id="stock-cfd-toggle"' not in instrument_body
    assert 'id="stock-cfd-toggle"' in manual_body
    assert '.manual-card.collapsed' in chart_source
    assert '.manual-card .side-card-head h4 {{ color:#f8fafc; font-size:16px' in chart_source


def test_chart_png_button_sits_next_to_save_chart_with_matching_size():
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    actions = chart_source.split('<div class="chart-save-actions">', 1)[1].split("</div>", 1)[0]
    assert 'id="saved-fibo-status"' in actions
    assert 'id="download-chart-png"' in actions
    assert '.chart-save-actions button {{ flex:0 0 150px; width:150px; min-height:32px; }}' in chart_source
    assert '#saved-fibo-status {{ flex:0 0 auto; width:150px;' in chart_source
    assert 'display:inline-flex; align-items:center; justify-content:center; gap:6px; overflow:hidden;' in chart_source
    assert '<span class="toolbar-label">Export</span>' not in chart_source


def test_selected_3p_controls_are_highlighted_but_group_chart_buttons_are_not():
    report_source = Path("run").read_text(encoding="utf-8")

    assert ".compactbtn.active,.iconbtn.active{" in report_source
    assert ".stockhelper-chart-btn.active" not in report_source
    assert "btn.classList.toggle('active',visible)" in report_source
    assert "btn.classList.toggle('active',active)" in report_source
    assert "function openTrojColumnStockhelperCharts(btn,col){btn?.classList.add('active')" not in report_source
    assert "function openClosestStockhelperCharts(btn){btn?.classList.add('active')" not in report_source
    assert "function openClosestStockhelperCharts(btn){_openStockhelperButtons" in report_source
    assert "chart.addEventListener('click',()=>{chart.classList.add('active')" not in report_source


def test_favorites_and_journal_are_fully_localized():
    expected = {
        "Favorite setups": "Ulubione układy",
        "No favorites": "Brak ulubionych",
        "Favorites not classified anywhere now": "Ulubione obecnie niesklasyfikowane",
        "No unclassified favorites": "Brak niesklasyfikowanych ulubionych",
        "Trade / Review": "Transakcja / ocena",
        "Buy / Entry": "Kupno / wejście",
        "Auto context": "Kontekst automatyczny",
        "Stop loss moves count": "Liczba przesunięć stop loss",
        "Notes saved": "Notatki zapisano",
    }
    for english, polish in expected.items():
        assert POLISH_TRANSLATIONS[english] == polish


def test_market_names_and_currencies_are_not_translated():
    for term in ("Ichimoku", "Fibo", "Stooq", "PLN"):
        assert term not in POLISH_TRANSLATIONS


def test_statuses_and_directions_are_translated():
    assert POLISH_TRANSLATIONS["Ichimoku continuation"] == "Kontynuacja Ichimoku"
    assert POLISH_TRANSLATIONS["Above the cloud"] == "Nad chmurą"
    assert POLISH_TRANSLATIONS["Long"] == "Długa"
    assert POLISH_TRANSLATIONS["Short"] == "Krótka"
    assert POLISH_TRANSLATIONS["Closing Price"] == "Cena zamknięcia"
    assert POLISH_TRANSLATIONS["Calculate position"] == "Oblicz pozycję"
    assert COLUMN_POLISH_TRANSLATIONS["Close"] == "Cena zamknięcia"
    assert POLISH_TRANSLATIONS["Trade Summary"] == "Podsumowanie transakcji"
    assert POLISH_TRANSLATIONS["NO PLAY UNTIL"] == "BEZ TRANSAKCJI DO"
    assert POLISH_TRANSLATIONS["breakout"] == "wybicie"
    assert POLISH_TRANSLATIONS["below"] == "pod chmurą"
    assert POLISH_TRANSLATIONS["bearish_hammer"] == "spadkowy_młot"
    assert POLISH_TRANSLATIONS["valid_reversal"] == "prawidłowe_odwrócenie"


def test_sorted_close_column_uses_price_translation():
    markup = language_controls_html()

    assert "trimmed.replace(/\\s*[↕↑↓]\\s*$/,'')" in markup
    assert "COLUMN_PL[columnKey]" in markup


def test_candlestick_names_follow_polish_reference_material():
    expected = {
        "morning_doji_star": "gwiazda_poranna_doji",
        "evening_doji_star": "gwiazda_wieczorna_doji",
        "piercing_pattern": "formacja_przenikania",
        "bullish_harami": "harami_prowzrostowe",
        "bearish_harami": "harami_prospadkowe",
        "dark_cloud_cover": "zasłona_ciemnej_chmury",
        "bullish_engulfing": "objęcie_hossy",
        "bearish_engulfing": "objęcie_bessy",
    }

    for source, translation in expected.items():
        assert POLISH_TRANSLATIONS[source] == translation

    assert POLISH_TRANSLATIONS["bullish_piercing_line"] == "formacja_przenikania"


def test_remaining_report_controls_and_statuses_are_localized():
    assert POLISH_TRANSLATIONS["Scanner"] == "Skaner"
    assert POLISH_TRANSLATIONS["Fibo pattern"] == "Formacja Fibo"
    assert POLISH_TRANSLATIONS["Show 3P debug"] == "Pokaż diagnostykę 3P"
    assert POLISH_TRANSLATIONS["shallow_retest_pattern"] == "płytki_retest_z_formacją"
    assert POLISH_TRANSLATIONS["Strong"] == "Silne"
    assert POLISH_TRANSLATIONS["FX conversion fee 1%: OFF"].endswith("WYŁ.")
    assert POLISH_TRANSLATIONS["Liquidity legend"] == "Legenda płynności"
    assert POLISH_TRANSLATIONS["base 500 000 PLN"].startswith("wartość bazowa")
    assert COLUMN_POLISH_TRANSLATIONS["Dir."] == "Kierunek"


def test_reported_mixed_language_phrases_have_complete_polish_translations():
    expected = {
        "Bullish piercing line": "Formacja przenikania",
        "Hammer": "Młot",
        "Falling wedge": "Klin opadający",
        "Inside the cloud - PATTERN!": "W chmurze – FORMACJA!",
        "Months since breakout": "Miesiące od wybicia",
        "completed · loss": "zamknięta · strata",
    }

    for source, translation in expected.items():
        assert POLISH_TRANSLATIONS[source] == translation


def test_short_fibo_zero_status_is_direction_aware_in_both_languages():
    markup = language_controls_html()
    scanner_source = Path("scanner_search.py").read_text(encoding="utf-8")

    assert "direction==='short'" in markup
    assert "replaceAll('3p_steep_incline','3p_steep_decline')" in markup
    assert POLISH_TRANSLATIONS["3p_steep_decline"] == "3P_stromy_spadek"
    assert POLISH_TRANSLATIONS["3P steep decline"] == "3P stromy spadek"
    assert '"🚀 3p_steep_decline" if r.direction=="short"' in scanner_source


def test_language_preference_uses_cookie_for_cross_port_views():
    markup = language_controls_html()

    assert "document.cookie.split('; ')" in markup
    assert "Max-Age=31536000; Path=/; SameSite=Lax" in markup
    assert "localStorage.setItem('stockhelper-language',value)" in markup


def test_language_controls_are_injected_into_all_web_views():
    journal_source = Path("journal.py").read_text(encoding="utf-8")
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    report_source = Path("run").read_text(encoding="utf-8")

    assert "<body>{language_ui}<div class='shell'>" in journal_source
    assert "  {language_ui}" in chart_source
    assert '_report_language_script() + "</body></html>"' in report_source
    assert "language_controls_html(show_controls=False)" in journal_source
    assert "language_controls_html(show_controls=False)" in chart_source
    assert "🇬🇧 EN" not in language_controls_html(show_controls=False)


def test_favorite_clear_button_uses_neutral_compact_button_styling():
    html = language_controls_html()
    assert ".favorite-clear-btn{margin-left:8px!important;min-width:28px" in html
    assert "background:rgba(120,53,15,.32)" not in html
