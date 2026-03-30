from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "SMCI"

    capital: float = 244000
    entry: float = 38
    stop_loss: float = 32.82
    high: float = 44.99
    low: float = 25.71

    lot_cost: float = 43.52
    pip_value: float = 0.038
    spread: float = 14 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
