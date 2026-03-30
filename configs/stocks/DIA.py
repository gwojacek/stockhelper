from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Diagnostyka"
    symbol: str = "DIA.WA"
    instrument_type: str = "stock"
    capital: float = 225000
    entry: float = 173.7
    stop_loss: float = 155
    high: float = 220
    low: float = 123.64
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
