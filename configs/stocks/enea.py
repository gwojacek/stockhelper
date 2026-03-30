from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Enea"
    symbol: str = "ENA.WA"
    instrument_type: str = "stock"
    capital: float = 234000
    entry: float = 20.84
    stop_loss: float = 19.65
    high: float = 23.46
    low: float = 18.68
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
