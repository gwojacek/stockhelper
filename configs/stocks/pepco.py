from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "PEPCO"
    capital: float = 250000
    entry: float = 16.57
    stop_loss: float = 15.35
    high: float = 25.81
    low: float = 14.44
    max_capital: float = 3000000  # 1% of 300M volume
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
