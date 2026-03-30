from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "Natural Gas"

    capital: float = 233000
    entry: float = 2.893
    stop_loss: float = 2.71
    high: float = 4.148
    low: float = 2.689

    lot_cost: float = 33048.80
    pip_value: float = 109325.5
    spread: float = 0.0005 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
