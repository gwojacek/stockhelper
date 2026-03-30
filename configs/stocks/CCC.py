from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "CCC"
    symbol: str = "CCC.WA"
    instrument_type: str = "stock"
    capital: float = 226000
    entry: float = 120
    stop_loss: float = 114.6
    high: float = 192
    low: float = 110.4
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
