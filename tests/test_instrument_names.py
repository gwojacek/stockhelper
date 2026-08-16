from __future__ import annotations

from pathlib import Path

from utilities.instrument_names import instrument_name_for_ticker


def test_instrument_name_lookup_accepts_provider_and_wig_tickers():
    assert instrument_name_for_ticker("AAPL.US") == "Apple"
    assert instrument_name_for_ticker("KGH") == "KGHM"
    assert instrument_name_for_ticker("KGH.WA / KGH") == "KGHM"


def test_stockhelper_chart_uses_full_name_and_ticker_in_page_title():
    selector = Path("chart_program/level_selector.py").read_text(encoding="utf-8")
    chart_ui = Path("chart_program/lightweight_chart_ui.py").read_text(encoding="utf-8")

    assert "display_name = instrument_name_for_ticker(" in selector
    assert 'chart_identity = f"{chart_identity} ({self.source_ticker})"' in chart_ui
    assert "<title>StockHelper Lightweight Chart - {html.escape(chart_identity)}</title>" in chart_ui
