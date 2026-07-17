from pathlib import Path

SOURCE = Path("utilities/stooq_playwright.py").read_text(encoding="utf-8")


def test_stooq_blank_retry_defaults_are_small_and_wait_helper_does_not_reload_by_default():
    assert 'STOCKHELPER_STOOQ_BLANK_AUTO_RETRIES", "1"' in SOURCE
    assert 'STOCKHELPER_STOOQ_WAIT_RELOAD_RETRIES", "0"' in SOURCE
    assert 'def _wait_for_table_or_limit_with_retry(page, retries: int | None = None)' in SOURCE
    assert 'attempts = 1 + (retries if retries is not None else _stooq_wait_reload_retries_default())' in SOURCE


def test_stooq_no_display_inspector_guard_is_present():
    assert 'def _headed_display_available()' in SOURCE
    assert 'DISPLAY") or os.getenv("WAYLAND_DISPLAY")' in SOURCE
    assert 'headed inspector skipped because DISPLAY/WAYLAND_DISPLAY is not set' in SOURCE
    assert 'forced inspector skipped' in SOURCE
    assert 'STOCKHELPER_STOOQ_FIREFOX_RETRY' in SOURCE
    assert 'headed Chromium fallback skipped' in SOURCE
    assert "img[src*='/q/l/s/i/']" in SOURCE
    assert 'Screenshot: {shot}' in SOURCE
    assert 'STOCKHELPER_STOOQ_DEBUG_DIR' in SOURCE
    assert 'debug screenshot saved for' in SOURCE
    assert 'html_path.write_text(page.content()' in SOURCE
    assert 'launching headless and skipping inspector pause' in SOURCE
    assert '--inspector requires a GUI display visible inside the process' in SOURCE
    assert 'debug_stooq_page symbol=' in SOURCE
    assert 'out_dir = out_dir or _stooq_debug_dir()' in SOURCE
    assert 'debug page artifacts saved' in SOURCE


def test_stooq_proxy_pool_configuration_is_supported():
    assert 'STOCKHELPER_STOOQ_PROXY_POOL' in SOURCE
    assert 'STOCKHELPER_STOOQ_PROXY_POOL_INDEX' in SOURCE
    assert 'no Playwright proxy configured' in SOURCE
    assert 'rotating Stooq proxy pool to slot' in SOURCE
    assert 'proxy_pool_index' in SOURCE
    assert 'def _stooq_proxy_pool_initial_index' in SOURCE
    assert 'def _recover_blank_page_with_proxy_rotation' in SOURCE
    assert 'proxy rotation skipped because STOCKHELPER_STOOQ_PROXY_POOL has' in SOURCE
