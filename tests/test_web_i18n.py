from utilities.web_i18n import ENGLISH_NORMALIZATIONS, POLISH_TRANSLATIONS, language_controls_html
from pathlib import Path


def test_language_controls_are_flagged_fixed_and_english_first():
    markup = language_controls_html()

    assert "position:fixed;top:12px;right:14px" in markup
    assert markup.index("🇬🇧 EN") < markup.index("🇵🇱 PL")
    assert "window.setStockhelperLanguage('en')" in markup
    assert "MutationObserver" in markup


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


def test_market_vocabulary_is_not_translated():
    for term in ("Ichimoku", "Fibo", "Stooq", "Long", "Short", "PLN"):
        assert term not in POLISH_TRANSLATIONS


def test_language_controls_are_injected_into_all_web_views():
    journal_source = Path("journal.py").read_text(encoding="utf-8")
    chart_source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")
    report_source = Path("run").read_text(encoding="utf-8")

    assert "<body>{language_ui}<div class='shell'>" in journal_source
    assert "  {language_ui}" in chart_source
    assert '_report_language_script() + "</body></html>"' in report_source
