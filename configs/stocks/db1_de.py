from dataclasses import dataclass

filename = "db1_de"


@dataclass
class TradingConfig:
    name: str = "DB1.DE"
    symbol: str = "DB1.DE"
    market_data_source: str = "local_csv"
    instrument_type: str = "stock"
    apply_currency_conversion_fee: bool = True
    currency_conversion_fee_pct: float = 0.01
    capital: float = 255000
    entry: float = 243.22
    stop_loss: float = 249.27
    high: float = 269.6
    low: float = 236.9
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = 242.42
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
