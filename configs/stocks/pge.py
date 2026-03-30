from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "PGE"
    symbol: str = "PGE.WA"
    instrument_type: str = "stock"
    capital: float = 240000
    entry: float = 9.50
    stop_loss: float = 9.11
    high: float = 11.36
    low: float = 8.21
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
