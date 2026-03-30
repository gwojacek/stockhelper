from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "USD/CAD"

    capital: float = 232000
    entry: float = 1.3848
    stop_loss: float = 1.3773
    high: float = 1.4275
    low: float = 1.3724

    lot_cost: float = 12017.80
    pip_value: float = 26.07
    pip_size: float = 0.0001
    spread: float = 1.5 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
