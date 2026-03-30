from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Vercom"
    symbol: str = "VRC.WA"
    instrument_type: str = "stock"
    capital: float = 239000
    entry: float = 123.04
    stop_loss: float = 119.55
    high: float = 127.6
    low: float = 102.35
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
