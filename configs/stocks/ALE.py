from dataclasses import dataclass


@dataclass
class TradingConfig:
    name: str = "Allegro"
    symbol: str = "ALE.WA"
    instrument_type: str = "stock"
    capital: float = 241000
    entry: float = 34.160
    stop_loss: float = 33.5200
    high: float = 38.570
    low: float = 32.610
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)