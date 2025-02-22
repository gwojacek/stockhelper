from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "AMD"

    capital: float = 253000
    entry: float = 113.69
    stop_loss: float = 107.6
    high: float = 167.5
    low: float = 106.5

    lot_cost: float = 112357.35
    pip_value: float = 112.13
    spread: float = 17 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
