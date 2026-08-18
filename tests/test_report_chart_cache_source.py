from pathlib import Path


def test_report_launched_charts_use_cache_but_allow_missing_file_fallback():
    source = Path("utilities/report_server.py").read_text(encoding="utf-8")
    chart_env_start = source.index('env["STOCKHELPER_REPORT_LAUNCHED_CHART"] = "1"')
    process_start = source.index("proc = _start_process(argv, env, output_tail)", chart_env_start)
    chart_launch = source[chart_env_start:process_start]

    assert 'env["STOCKHELPER_CACHE_ONLY"] = "1"' in chart_launch
    assert 'env["STOCKHELPER_CHART_FAST_CACHE"] = "1"' in chart_launch
    assert 'env["STOCKHELPER_REPORT_FETCH_IF_CACHE_MISSING"] = "1"' in chart_launch


def test_cache_only_loader_falls_through_only_for_report_missing_cache():
    source = Path("chart_program/chart_loader.py").read_text(encoding="utf-8")
    cached_return = source.index('"fallback_reason": "Cache-only mode enabled."')
    remote_download = source.index("_download_remote(", cached_return)
    between = source[cached_return:remote_download]

    assert "report_missing_cache_fallback" in between
    assert 'os.environ.get("STOCKHELPER_REPORT_LAUNCHED_CHART") == "1"' in between
    assert 'os.environ.get("STOCKHELPER_REPORT_FETCH_IF_CACHE_MISSING") == "1"' in between
    assert 'os.environ.get("STOCKHELPER_SNAPSHOT_CACHE_ONLY") != "1"' in between
    assert 'os.environ.get("STOCKHELPER_USER_ONLYCACHE") != "1"' in between
    assert 'if cache_only and not report_missing_cache_fallback:' in between
    assert 'raise ValueError(f"Cache-only mode: no local CSV data for {symbol}")' in between
