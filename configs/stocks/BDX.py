from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "BDX"
    symbol: str = "BDX.WA"
    instrument_type: str = "stock"
    capital: float = 233000
    entry: float = 644
    stop_loss: float = 602
    high: float = 814
    low: float = 500
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
