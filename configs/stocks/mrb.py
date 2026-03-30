from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "MRB"
    symbol: str = "MRB.WA"
    instrument_type: str = "stock"
    capital: float = 225000
    entry: float = 14.2
    stop_loss: float = 13.69
    high: float = 15.25
    low: float = 13.34
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
