from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "CDR"
    symbol: str = "CDR.WA"
    instrument_type: str = "stock"
    capital: float = 225000
    entry: float = 243
    stop_loss: float = 234
    high: float = 260.7
    low: float = 234
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
