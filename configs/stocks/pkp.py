from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "PKP"
    symbol: str = "PKP.WA"
    instrument_type: str = "stock"
    capital: float = 238000
    entry: float = 15.990
    stop_loss: float = 15.49
    high: float = 18.51
    low: float = 13.77
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
