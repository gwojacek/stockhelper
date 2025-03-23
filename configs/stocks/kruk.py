from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Kruk"
    symbol: str = "KRU.WA"
    instrument_type: str = "stock"
    capital: float = 250000
    entry: float = 437
    stop_loss: float = 422.85
    high: float = 481
    low: float = 405.8
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
