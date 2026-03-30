from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "PEO"
    symbol: str = "PEO.WA"
    instrument_type: str = "stock"
    capital: float = 234000
    entry: float = 177
    stop_loss: float = 172.4
    high: float = 201
    low: float = 170.6
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
