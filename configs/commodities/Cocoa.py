from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "COCOA"

    capital: float = 236000
    entry: float = 8089
    stop_loss: float = 7380
    high: float = 10004
    low: float = 7309

    lot_cost: float = 29490
    pip_value: float = 36.20
    spread: float = 18 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
