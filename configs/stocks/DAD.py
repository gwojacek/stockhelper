from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Dadelo"
    symbol: str = "DAD.WA"
    instrument_type: str = "stock"
    capital: float = 237000
    entry: float = 60.2
    stop_loss: float = 57.3
    high: float = 70.45
    low: float = 56.4
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
