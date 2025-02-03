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
    pip_size,
):
    """Calculate maximum lot size to stay within specified risk levels for SHORT trading."""
    results = {}

    for risk in risk_levels:
        max_loss = risk * initial_capital

        def calculate_loss_for_lots(lots):
            # Calculate pips between entry and stop loss
            pips = (stop_loss_price - entry_price) / pip_size
            loss_per_lot = pips * pip_value * lots
            spread_cost = spread * lots * 2  # Spread paid both entry and exit
            total_loss = loss_per_lot + spread_cost
            return total_loss

        max_lots = 0
        while True:
            max_lots += 0.01
            total_loss = calculate_loss_for_lots(max_lots)
            engaged_capital = max_lots * lot_price

            if total_loss > max_loss or engaged_capital > initial_capital:
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
    """Calculate the take profit selling level based on highest and lowest points for SHORT trading."""
    h = highest_point - lowest_point
    take_profit_price = entry_price - (2 / 3) * h
    return take_profit_price, h


def calculate_potential_profit(
    entry_price, take_profit_price, max_lots, pip_value, pip_size
):
    """Calculate potential profit for given parameters in terms of pips for SHORT trading."""
    pips_earned = (entry_price - take_profit_price) / pip_size
    potential_profit = pips_earned * pip_value * max_lots
    return potential_profit, pips_earned


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

    print(
        Fore.BLUE + f"Take Profit Price: {take_profit_price:.3f} PLN" + Style.RESET_ALL
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
    # Central parameter configuration
    pip_size = 0.01  # For JPY pairs (1 pip = 0.01), for other 0.0001

    initial_capital = 250000
    entry_price = 159.020
    stop_loss_price = 162.100
    lot_price = 14092.73
    pip_value = 26.63
    spread_multiplier = 1.5
    risk_levels = [0.005, 0.03, 0.025, 0.02, 0.015, 0.01]
    commodity_name = "EURJPY"
    highest_point = 166.680
    lowest_point = 157.980

    results = calculate_investment(
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        initial_capital=initial_capital,
        risk_levels=risk_levels,
        lot_price=lot_price,
        pip_value=pip_value,
        spread=spread_multiplier * pip_value,
        pip_size=pip_size,
    )

    take_profit_price, h = calculate_take_profit(
        entry_price=entry_price, highest_point=highest_point, lowest_point=lowest_point
    )

    # Calculate profit metrics
    profit = entry_price - take_profit_price
    risk = stop_loss_price - entry_price
    profit_risk_ratio = profit / risk if risk != 0 else 0

    # Calculate potential profit
    max_lots_05_risk = results[0.005]["max_lots"]
    potential_profit, _ = calculate_potential_profit(
        entry_price=entry_price,
        take_profit_price=take_profit_price,
        max_lots=max_lots_05_risk,
        pip_value=pip_value,
        pip_size=pip_size,
    )
    profit_percentage = (potential_profit / initial_capital) * 100

    # Display results
    display_results(
        results=results,
        profit_risk_ratio=profit_risk_ratio,
        take_profit_price=take_profit_price,
        potential_profit=potential_profit,
        profit_percentage=profit_percentage,
        initial_capital=initial_capital,
        commodity_name=commodity_name,
    )


if __name__ == "__main__":
    main()
