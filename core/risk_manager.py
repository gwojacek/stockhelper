def calculate_take_profit(
    entry: float,
    high: float,
    low: float,
    position_type: str,
    start_value: float | None = None,
) -> float:
    """Universal take profit calculation"""
    base_value = entry if start_value is None else start_value
    volatility = high - low
    if position_type == "long":
        return round(base_value + (2 / 3) * volatility, 4)
    return round(base_value - (2 / 3) * volatility, 4)


def calculate_distance_ratio(entry: float, stop_loss: float, check_value: float) -> float:
    """Distance ratio between entry->check_value and entry->stop_loss."""
    risk_distance = abs(entry - stop_loss)
    if risk_distance == 0:
        return 0
    return abs(check_value - entry) / risk_distance


def calculate_risk_reward(
    entry: float, stop_loss: float, take_profit: float, position_type: str
) -> float:
    """Risk-reward ratio calculator"""
    if position_type == "long":
        risk = entry - stop_loss
        reward = take_profit - entry
    else:
        risk = stop_loss - entry
        reward = entry - take_profit

    return round(reward / risk, 2) if risk != 0 else 0
