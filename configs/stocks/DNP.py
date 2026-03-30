from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "DNP"
    symbol: str = "DNP.WA"
    instrument_type: str = "stock"
    capital: float = 241000
    entry: float = 41.3
    stop_loss: float = 40
    high: float = 52.85
    low: float = 37.12
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
