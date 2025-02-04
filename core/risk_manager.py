def calculate_take_profit(
    entry: float, high: float, low: float, position_type: str
) -> float:
    """Universal take profit calculation"""
    volatility = high - low
    if position_type == "long":
        return round(entry + (2 / 3) * volatility, 4)
    return round(entry - (2 / 3) * volatility, 4)


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
