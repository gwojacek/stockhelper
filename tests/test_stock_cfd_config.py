from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_program.config_writer import write_or_update_config


def test_stock_cfd_config_uses_spread_without_explicit_pip_value(tmp_path):
    config_path = tmp_path / "boeing_long.py"
    write_or_update_config(
        "commodity",
        config_path,
        {
            "instrument_type": "commodity",
            "stock_cfd_mode": True,
            "name": "BA.US",
            "position_type": "long",
            "capital": 255000,
            "entry": 218.23,
            "stop_loss": 210.0,
            "high": 225.0,
            "low": 200.0,
            "lot_cost": 43.65,
            "spread": 0.76,
            "spread_pips": 76.0,
            "check_zr_value_fibo_or_elevation": 220.0,
            "line_cross_value": 222.0,
        },
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'instrument_type: str = "commodity"' in text
    assert "stock_cfd_mode: bool = True" in text
    assert "spread_pips: float = 76.0" in text
    assert "spread: float = 0.76" in text
    assert "pip_value" not in text
