import json
import inspect
from pathlib import Path

import pandas as pd

from utilities.stooq_playwright import (
    _POLISH_MONTHS_BY_NUMBER,
    _capture_stooq_ui_failure,
    _parse_stooq_ui_csv,
    _drop_local_tail_covered_by_remote,
    _stooq_history_urls,
    _stooq_query_symbol,
    _trim_stooq_ui_history_to_window,
)


def test_forced_rebase_drops_yahoo_only_rows_from_remote_tail():
    local = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-24", "2026-07-28", "2026-07-29", "2026-07-30"]),
            "Close": [58.203, 57.69499969482422, 58.415000915527344, 58.36000061035156],
        }
    )
    remote = pd.DataFrame(
        {
            # Stooq may omit a Yahoo-only date; that old row must still vanish.
            "Date": pd.to_datetime(["2026-07-27", "2026-07-31"]),
            "Close": [58.403, 57.928],
        }
    )

    retained = _drop_local_tail_covered_by_remote(local, remote)

    assert retained["Date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-07-24"]


def test_forex_stooq_urls_use_compact_pair_without_slash():
    assert _stooq_query_symbol("GBP/PLN") == "gbppln"
    assert _stooq_history_urls("GBP/PLN") == ["https://stooq.pl/q/d/?s=gbppln&i=d"]
    source = inspect.getsource(__import__("utilities.stooq_playwright", fromlist=["update_stooq_history_from_ui_csv"]).update_stooq_history_from_ui_csv)
    assert "_stooq_query_symbol(symbol)" in source


def test_parse_polish_stooq_ui_csv():
    payload = (
        "Data,Otwarcie,Najwyzszy,Najnizszy,Zamkniecie\n"
        "1971-01-04,357.73,357.73,357.73,357.73\n"
    ).encode("cp1250")

    frame = _parse_stooq_ui_csv(payload)

    assert list(frame.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert frame.iloc[0]["Date"] == pd.Timestamp("1971-01-04")
    assert frame.iloc[0]["Close"] == 357.73
    assert frame.iloc[0]["Volume"] == 0


def test_full_ui_download_is_trimmed_to_submitted_548_day_window():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2025-01-19", "2025-01-20", "2026-07-20"]),
            "Close": [1.0, 2.0, 3.0, 4.0],
        }
    )

    trimmed = _trim_stooq_ui_history_to_window(frame, pd.Timestamp("2025-01-20").date())

    assert trimmed["Date"].dt.strftime("%Y-%m-%d").tolist() == ["2025-01-20", "2026-07-20"]


def test_july_is_selected_using_the_polish_ui_label():
    assert _POLISH_MONTHS_BY_NUMBER[7] == "lip"


def test_ui_actions_use_dom_clicks_to_bypass_stooq_dark_overlay():
    from utilities.stooq_playwright import update_stooq_history_from_ui_csv

    source = inspect.getsource(update_stooq_history_from_ui_csv)
    assert 'submit.evaluate("button => button.click()")' in source
    assert 'download_link.evaluate("link => link.click()")' in source


def test_filtered_ui_csv_reuses_commodity_consent_and_captcha_flow():
    from utilities.stooq_playwright import (
        _resolve_stooq_ui_consent_and_captcha,
        update_stooq_history_from_ui_csv,
    )

    resolver_source = inspect.getsource(_resolve_stooq_ui_consent_and_captcha)
    download_source = inspect.getsource(update_stooq_history_from_ui_csv)
    assert "_accept_consent_if_present" in resolver_source
    assert "_try_solve_stooq_captcha" in resolver_source
    assert "_retry_blocked_page_before_inspector" in resolver_source
    assert download_source.count("_resolve_stooq_ui_consent_and_captcha") == 3


def test_stooq_consent_is_checked_twice_before_table_fetching():
    from utilities.stooq_playwright import _accept_consent_if_present

    source = inspect.getsource(_accept_consent_if_present)
    assert "for consent_pass in range(4)" in source
    assert "consent_pass == 1 and sel == selectors[0]" in source
    assert "loc.wait_for(state='visible', timeout=3000)" in source
    assert "checking once more for follow-up consent dialog" in source
    assert "consent_pass >= 1" in source
    assert "consent overlay remained visible after repeated acceptance" in source


