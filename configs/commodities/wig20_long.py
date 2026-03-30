from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "WIG20"

    capital: float = 234000
    entry: float = 2832
    stop_loss: float = 2795
    high: float = 3022
    low: float = 2726

    lot_cost: float = 5724.8
    pip_value: float = 20
    spread: float = 1.8 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
