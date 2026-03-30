from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "SPL"
    symbol: str = "SPL.WA"
    instrument_type: str = "stock"
    capital: float = 233000
    entry: float = 484
    stop_loss: float = 460
    high: float = 576.2
    low: float = 461.1
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
