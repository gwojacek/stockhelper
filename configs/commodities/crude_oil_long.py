from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "Crude Oil"

    capital: float = 238000
    entry: float = 68.29
    stop_loss: float = 65.57
    high: float = 79.4
    low: float = 65.07

    lot_cost: float = 24511.82
    pip_value: float = 3591
    spread: float = 0.05 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
