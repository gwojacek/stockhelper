from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "ATT"
    symbol: str = "ATT.WA"
    instrument_type: str = "stock"
    capital: float = 241000
    entry: float = 16.7
    stop_loss: float = 16.0750
    high: float = 19.04
    low: float = 15.75
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
