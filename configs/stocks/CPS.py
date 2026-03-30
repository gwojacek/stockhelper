from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "CPS"
    symbol: str = "CPS.WA"
    instrument_type: str = "stock"
    capital: float = 234000
    entry: float = 13.73
    stop_loss: float = 13.34
    high: float = 17.9
    low: float = 13.35
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
