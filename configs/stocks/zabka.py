from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Zabka"
    symbol: str = "ZAB.WA"
    instrument_type: str = "stock"
    capital: float = 243000
    entry: float = 21.65
    stop_loss: float = 20.54
    high: float = 24.99
    low: float = 19.64
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