def test_commodity_table_scraper_uses_double_consent_before_extracting_rows():
    from utilities.stooq_playwright import update_stooq_history_with_playwright

    source = inspect.getsource(update_stooq_history_with_playwright)
    consent = source.index("_accept_consent_if_present(page, first_page=True)")
    extraction = source.index("_extract_rows_from_frame(page)")

    assert consent < extraction
    assert "shared by literal commodities and" in source
    assert "mandatory second consent" in source


def test_forex_browser_uses_exact_download_url_before_ui_fallback():
    from utilities.stooq_playwright import update_stooq_history_from_ui_csv

    source = inspect.getsource(update_stooq_history_from_ui_csv)
    assert 'direct_url = f"https://stooq.pl/q/d/l/?s={compact_symbol}&i=d"' in source
    assert source.index("_download_stooq_direct_csv(page, direct_url)") < source.index("input[name=\"d7\"]")
    assert "direct CSV was empty" in source


def test_rate_limit_ocr_is_capped_at_three_attempts():
    source = Path("utilities/stooq_playwright.py").read_text(encoding="utf-8")
    assert 'min(3, max(1, int(os.getenv("STOCKHELPER_STOOQ_CAPTCHA_ATTEMPTS", "3"))))' in source


def test_stooq_playwright_uses_conditions_not_fixed_timeouts():
    source = Path("utilities/stooq_playwright.py").read_text(encoding="utf-8")
    assert "wait_for_timeout(" not in source


def test_commodity_tail_repair_limits_stooq_scrape_to_first_page():
    source = Path("utilities/stooq_playwright.py").read_text(encoding="utf-8")
    assert 'tail_refresh = os.environ.get("STOCKHELPER_STOOQ_TAIL_REFRESH") == "1"' in source
    assert "max_page = 1 if tail_refresh" in source


def test_ui_failure_writes_screenshot_html_raw_download_and_json(monkeypatch, tmp_path):
    class FakePage:
        url = "https://stooq.pl/q/d/?s=usdjpy"

        def content(self):
            return "<html><body>Odmowa dostępu</body></html>"

        def screenshot(self, *, path, full_page):
            assert full_page is True
            Path(path).write_bytes(b"png")

    monkeypatch.setenv("STOCKHELPER_STOOQ_DEBUG_DIR", str(tmp_path))
    monkeypatch.setenv("STOCKHELPER_STOOQ_TOR", "0")

    info_path = _capture_stooq_ui_failure(
        "USDJPY", FakePage(), "invalid_download", "unexpected columns", b"Odmowa,dostepu\n"
    )
    info = json.loads(Path(info_path).read_text(encoding="utf-8"))

    assert info["stage"] == "invalid_download"
    assert info["download_preview"].startswith("Odmowa")
    assert (tmp_path / "usdjpy_ui_csv_invalid_download.png").exists()
    assert (tmp_path / "usdjpy_ui_csv_invalid_download.html").exists()
    assert (tmp_path / "usdjpy_ui_csv_invalid_download.download").exists()


def test_ui_failure_json_identifies_download_action(monkeypatch, tmp_path):
    class FakePage:
        url = "https://stooq.pl/q/d/?s=usdpln"

        def content(self):
            return "<html>valid table and csv link</html>"

        def screenshot(self, *, path, full_page):
            Path(path).write_bytes(b"png")

    monkeypatch.setenv("STOCKHELPER_STOOQ_DEBUG_DIR", str(tmp_path))
    monkeypatch.setenv("STOCKHELPER_STOOQ_TOR", "0")
    info_path = _capture_stooq_ui_failure(
        "USDPLN",
        FakePage(),
        "download_endpoint_denied",
        "q/d/l denied access",
        b"Odmowa,dostepu\n",
        extra={"download_url": "https://stooq.pl/q/d/l/?s=usdpln&i=d", "download_response_status": 200},
    )

    info = json.loads(Path(info_path).read_text(encoding="utf-8"))
    assert info["stage"] == "download_endpoint_denied"
    assert info["download_url"].endswith("s=usdpln&i=d")
    assert info["download_response_status"] == 200
