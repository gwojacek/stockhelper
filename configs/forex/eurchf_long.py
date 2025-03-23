from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "EUR/CHF"

    capital: float = 230000
    entry: float = 0.95450
    stop_loss: float = 0.94205
    high: float = 0.9581
    low: float = 0.9196

    lot_cost: float = 13894.26
    pip_value: float = 43.72
    pip_size: float = 0.0001
    spread: float = 1.4 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
