from dataclasses import dataclass

filename = "ena"


@dataclass
class TradingConfig:
    name: str = "Enea"
    symbol: str = "ENA.WA"
    instrument_type: str = "stock"
    apply_currency_conversion_fee: bool = False
    currency_conversion_fee_pct: float = 0.01
    capital: float = 255000
    entry: float = 22.82
    stop_loss: float = 21.75
    high: float = 27
    low: float = 20.1
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = 22.36
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
