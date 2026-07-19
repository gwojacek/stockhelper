import json
import inspect
from pathlib import Path

import pandas as pd

from utilities.stooq_playwright import (
    _POLISH_MONTHS_BY_NUMBER,
    _capture_stooq_ui_failure,
    _parse_stooq_ui_csv,
)


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
    assert download_source.count("_resolve_stooq_ui_consent_and_captcha") == 2


def test_stooq_playwright_uses_conditions_not_fixed_timeouts():
    source = Path("utilities/stooq_playwright.py").read_text(encoding="utf-8")
    assert "wait_for_timeout(" not in source


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
