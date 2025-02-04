def calculate_position_size(
        entry: float,
        stop_loss: float,
        capital: float,
        risk_percent: float,
        pip_value: float,
        lot_cost: float,
        spread: float,
        pip_size: float = 1.0,
        position_type: str = "long",
        instrument_type: str = "commodity"
) -> dict:
    max_loss = capital * risk_percent
    lots = 0.0
    position_multiplier = 1 if position_type == "long" else -1

    while True:
        lots += 0.01
        price_diff = (stop_loss - entry) * position_multiplier
        pips = abs(price_diff / pip_size)
        spread_cost = spread * lots
        loss = round(pips * pip_value * lots, 2)
        total_loss = round(loss + spread_cost, 2)

        # If the loss or required capital exceed limits, step back one increment
        if total_loss > max_loss or lots * lot_cost > capital:
            lots -= 0.01  # Adjust the lot size back
            # Recalculate using the adjusted lots value
            spread_cost = spread * lots

            loss = round(pips * pip_value * lots, 2)
            total_loss = round(loss + spread_cost, 2)
            break

    return {
        "lots": round(lots, 2),
        "capital_used": round(lots * lot_cost, 2),
        "potential_loss": total_loss,
        "risk_percent": round((total_loss / capital) * 100, 2)
    }



def calculate_stock_position(
        entry: float,
        stop_loss: float,
        capital: float,
        risk_percent: float,
        max_capital: float
) -> dict:
    loss_per_share = entry - stop_loss
    max_loss = risk_percent * capital

    max_shares = [
        int(max_loss / loss_per_share) if loss_per_share > 0 else 0,
        int(capital / entry),
        int(max_capital / entry)
    ]

    shares = min(filter(lambda x: x >= 0, max_shares))

    return {
        "shares": shares,
        "capital_used": shares * entry,
        "potential_loss": shares * loss_per_share,
        "risk_percent": (shares * loss_per_share / capital) * 100
    }