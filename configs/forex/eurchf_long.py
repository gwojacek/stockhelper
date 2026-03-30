from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "EUR/CHF"

    capital: float = 233000
    entry: float = 0.93614
    stop_loss: float = 0.9318
    high: float = 0.9446
    low: float = 0.9267

    lot_cost: float = 14196.26
    pip_value: float = 45.54
    pip_size: float = 0.0001
    spread: float = 1.4 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
