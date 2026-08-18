from pathlib import Path


def test_report_launched_charts_are_strictly_cache_only():
    source = Path("utilities/report_server.py").read_text(encoding="utf-8")
    chart_env_start = source.index('env["STOCKHELPER_REPORT_LAUNCHED_CHART"] = "1"')
    process_start = source.index("proc = _start_process(argv, env, output_tail)", chart_env_start)
    chart_launch = source[chart_env_start:process_start]

    assert 'env["STOCKHELPER_CACHE_ONLY"] = "1"' in chart_launch
    assert 'env["STOCKHELPER_CHART_FAST_CACHE"] = "1"' in chart_launch
    assert "STOCKHELPER_REPORT_FETCH_IF_CACHE_MISSING" not in chart_launch


def test_cache_only_loader_never_falls_through_to_remote_download():
    source = Path("chart_program/chart_loader.py").read_text(encoding="utf-8")
    cached_return = source.index('"fallback_reason": "Cache-only mode enabled."')
    remote_download = source.index("_download_remote(", cached_return)
    between = source[cached_return:remote_download]

    assert 'raise ValueError(f"Cache-only mode: no local CSV data for {symbol}")' in between


def test_report_server_repairs_legacy_forex_and_etf_commands_before_launch():
    source = Path("utilities/report_server.py").read_text(encoding="utf-8")
    launch = source[source.index("def _run_chart_command"):source.index("env = os.environ.copy()", source.index("def _run_chart_command"))]

    assert '"--instrument" not in argv' in launch
    assert "detected_instrument = detect_instrument_type(argv[3])" in launch
    assert 'argv.extend(["--instrument", detected_instrument])' in launch
