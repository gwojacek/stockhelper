from dataclasses import dataclass

filename = "blo"


@dataclass
class TradingConfig:
    name: str = "BLO.WA"
    symbol: str = "BLO.WA"
    market_data_source: str = "local_csv"
    instrument_type: str = "stock"
    capital: float = 255000
    entry: float = 26.14
    stop_loss: float = 25.86
    high: float = None
    low: float = None
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = None
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
