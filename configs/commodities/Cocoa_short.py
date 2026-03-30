from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "short"
    name: str = "COCOA"

    capital: float = 235000
    entry: float = 5843
    stop_loss: float = 6220
    high: float = 9326
    low: float = 5890

    lot_cost: float = 21443.5
    pip_value: float = 36.70
    spread: float = 9 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
