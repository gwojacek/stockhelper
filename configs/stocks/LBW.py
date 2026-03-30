from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "LBW"
    symbol: str = "LBW.WA"
    instrument_type: str = "stock"
    capital: float = 241000
    entry: float = 10.38
    stop_loss: float = 9.76
    high: float = 12.24
    low: float = 7.23
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
