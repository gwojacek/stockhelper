from tabulate import tabulate
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


def calculate_investment(
    entry_price,
    stop_loss_price,
    initial_capital,
    risk_levels,
    lot_price,
    pip_value,
    spread,
):
    """Calculate maximum lot size to stay within specified risk levels for SHORT trading."""
    results = {}

    for risk in risk_levels:
        max_loss = risk * initial_capital  # Maximum allowable loss at this risk level

        def calculate_loss_for_lots(lots):
            adjusted_pip_value = (
                pip_value * lots
            )  # Adjust pip value proportionally to lot size
            loss_per_lot = (
                stop_loss_price - entry_price
            ) * adjusted_pip_value  # Loss per lot if the price goes against
            spread_loss_entry = spread * lots  # Spread cost at entry
            spread_loss_exit = (spread * lots) * (
                entry_price / stop_loss_price
            )  # Spread cost if closing at stop loss level
            total_loss = loss_per_lot + spread_loss_entry + spread_loss_exit
            return total_loss

        max_lots = 0
        while True:
            max_lots += 0.01  # Increment lots in steps of 0.01
            total_loss = calculate_loss_for_lots(max_lots)
            if total_loss > max_loss:
                max_lots -= 0.01  # Rollback to the last valid lot size
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
    """Calculate the take profit selling level based on highest and lowest points for SHORT trading."""
    h = highest_point - lowest_point  # Distance between the highest and lowest points
    take_profit_price = (
        entry_price - (2 / 3) * h
    )  # Take profit price for SHORT: lower than entry
    return take_profit_price, h


def calculate_potential_profit(entry_price, take_profit_price, max_lots, pip_value):
    """Calculate potential profit for given parameters in terms of pips for SHORT trading."""
    price_movement = (
        entry_price - take_profit_price
    ) / 0.0001  # Assuming a pip is 0.0001
    return (
        max_lots * price_movement * pip_value,
        price_movement,
    )  # Return both potential profit and price movement in pips


def display_results(
    results,
    profit_risk_ratio,
    take_profit_price,
    potential_profit,
    profit_percentage,
    initial_capital,
    commodity_name,
):
    """Display results in a formatted table with colors."""
    print(
        "\n"
        + Fore.LIGHTRED_EX
        + f"--- Calculation Results --- {commodity_name} ---"
        + Style.RESET_ALL
    )

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

    # Display take profit and potential profit information
    print(
        Fore.BLUE + f"Take Profit Price: {take_profit_price:.4f} PLN" + Style.RESET_ALL
    )
    print(
        Fore.MAGENTA
        + f"Profit/Risk Ratio (Z/R): {profit_risk_ratio:.2f}"
        + Style.RESET_ALL
    )
    print(
        Fore.GREEN + f"Potential Profit: {potential_profit:.2f} PLN" + Style.RESET_ALL
    )
    print(
        Fore.CYAN
        + f"Potential Profit as % of Initial Capital: {profit_percentage:.2f}%"
        + Style.RESET_ALL
    )

    if profit_risk_ratio <= 4:
        print(
            "\n"
            + Fore.RED
            + "Warning: The Profit/Risk Ratio (Z/R) is less than or equal to 4. Consider revising your strategy."
            + Style.RESET_ALL
        )


def main():
    initial_capital = 207000  # Capital available for investment
    entry_price = 1.2000  # Entry price in PLN
    stop_loss_price = 1.2050  # Stop loss price in PLN (above the entry price)
    lot_price = 20247.75  # Price per lot in PLN
    pip_value = 10  # Value of one pip in PLN for a standard lot
    spread = 35 * pip_value  # Spread cost for 1 lot in PLN
    risk_levels = [0.005, 0.03, 0.025, 0.02, 0.015, 0.01]

    commodity_name = "Example Forex Pair (Short)"  # Change as necessary
    highest_point = 1.2500  # Example value, replace with actual value
    lowest_point = 1.1500  # Example value, replace with actual value

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

    profit = entry_price - take_profit_price  # Profit calculation for SHORT
    risk = stop_loss_price - entry_price  # Risk calculation for SHORT
    profit_risk_ratio = profit / risk if risk != 0 else 0  # Prevent division by zero

    # Calculate potential profit for the maximum lots at the lowest risk level
    max_lots_05_risk = results[0.005]["max_lots"]
    potential_profit, _ = calculate_potential_profit(
        entry_price, take_profit_price, max_lots_05_risk, pip_value
    )
    profit_percentage = (potential_profit / initial_capital) * 100

    # Display results
    display_results(
        results,
        profit_risk_ratio,
        take_profit_price,
        potential_profit,
        profit_percentage,
        initial_capital,
        commodity_name,
    )


if __name__ == "__main__":
    main()
