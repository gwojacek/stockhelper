from pathlib import Path


def test_forex_ui_download_compacts_slash_pair_in_every_history_url():
    source = Path("utilities/stooq_playwright.py").read_text(encoding="utf-8")
    assert 'return (symbol or "").strip().lower().replace("/", "")' in source
    assert 'url = f"https://stooq.pl/q/d/?s={_stooq_query_symbol(symbol)}"' in source
    assert 'url = f"https://stooq.pl/q/d/?s={_stooq_query_symbol(symbol)}&i=d&l={page_num}"' in source
    assert 'f"https://stooq.pl/q/d/?s={c}&i=d"' in source
    assert 'symbol.strip().lower()' not in source


def test_chart_loader_compacts_forex_before_table_ui_downloader():
    source = Path("chart_program/chart_loader.py").read_text(encoding="utf-8")
    assert 'stooq_forex_symbol = symbol.replace("/", "")' in source
    assert "symbol=stooq_forex_symbol.lower()," in source
    assert "update_stooq_history_from_ui_csv" not in source
