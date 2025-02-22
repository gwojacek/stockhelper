from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "sugar"

    capital: float = 250000
    entry: float = 19.88
    stop_loss: float = 19.00
    high: float = 22.92
    low: float = 17.56

    lot_cost: float = 8884.11
    pip_value: float = 4457
    spread: float = 0.05 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
