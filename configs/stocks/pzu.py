from dataclasses import dataclass

filename = "pzu"


@dataclass
class TradingConfig:
    name: str = "PZU"
    symbol: str = "PZU.WA"
    market_data_source: str = "local_csv"
    instrument_type: str = "stock"
    capital: float = 255000
    entry: float = None
    stop_loss: float = None
    high: float = 72.72
    low: float = 60.78
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = None
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
