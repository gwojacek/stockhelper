from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "KGHM"
    symbol: str = "KGH.WA"
    instrument_type: str = "stock"
    capital: float = 230000
    entry: float = 137.40
    stop_loss: float = 132.125
    high: float = 166.89
    low: float = 115.04
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
