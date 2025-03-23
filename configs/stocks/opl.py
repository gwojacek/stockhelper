from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "OPL"
    symbol: str = "OPL.WA"
    instrument_type: str = "stock"
    capital: float = 250000
    entry: float = 7.398
    stop_loss: float = 7.20
    high: float = 8.666
    low: float = 7.040
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
