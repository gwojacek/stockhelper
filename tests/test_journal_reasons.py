from pathlib import Path

from journal import html_fragment


def test_trade_summary_reason_is_technique_specific_select():
    entries = [
        {"id": "ichi", "technique": "Ichimoku", "reason_label": "Retest + Bullish Harami", "pattern": "Bullish Harami"},
        {"id": "fib", "technique": "Fibo", "reason_label": "Fibo 61.8 + Hammer", "pattern": "Hammer"},
        {"id": "wedge", "technique": "Kliny", "reason_label": "Wedge breakout"},
    ]

    page = html_fragment(entries)

    assert page.count("<select class='summary-autosave summary-reason'") == 3
    assert "<option value='Cloud breakout'>Cloud breakout</option>" in page
    assert "<option value='Retest + Bullish Harami' selected>Retest + Bullish Harami</option>" in page
    assert "<option value='Fibo 61.8 + Hammer' selected>Fibo 61.8 + Hammer</option>" in page
    assert page.count("<option value='Wedge breakout' selected>Wedge breakout</option>") == 1
    assert "Wedge retest" not in page


def test_trade_summary_recovers_legacy_pattern_from_reason_label():
    page = html_fragment([
        {"id": "legacy", "technique": "Ichimoku", "reason_label": "Retest + Morning Star"},
    ])

    assert "<option value='Retest + Morning Star' selected>Retest + Morning Star</option>" in page


def test_chart_sidebar_uses_scanner_patterns_for_reason_choices():
    source = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "['wedge_breakout', 'Wedge breakout']" in source
    assert "wedge_retest" not in source[source.index("const journalReasonOptions"):source.index("function reasonOptionsForTechnique")]
    assert "__scanner_latest_retest_pattern__" in source[source.index("function detectedJournalPattern"):source.index("function reasonLabel")]
    assert "__scanner_pattern_name__" in source[source.index("function detectedJournalPattern"):source.index("function reasonLabel")]
    assert "fibo618PatternFromChart()" in source[source.index("function detectedJournalPattern"):source.index("function reasonLabel")]
    assert "pattern: detectedJournalPattern" in source
