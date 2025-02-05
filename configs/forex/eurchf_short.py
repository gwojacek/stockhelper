from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "short"
    pair: str = "EUR/CHF"

    capital: float = 250000
    entry: float = 0.9394
    stop_loss: float = 0.9469
    high: float = 0.9509
    low: float = 0.9256

    lot_cost: float = 14018.13
    pip_value: float = 44.80
    pip_size: float = 0.0001
    spread: float = 7.4 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
