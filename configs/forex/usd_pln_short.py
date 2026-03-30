from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "short"
    pair: str = "USD/PLN"

    capital: float = 238000
    entry: float = 3.6360
    stop_loss: float = 3.68955
    high: float = 4.1235
    low: float = 3.67043

    lot_cost: float = 18186.75
    pip_value: float = 10
    pip_size: float = 0.0001
    spread: float = 13 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
