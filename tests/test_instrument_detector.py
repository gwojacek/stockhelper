import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "instrument_detector_under_test", Path("chart_program/instrument_detector.py")
)
assert spec and spec.loader
detector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detector)


def test_etf_cache_disambiguates_us_ticker_from_stock(tmp_path: Path):
    etf_dir = tmp_path / "etfs"
    etf_dir.mkdir()
    (etf_dir / "ITOT_US.csv").write_text("Date,Open,High,Low,Close\n", encoding="utf-8")

    assert detector.detect_from_symbol("ITOT.US") == "stock"
    assert detector.detect_from_cached_csv("ITOT.US", tmp_path) == "etf"


def test_etf_config_directory_is_detected():
    assert detector.detect_from_config_path(Path("configs/etfs/ITOT_US.py")) == "etf"
