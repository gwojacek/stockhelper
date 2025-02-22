from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "GBP/CHF"

    capital: float = 251000
    entry: float = 1.1362
    stop_loss: float = 1.1244
    high: float = 1.1521
    low: float = 1.0744

    lot_cost: float = 16715.86
    pip_value: float = 43.89
    pip_size: float = 0.0001
    spread: float = 1.9 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
