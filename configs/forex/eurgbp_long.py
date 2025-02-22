from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "EUR/GBP"

    capital: float = 250000
    entry: float = 0.8323
    stop_loss: float = 0.8289
    high: float = 0.8473
    low: float = 0.8222

    lot_cost: float = 13996.16
    pip_value: float = 50.50
    pip_size: float = 0.0001
    spread: float = 1.5 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
