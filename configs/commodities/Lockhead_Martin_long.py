from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "LMT.US"

    capital: float = 237000
    entry: float = 456.92
    stop_loss: float = 448.25
    high: float = 516.22
    low: float = 410.11

    lot_cost: float = 334.16
    pip_value: float = 0.0365
    spread: float = 143 * pip_value
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
