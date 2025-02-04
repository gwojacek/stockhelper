from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "long"
    name: str = "Silver"

    capital: float = 240000
    entry: float = 31.077
    stop_loss: float = 30.04
    high: float = 32.945
    low: float = 28.78

    lot_cost: float = 62656
    pip_value: float = 20203
    spread: float = 0.4 * 20203 * 2
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
