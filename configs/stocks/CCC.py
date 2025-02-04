from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "CCC"
    capital: float = 250000
    entry: float = 175
    stop_loss: float = 167.85
    high: float = 217
    low: float = 163.3
    max_capital: float = 3000000  # 1% of 300M volume
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
