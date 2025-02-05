from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "short"
    pair: str = "EUR/JPY"

    capital: float = 250000
    entry: float = 159.020
    stop_loss: float = 162.100
    high: float = 166.680
    low: float = 157.980

    lot_cost: float = 14092.73
    pip_value: float = 26.63
    pip_size: float = 0.01
    spread: float = 1.5 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
