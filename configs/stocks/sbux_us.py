from dataclasses import dataclass

filename = "sbux_us"
@dataclass
class TradingConfig:
    name: str = "Sbux us"
    symbol: str = "SBUX.US"
    market_data_source: str = "local_csv"
    instrument_type: str = "stock"
    apply_currency_conversion_fee: bool = True
    currency_conversion_fee_pct: float = 0.01
    capital: float = 255000
    entry: float = 96.8
    stop_loss: float = 95.19
    high: float = None
    low: float = None
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = None
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
