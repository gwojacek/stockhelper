from dataclasses import dataclass

@dataclass
class OPLConfig:
    name: str = "OPL"
    capital: float = 250000
    entry: float = 7.398
    stop_loss: float = 7.20
    high: float = 8.666
    low: float = 7.040
    max_capital: float = 3000000  # 1% of 300M volume
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)