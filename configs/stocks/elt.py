from dataclasses import dataclass

filename = "elt"


@dataclass
class TradingConfig:
    name: str = "ELT.WA"
    symbol: str = "ELT.WA"
    market_data_source: str = "local_csv"
    instrument_type: str = "stock"
    capital: float = 255000
    entry: float = 59.72
    stop_loss: float = 56.47
    high: float = None
    low: float = None
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = None
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
