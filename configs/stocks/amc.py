from dataclasses import dataclass

filename = "amc"


@dataclass
class TradingConfig:
    name: str = "AMC.WA"
    symbol: str = "AMC.WA"
    market_data_source: str = "local_csv"
    instrument_type: str = "stock"
    capital: float = 255000
    entry: float = None
    stop_loss: float = 51.45
    high: float = 57
    low: float = 49.65
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = 52.51
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
