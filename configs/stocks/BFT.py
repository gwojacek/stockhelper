from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "BFT"
    symbol: str = "BFT.WA"
    instrument_type: str = "stock"
    capital: float = 233000
    entry: float = 3460
    stop_loss: float = 3265
    high: float = 4050
    low: float = 2980
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
