from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "USD/PLN"

    capital: float = 242000
    entry: float = 3.7669
    stop_loss: float = 3.7363
    high: float = 4.1235
    low: float = 3.69826

    lot_cost: float = 18824.25
    pip_value: float = 10
    pip_size: float = 0.0001
    spread: float = 13 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
