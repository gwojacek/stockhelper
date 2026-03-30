from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Orlen"
    symbol: str = "PKN.WA"
    instrument_type: str = "stock"
    capital: float = 241000
    entry: float = 103.12
    stop_loss: float = 97.76
    high: float = 105.3
    low: float = 84.4
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
