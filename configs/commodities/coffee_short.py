from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "short"
    name: str = "COFFEE"

    capital: float = 228000
    entry: float = 366.57
    stop_loss: float = 386.2
    high: float = 440.85
    low: float = 359.20

    lot_cost: float = 286309.31
    pip_value: float = 7807.3
    spread: float = 0.3 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
