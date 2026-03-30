from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Medicalgorithmics"
    symbol: str = "MDG.WA"
    instrument_type: str = "stock"
    capital: float = 237000
    entry: float = 32.4
    stop_loss: float = 30.45
    high: float = 42.8
    low: float = 24.55
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
