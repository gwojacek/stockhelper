from dataclasses import dataclass

filename = "eat"


@dataclass
class TradingConfig:
    name: str = "EAT"
    symbol: str = "EAT.WA"
    market_data_source: str = "local_csv"
    instrument_type: str = "stock"
    capital: float = 255000
    entry: float = 10.4
    stop_loss: float = 10.2
    high: float = 12.44
    low: float = 9.7
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = 10.38
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
