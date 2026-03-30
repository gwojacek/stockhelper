from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "KTY"
    symbol: str = "KTY.WA"
    instrument_type: str = "stock"
    capital: float = 229000
    entry: float = 760
    stop_loss: float = 720.61
    high: float = 882.82
    low: float = 665.31
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
