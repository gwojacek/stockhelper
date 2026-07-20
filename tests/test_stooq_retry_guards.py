from pathlib import Path

SOURCE = Path("utilities/stooq_playwright.py").read_text(encoding="utf-8")
RUN_SOURCE = Path("run").read_text(encoding="utf-8")
STOCK_SOURCE = Path("stock").read_text(encoding="utf-8")
LOADER_SOURCE = Path("chart_program/chart_loader.py").read_text(encoding="utf-8")
SCANNER_SOURCE = Path("scanner_search.py").read_text(encoding="utf-8")


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
    assert 'no proxy pool rotation available' in SOURCE
    assert 'if _stooq_verbose_enabled():' in SOURCE
    assert 'browser.new_context(**context_kwargs)' in SOURCE
    assert 'context_kwargs["proxy"] = proxy' in SOURCE
    assert 'invalid proxy from' in SOURCE
    assert 'Use a real numeric port' in SOURCE
    assert 'STOCKHELPER_STOOQ_TOR' in SOURCE
    assert 'STOCKHELPER_STOOQ_TOR_PROXY' in SOURCE
    assert 'SIGNAL NEWNYM' in SOURCE
    assert 'STOCKHELPER_STOOQ_TOR_AUTO' in SOURCE
    assert 'def _stooq_tor_proxy_reachable' in SOURCE


def test_stooq_fetch_keeps_auto_captcha_handling_in_main_flow():
    assert '_handle_captcha_interactive(page, symbol, interactive_state, interactive_captcha)' in SOURCE
    assert 'Stooq page load failed. URL:' in SOURCE
    assert 'STOCKHELPER_STOOQ_TOR_CONTROL' in SOURCE
    assert '_CAPTCHA_SOLVER_LOGGED_SYMBOLS' in SOURCE
    assert "lookback_days: int = 548" in SOURCE
    assert "remote = _trim_stooq_ui_history_to_window(remote, start)" in SOURCE


def test_allsearch_enables_tor_for_stooq_playwright_by_default():
    assert 'os.environ.setdefault("STOCKHELPER_STOOQ_TOR", "1")' in RUN_SOURCE
    assert 'f"[allsearch] Stooq Playwright Tor mode=' in RUN_SOURCE


def test_allsearch_top_choice_actions_are_scoped_to_their_category():
    selector = "btn?.closest('.top-choice-group')||btn?.closest('.top-choice')"
    assert RUN_SOURCE.count(selector) >= 4
    assert "function openClosestStockhelperCharts(btn)" in RUN_SOURCE
    assert "function copyClosestSheetsCells(btn)" in RUN_SOURCE


def test_forex_uses_two_fresh_csv_sessions_and_reports_fetch_paths():
    assert "attempts = 2" in LOADER_SOURCE
    assert "previous browser session closed" in LOADER_SOURCE
    assert 'return "downloaded_csv"' in SCANNER_SOURCE
    assert 'return "table_ui"' in SCANNER_SOURCE
    assert '_print_forex_source_summary("search", members, data_source_by_ticker)' in SCANNER_SOURCE
    assert '_print_forex_source_summary("fibo", members, data_source_by_ticker)' in SCANNER_SOURCE
    assert '_forex_csv_health_check(members, data_source_by_ticker)' in SCANNER_SOURCE
    assert 'not in {"commodities", "forex"}' in SCANNER_SOURCE


def test_report_container_is_auto_removed_and_stale_runs_use_compose_label_cleanup():
    assert 'docker compose run --rm --no-deps' in STOCK_SOURCE
    assert 'label=com.docker.compose.service=stockhelper' in STOCK_SOURCE
    assert 'docker compose run --rm will delete this one-shot container' in RUN_SOURCE
