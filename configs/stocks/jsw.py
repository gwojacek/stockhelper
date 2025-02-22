from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "jsw"
    capital: float = 253000
    entry: float = 26.1
    stop_loss: float = 24.27
    high: float = 25
    low: float = 19.84
    max_capital: float = 3000000  # 1% of 300M volume
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
