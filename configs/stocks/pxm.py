from dataclasses import dataclass



filename = "pxm"
@dataclass
class TradingConfig:
    name: str = "Pxm"
    symbol: str = "PXM.WA"
    instrument_type: str = "stock"
    capital: float = 233000
    entry: float = 7.7
    stop_loss: float = 7.06
    high: float = 9.86
    low: float = 5.51
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = 7.38
    market_data_source: float = "local_csv"
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
