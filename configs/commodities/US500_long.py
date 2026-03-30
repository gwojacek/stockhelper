from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "S&P500"

    capital: float = 245000
    entry: float = 5542
    stop_loss: float = 5434.5
    high: float = 6041.81
    low: float = 4837.71

    lot_cost: float = 52160.53
    pip_value: float = 187.45
    spread: float = 0.7 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
