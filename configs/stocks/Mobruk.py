from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "MBR"
    symbol: str = "MBR.WA"
    instrument_type: str = "stock"
    capital: float = 235000
    entry: float = 296
    stop_loss: float = 288
    high: float = 320.9
    low: float = 244.8
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
