from dataclasses import dataclass

filename = "db1_de_long"


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    stock_cfd_mode: bool = True
    spread_pips: float = 424.0
    position_type: str = "long"
    name: str = "DB1.DE"

    capital: float = 265000

    entry: float = 243.22
    stop_loss: float = 249.27
    high: float = 269.6
    low: float = 236.9

    lot_cost: float = 206.39
    spread: float = 4.24
    check_zr_value_fibo_or_elevation: float = None
    line_cross_value: float = 242.42
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
