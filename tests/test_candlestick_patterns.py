from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.modules.setdefault("pandas", types.SimpleNamespace(Series=dict, DataFrame=object))

chart_program = types.ModuleType("chart_program")
instrument_detector = types.ModuleType("chart_program.instrument_detector")
instrument_detector.detect_instrument_type = lambda ticker, default=None: default or "stock"
chart_loader = types.ModuleType("chart_program.chart_loader")
chart_loader.CSV_DATA_DIR = Path("data")
chart_loader.STATE_DATA_DIR = Path("data")
chart_loader.COMMODITY_STOOQ_MAP = {}
chart_loader.COMMODITY_YAHOO_MAP = {}
chart_loader.load_or_update_daily_data = lambda *args, **kwargs: None
chart_loader.has_new_remote_data = lambda *args, **kwargs: False
chart_loader.local_csv_path_for_symbol = lambda *args, **kwargs: Path("data/fake.csv")
chart_loader._yahoo_download = lambda *args, **kwargs: None
chart_loader._yahoo_download_window = lambda *args, **kwargs: None
yahoo_finance = types.ModuleType("utilities.yahoo_finance")
yahoo_finance.get_fx_to_pln_rate_yahoo = lambda *args, **kwargs: 1.0
output_silence = types.ModuleType("utilities.output_silence")
output_silence.call_silenced = lambda fn, *args, **kwargs: fn(*args, **kwargs)
sys.modules.setdefault("chart_program", chart_program)
sys.modules.setdefault("chart_program.instrument_detector", instrument_detector)
sys.modules.setdefault("chart_program.chart_loader", chart_loader)
sys.modules.setdefault("utilities.yahoo_finance", yahoo_finance)
sys.modules.setdefault("utilities.output_silence", output_silence)

from scanner_search import _is_bearish_shooting_star, _is_bullish_hammer


def candle(open_: float, high: float, low: float, close: float) -> dict[str, float]:
    return {"Open": open_, "High": high, "Low": low, "Close": close}


def test_bullish_hammer_requires_lower_shadow_at_least_twice_body_and_allows_upper_shadow_up_to_twice_body():
    assert _is_bullish_hammer(candle(10.0, 12.0, 6.0, 11.0))
    assert not _is_bullish_hammer(candle(10.0, 13.1, 6.0, 11.0))
    assert not _is_bullish_hammer(candle(10.0, 12.0, 8.1, 11.0))


def test_bullish_hammer_allows_doji_hammer_shape():
    assert _is_bullish_hammer(candle(10.0, 10.5, 8.0, 10.0))


def test_bearish_hammer_mirrors_shadow_rules_and_allows_doji_shape():
    assert _is_bearish_shooting_star(candle(10.0, 14.0, 8.0, 11.0))
    assert not _is_bearish_shooting_star(candle(10.0, 14.0, 7.9, 11.0))
    assert _is_bearish_shooting_star(candle(10.0, 12.0, 9.5, 10.0))
