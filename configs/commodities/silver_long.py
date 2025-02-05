from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "Silver"

    capital: float = 250000
    entry: float = 31.077
    stop_loss: float = 30.04
    high: float = 32.945
    low: float = 28.78

    lot_cost: float = 62645.36
    pip_value: float = 20157.5
    spread: float = 0.03 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
