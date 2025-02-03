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
    """Calculate maximum lot size to stay within specified risk levels for short position."""
    results = {}

    for risk in risk_levels:
        max_loss = risk * initial_capital

        def calculate_loss_for_lots(lots):
            adjusted_pip_value = pip_value * lots
            loss_per_lot = (
                stop_loss_price - entry_price
            ) * adjusted_pip_value  # Changed for short position
            spread_loss_entry = spread * lots
            spread_loss_exit = (spread * lots) * (
                stop_loss_price / entry_price
            )  # Spread cost at stop loss level
            total_loss = loss_per_lot + spread_loss_entry + spread_loss_exit
            return total_loss

        max_lots = 0
        total_loss = 0
        while True:
            max_lots += 0.01
            total_loss = calculate_loss_for_lots(max_lots)
            if total_loss > max_loss:
                max_lots -= 0.01
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
    """Calculate the take profit selling level based on highest and lowest points for short position."""
    h = highest_point - lowest_point
    take_profit_price = entry_price - (2 / 3) * h  # Changed for short position
    return take_profit_price, h


def display_take_profit_info(
    take_profit_price, profit_risk_ratio, potential_profit, profit_percentage
):
    """Display detailed take profit info with colors."""
    print(
        "\n" + Fore.BLUE + "--- Take Profit Information ---" + Style.RESET_ALL
    )  # Header in blue
    print(
        Fore.YELLOW + f"Take Profit Price:" + Style.RESET_ALL,
        f"{take_profit_price:.2f} PLN",
    )  # Yellow for Take Profit Price
    print(
        Fore.MAGENTA + f"Profit/Risk Ratio (Z/R):" + Style.RESET_ALL,
        f"{profit_risk_ratio:.2f}",
    )  # Magenta for Profit/Risk Ratio
    print(
        Fore.GREEN + f"Potential Profit:" + Style.RESET_ALL,
        f"{potential_profit:.2f} PLN",
    )  # Green for Potential Profit
    print(
        Fore.CYAN + f"Potential Profit as % of Initial Capital:" + Style.RESET_ALL,
        f"{profit_percentage:.2f}%",
    )  # Cyan for Profit Percentage


def main():
    initial_capital = 240000  # Capital available for investment
    entry_price = 532.86  # Entry price in PLN
    stop_loss_price = 540  # Stop loss price in PLN
    lot_price = 87937.83  # Price per lot in PLN
    pip_value = 1658.50  # Value of one pip in PLN
    spread = 1.05 * pip_value  # Spread cost for 1 lot in PLN (0.03 pip)
    risk_levels = [0.005, 0.03, 0.025, 0.02, 0.015, 0.01]

    # Define the commodity name
    commodity_name = "WHEAT"  # Replace with the actual commodity name

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

    profit = entry_price - take_profit_price  # Changed for short position
    risk = stop_loss_price - entry_price  # Changed for short position
    profit_risk_ratio = profit / risk

    # Display results
    print(
        "\n--- Calculation Results ---",
        Fore.LIGHTRED_EX + f"({commodity_name})" + Style.RESET_ALL,
    )  # Added commodity name to the header
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

    # Dedicated section for 0.5% risk level
    if 0.005 in results:
        data = results[0.005]
        potential_profit = profit * data["max_lots"] * pip_value
        potential_profit_percentage = (potential_profit / initial_capital) * 100
        display_take_profit_info(
            take_profit_price,
            profit_risk_ratio,
            potential_profit,
            potential_profit_percentage,
        )
    else:
        print("No results available for 0.5% risk level.")

    if profit_risk_ratio <= 4:
        print(
            "\n"
            + Fore.RED
            + "Warning: The Profit/Risk Ratio (Z/R) is less than or equal to 4. Consider revising your strategy."
            + Style.RESET_ALL
        )


if __name__ == "__main__":
    main()
