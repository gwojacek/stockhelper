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
    assert 'STOCKHELPER_STOOQ_TABLE_WAIT_MS", "8000"' in SOURCE
    assert 'tr[id^=\'t\']:has(td:nth-child(8))' in SOURCE
    assert 'reloading here only recreated the dialog' in SOURCE


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
    assert 'browser_name: str = "chrome"' in SOURCE
    assert 'launch_kwargs["channel"] = "chrome"' in SOURCE
    assert '"service_workers": "block"' in SOURCE
    assert 're.compile(r"(?:boq|bog)-content-ads-contributor"' in SOURCE
    assert 'context.route(broken_contributor' in SOURCE
    assert 'page.route(broken_contributor' in SOURCE
    assert '"Network.setBlockedURLs"' in SOURCE
    assert "STOCKHELPER_STOOQ_ALLOW_BROKEN_AD_SCRIPT" not in SOURCE
    assert 'debug_stooq_page symbol=' in SOURCE
    assert 'out_dir = out_dir or _stooq_debug_dir()' in SOURCE
    assert 'debug page artifacts saved' in SOURCE
    assert 'browser = browser_type.launch(**launch_kwargs)' in SOURCE


def test_stooq_bulk_download_retains_only_newest_archive_and_clears_debug():
    assert "def _clear_stooq_bulk_debug_dir()" in SOURCE
    assert "def _prune_stooq_bulk_downloads(" in SOURCE
    bulk_download = SOURCE[
        SOURCE.index("def _download_stooq_wig_bulk_zip("):
        SOURCE.index("def _find_wse_txt_members(")
    ]
    assert "_clear_stooq_bulk_debug_dir()" in bulk_download
    assert "_prune_stooq_bulk_downloads(download_dir)" in bulk_download
    assert 'browser_name="chrome"' in bulk_download
    assert "def _wait_for_stooq_bulk_link(" in SOURCE
    assert "bulk link missing on direct connection; retrying through Tor SOCKS" in bulk_download
    assert "use_proxy=not direct_first" in bulk_download
    assert "use_proxy=True" in bulk_download
    assert "accept_downloads=True" in bulk_download


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
    assert 'STOCKHELPER_STOOQ_TOR_AUTO' in SOURCE
    assert 'def _stooq_tor_proxy_reachable' in SOURCE
    assert 'direct connection had no table, retrying through Tor SOCKS' in SOURCE


def test_stooq_fetch_keeps_auto_captcha_handling_in_main_flow():
    assert '_handle_captcha_interactive(page, symbol, interactive_state, interactive_captcha)' in SOURCE
    assert 'Stooq page load failed. URL:' in SOURCE
    assert '_CAPTCHA_SOLVER_LOGGED_SYMBOLS' in SOURCE
    assert "lookback_days: int = 548" in SOURCE
    assert "remote = _trim_stooq_ui_history_to_window(remote, start)" in SOURCE

    switch_source = SOURCE[
        SOURCE.index("def _switch_to_inspector_for_captcha("):
        SOURCE.index("def _accept_consent_if_present(")
    ]
    auto_solver = switch_source.index("_try_solve_stooq_captcha(page, symbol)")
    interactive_guard = switch_source.index("if not interactive_captcha:")
    assert auto_solver < interactive_guard


def test_stooq_captcha_preprocessing_supports_current_black_grid_challenge():
    preprocess_source = SOURCE[
        SOURCE.index("def _preprocess_stooq_captcha_image("):
        SOURCE.index("def _captcha_code_from_text(")
    ]
    assert "cv2.countNonZero(red_mask)" in preprocess_source
    assert "cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU" in preprocess_source
    assert "horizontal_grid" in preprocess_source
    assert "vertical_grid" in preprocess_source


def test_allsearch_uses_direct_connection_before_tor_fallback():
    assert 'os.environ.setdefault("STOCKHELPER_STOOQ_DIRECT_FIRST", "1")' in RUN_SOURCE
    assert 'connection mode=direct-first' in RUN_SOURCE


def test_commodity_health_repair_precedes_ichimoku_calculation():
    ichimoku_source = SCANNER_SOURCE[
        SCANNER_SOURCE.index("def run_ichimoku_search("):
        SCANNER_SOURCE.index("def run_fibo_search(")
    ]
    health = ichimoku_source.index("unresolved = _commodity_csv_health_check(members)")
    targets_cleared = ichimoku_source.index('os.environ.pop("STOCKHELPER_COMMODITIES_REFRESH_TICKERS", None)')
    audited_targets_cleared = ichimoku_source.index('os.environ.pop("STOCKHELPER_MARKET_REFRESH_SYMBOLS", None)')
    scan_start = ichimoku_source.index("def _record_scan_error(")
    assert health < targets_cleared < audited_targets_cleared < scan_start
    assert "aborting Ichimoku: commodity history is still unhealthy after repair" in ichimoku_source
    assert ichimoku_source.count("_commodity_csv_health_check(members)") == 1

    commodity_loader = LOADER_SOURCE[
        LOADER_SOURCE.index("use_commodity_yahoo_freshness ="):
        LOADER_SOURCE.index("if is_literal_commodity:")
    ]
    assert "if use_commodity_yahoo_freshness and not _force_remote_refresh_enabled():" in commodity_loader


def test_allsearch_top_choice_actions_are_scoped_to_their_category():
    selector = "btn?.closest('.top-choice-group')||btn?.closest('.top-choice')"
    assert RUN_SOURCE.count(selector) >= 4
    assert "function openClosestStockhelperCharts(btn)" in RUN_SOURCE
    assert "function copyClosestSheetsCells(btn)" in RUN_SOURCE


def test_forex_uses_table_ui_only_and_reports_fetch_paths():
    forex_branch = LOADER_SOURCE[LOADER_SOURCE.index('if instrument_type == "forex":'):]
    forex_branch = forex_branch[:forex_branch.index('if instrument_type == "commodity" and _is_index_like_commodity')]
    assert "update_stooq_history_with_playwright" in forex_branch
    assert "interactive_captcha=_stooq_interactive_captcha_enabled()" in forex_branch
    assert "update_stooq_history_from_ui_csv" not in forex_branch
    assert "attempts = 2" not in forex_branch
    assert 'return "downloaded_csv"' in SCANNER_SOURCE
    assert 'return "table_ui"' in SCANNER_SOURCE
    assert '_print_forex_source_summary("search", members, data_source_by_ticker)' in SCANNER_SOURCE
    assert '_print_forex_source_summary("fibo", members, data_source_by_ticker)' in SCANNER_SOURCE
    assert '_forex_csv_health_check(members, data_source_by_ticker)' in SCANNER_SOURCE
    assert 'not in {"commodities", "forex"}' in SCANNER_SOURCE


def test_report_container_is_auto_removed_and_stale_runs_use_compose_label_cleanup():
    assert 'docker compose run --rm --no-deps' in STOCK_SOURCE
    assert 'trap _stockhelper_stop_tor EXIT' in STOCK_SOURCE
    assert 'docker compose up -d --no-deps tor' in STOCK_SOURCE
    assert 'docker compose stop tor' in STOCK_SOURCE
    assert 'label=com.docker.compose.service=stockhelper' in STOCK_SOURCE
    assert 'docker compose run --rm will delete this one-shot container' in RUN_SOURCE
