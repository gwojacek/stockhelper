from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "US100"

    capital: float = 243000
    entry: float = 19303
    stop_loss: float = 18713
    high: float = 22243
    low: float = 16481

    lot_cost: float = 72501.26
    pip_value: float = 75.19
    spread: float = 1.3 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
