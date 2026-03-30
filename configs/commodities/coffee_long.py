from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "COFFEE"

    capital: float = 242000
    entry: float = 285.3
    stop_loss: float = 271.54
    high: float = 372.5
    low: float = 277.5

    lot_cost: float = 206372.71
    pip_value: float = 7237.9
    spread: float = 0.35 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
