from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Lockheed Martin"
    symbol: str = "LMT.US"
    instrument_type: str = "stock"
    capital: float = 236000
    entry: float = 456.92
    stop_loss: float = 448.25
    high: float = 516.22
    low: float = 410.11
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
