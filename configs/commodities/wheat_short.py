from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "short"
    name: str = "WHEAT"

    capital: float = 240000
    entry: float = 532.86
    stop_loss: float = 540.00
    high: float = 617.25
    low: float = 520.75

    lot_cost: float = 87937.83
    pip_value: float = 1658.50
    spread: float = 1.05 * 1658.50 * 2  # Spread for both entry+exit
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)