from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Polimex Mostostal"
    symbol: str = "PXM.WA"
    instrument_type: str = "stock"
    capital: float = 233000
    entry: float = 7.7
    stop_loss: float = 7.06
    high: float = 9.86
    low: float = 5.51
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
