from dataclasses import dataclass


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "long"
    pair: str = "EUR/PLN"

    capital: float = 230000
    entry: float = 4.20000
    stop_loss: float = 4.1537
    high: float = 4.3752
    low: float = 4.1276

    lot_cost: float = 20999.00
    pip_value: float = 10
    pip_size: float = 0.0001
    spread: float = 29 * pip_value  # Spread per side
    risk_levels: tuple = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
