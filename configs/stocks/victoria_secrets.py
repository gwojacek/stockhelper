from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "victoria_secrets"
    # symbol: str = "JSW.WA"
    # instrument_type: str = "stock"
    capital: float = 248000
    entry: float = 29.28
    stop_loss: float = 27.03
    high: float = 48.73
    low: float = 15.12
    max_capital: float = 3000000  # 1% of 300M volume
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
