from tabulate import tabulate
import pandas as pd


def calculate_investment(
    entry_price,
    stop_loss_price,
    initial_capital,
    risk_levels,
    lot_price,
    pip_value,
    spread,
):
    """Calculate maximum lot size to stay within specified risk levels."""
    results = {}

    for risk in risk_levels:
        max_loss = risk * initial_capital  # Maximum allowable loss at this risk level

        def calculate_loss_for_lots(lots):
            adjusted_pip_value = (
                pip_value * lots
            )  # Adjust pip value proportionally to lot size
            loss_per_lot = (entry_price - stop_loss_price) * adjusted_pip_value
            spread_loss_entry = spread * lots  # Spread cost at entry
            spread_loss_exit = (spread * lots) * (
                stop_loss_price / entry_price
            )  # Spread cost at stop loss level
            total_loss = loss_per_lot + spread_loss_entry + spread_loss_exit
            return total_loss

        max_lots = 0
        total_loss = 0
        while True:
            max_lots += 0.01  # Increment lots in steps of 0.01
            total_loss = calculate_loss_for_lots(max_lots)
            if total_loss > max_loss:
                max_lots -= 0.01  # Rollback to last valid lot size
                break

        engaged_capital = max_lots * lot_price
        actual_loss = calculate_loss_for_lots(max_lots)
        actual_percentage_loss = (actual_loss / initial_capital) * 100

        results[risk] = {
            "max_lots": max_lots,
            "engaged_capital": engaged_capital,
            "actual_loss": actual_loss,
            "actual_percentage_loss": actual_percentage_loss,
        }

    return results


def calculate_take_profit(entry_price, highest_point, lowest_point):
    """Calculate the take profit selling level based on highest and lowest points."""
    h = (
        highest_point - lowest_point
    )  # Calculate the distance between highest and lowest points
    take_profit_price = entry_price + (2 / 3) * h
    return take_profit_price, h


def main():
    initial_capital = 207000  # Capital available for investment
    entry_price = 554.75  # Entry price in PLN
    stop_loss_price = 539  # Stop loss price in PLN
    lot_price = 90211.18  # Price per lot in PLN
    pip_value = 1643.56  # Value of one pip in PLN
    spread = 1.05 * pip_value  # Spread cost for 1 lot in PLN (0.03 pip)
    risk_levels = [0.005, 0.03, 0.025, 0.02, 0.015, 0.01]

    # Define highest and lowest points manually
    highest_point = 617.25  # Example value, replace with actual value
    lowest_point = 520.75  # Example value, replace with actual value

    results = calculate_investment(
        entry_price,
        stop_loss_price,
        initial_capital,
        risk_levels,
        lot_price,
        pip_value,
        spread,
    )
    take_profit_price, h = calculate_take_profit(
        entry_price, highest_point, lowest_point
    )

    profit = take_profit_price - entry_price
    risk = entry_price - stop_loss_price
    profit_risk_ratio = profit / risk

    print("\n--- Calculation Results ---")
    table_data = []
    for risk, data in results.items():
        table_data.append(
            [
                f"{risk * 100:.1f}%",
                f"{data['max_lots']:.2f} Lots",
                f"{data['engaged_capital']:.2f} PLN",
                f"{data['actual_loss']:.2f} PLN",
                f"{data['actual_percentage_loss']:.2f}%",
            ]
        )

    headers = [
        "Risk Level",
        "Max Lots",
        "Engaged Capital",
        "Actual Loss",
        "Actual % Loss",
    ]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

    print(f"\nTake Profit Price: {take_profit_price:.2f} PLN")
    print(f"Profit/Risk Ratio (Z/R): {profit_risk_ratio:.2f}")

    if profit_risk_ratio <= 4:
        print(
            "\nWarning: The Profit/Risk Ratio (Z/R) is less than or equal to 4. Consider revising your strategy."
        )


if __name__ == "__main__":
    main()
