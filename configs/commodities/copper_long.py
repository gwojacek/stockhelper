from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "Copper"

    capital: float = 250000
    entry: float = 444
    stop_loss: float = 422
    high: float = 519
    low: float = 400

    lot_cost: float = 112357.35
    pip_value: float = 112.13
    spread: float = 17 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
