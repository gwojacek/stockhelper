from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "CCC"
    symbol: str = "CCC.WA"
    instrument_type: str = "stock"
    capital: float = 250000
    entry: float = 176.9
    stop_loss: float = 167.85
    high: float = 217
    low: float = 163.3
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
