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


def test_polish_dictionary_covers_reports_journal_and_chart_columns():
    expected = {
        "Why top choice": "Dlaczego wybrano",
        "Breakout date": "Data wybicia",
        "Upper touches": "Górne dotknięcia",
        "StockHelper Transaction Journal": "Dziennik transakcji StockHelper",
        "Trade review": "Ocena transakcji",
        "Position calculator": "Kalkulator pozycji",
        "Download chart PNG": "Pobierz wykres PNG",
    }

    for english, polish in expected.items():
        assert POLISH_TRANSLATIONS[english] == polish
    assert ENGLISH_NORMALIZATIONS["Brak wyników."] == "No results."


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
