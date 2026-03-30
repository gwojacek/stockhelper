from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "EUR/JPY"

    capital: float = 243000
    entry: float = 162.94
    stop_loss: float = 162.079
    high: float = 164.179
    low: float = 158.092

    lot_cost: float = 14206.95
    pip_value: float = 26.29
    pip_size: float = 0.01
    spread: float = 1.6 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
