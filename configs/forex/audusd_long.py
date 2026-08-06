from dataclasses import dataclass



filename = "audusd_long"
@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "AUD/USD"

    capital: float = 400
    entry: float = 0.6368
    stop_loss: float = 0.6294
    high: float = 0.676
    low: float = 0.6087

    lot_cost: float = 12136.5
    pip_value: float = 38.47
    pip_size: float = 0.0001
    spread: float = 0
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = None
    spread_multiplier: float = 0
    apply_currency_conversion_fee: float = True
    currency_conversion_fee_pct: float = 0.01
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
