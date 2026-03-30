from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Bumech"
    symbol: str = "BMC.WA"
    instrument_type: str = "stock"
    capital: float = 241000
    entry: float = 21.78
    stop_loss: float = 20.44
    high: float = 31.76
    low: float = 12.62
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
