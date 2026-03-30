from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "APR"
    symbol: str = "APR.WA"
    instrument_type: str = "stock"
    capital: float = 236000
    entry: float = 21.30
    stop_loss: float = 20.55
    high: float = 23.48
    low: float = 19.08
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
