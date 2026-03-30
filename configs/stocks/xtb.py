from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "XTB"
    symbol: str = "XTB.WA"
    instrument_type: str = "stock"
    capital: float = 233000
    entry: float = 71.8
    stop_loss: float = 70.6
    high: float = 85.41
    low: float = 65.6
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
