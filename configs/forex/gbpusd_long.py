from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "GBP/USD"

    capital: float = 251000
    entry: float = 1.24240
    stop_loss: float = 1.23090
    high: float = 1.34231
    low: float = 1.21003

    lot_cost: float = 16792.86
    pip_value: float = 40.67
    pip_size: float = 0.0001
    spread: float = 1.5 * 40.67  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)