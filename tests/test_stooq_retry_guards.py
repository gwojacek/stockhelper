from pathlib import Path

SOURCE = Path("utilities/stooq_playwright.py").read_text(encoding="utf-8")


def test_stooq_blank_retry_defaults_are_small_and_wait_helper_does_not_reload_by_default():
    assert 'STOCKHELPER_STOOQ_BLANK_AUTO_RETRIES", "1"' in SOURCE
    assert 'STOCKHELPER_STOOQ_WAIT_RELOAD_RETRIES", "0"' in SOURCE
    assert 'def _wait_for_table_or_limit_with_retry(page, retries: int | None = None)' in SOURCE
    assert 'attempts = 1 + (retries if retries is not None else _stooq_wait_reload_retries_default())' in SOURCE


def test_stooq_retry_budget_and_no_display_inspector_guard_are_present():
    assert 'def _consume_stooq_retry_budget' in SOURCE
    assert 'blank/no-table retry budget exhausted' in SOURCE
    assert 'def _headed_display_available()' in SOURCE
    assert 'DISPLAY") or os.getenv("WAYLAND_DISPLAY")' in SOURCE
    assert 'headed inspector skipped because DISPLAY/WAYLAND_DISPLAY is not set' in SOURCE
    assert 'forced inspector skipped' in SOURCE
    assert 'STOCKHELPER_STOOQ_FIREFOX_RETRY' in SOURCE
    assert 'headed Chromium fallback skipped' in SOURCE
    assert 'Stooq blank/no-table retry budget exhausted after table wait' in SOURCE
