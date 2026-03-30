from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "SNT"
    symbol: str = "SNT.WA"
    instrument_type: str = "stock"
    capital: float = 242000
    entry: float = 218.3
    stop_loss: float = 211.08
    high: float = 236.4
    low: float = 180.2
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
