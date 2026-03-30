from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "RBW"
    symbol: str = "RBW.WA"
    instrument_type: str = "stock"
    capital: float = 236000
    entry: float = 124.3
    stop_loss: float = 122
    high: float = 142.4
    low: float = 112.7
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
