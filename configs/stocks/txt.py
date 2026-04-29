from dataclasses import dataclass

filename = "txt"


@dataclass
class TradingConfig:
    name: str = "Txt"
    symbol: str = "TXT.WA"
    instrument_type: str = "stock"
    apply_currency_conversion_fee: bool = False
    currency_conversion_fee_pct: float = 0.01
    capital: float = 255000
    entry: float = 39.38
    stop_loss: float = 38.03
    high: float = 56.74
    low: float = 35.5
    check_zr_value_fibo_or_elevation: float = 52
    line_cross_value: float = None
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
