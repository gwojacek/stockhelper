from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "algt_us"
    # symbol: str = "JSW.WA"
    # instrument_type: str = "stock"
    capital: float = 230000
    entry: float = 65.00
    stop_loss: float = 61.42
    high: float = 107.57
    low: float = 62.1
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
