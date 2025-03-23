from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "AUD/USD"

    capital: float = 230000
    entry: float = 0.6368
    stop_loss: float = 0.6294
    high: float = 0.6760
    low: float = 0.6087

    lot_cost: float = 12136.50
    pip_value: float = 38.47
    pip_size: float = 0.0001
    spread: float = 1.2 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
