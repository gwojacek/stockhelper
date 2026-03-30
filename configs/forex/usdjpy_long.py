from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "USD/JPY"

    capital: float = 233000
    entry: float = 148.78
    stop_loss: float = 147
    high: float = 150.915
    low: float = 145.756

    lot_cost: float = 12094.06
    pip_value: float = 24.4
    pip_size: float = 0.01
    spread: float = 1.3 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
