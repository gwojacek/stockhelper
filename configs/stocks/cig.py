from dataclasses import dataclass

filename = "cig"
@dataclass
class TradingConfig:
    name: str = "CIG.WA"
    symbol: str = "CIG.WA"
    market_data_source: str = "local_csv"
    instrument_type: str = "stock"
    capital: float = 265000
    entry: float = 2.94
    stop_loss: float = 2.9
    high: float = 3.57
    low: float = 2.68
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = 2.93
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
