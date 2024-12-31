from utils.color_coding import color_text
from tabulate import tabulate


def display_trade_info(initial_capital, entry_price, stop_loss_price, max_capital):
    """Display crucial trade information."""
    print(color_text("\n--- Trade Information ---", "blue"))
    print(color_text(f"Initial Capital: {initial_capital:.2f} zł", "magenta"))
    print(color_text(f"Entry Price: {entry_price:.2f} zł", "cyan"))
    print(color_text(f"Stop Loss Price: {stop_loss_price:.2f} zł", "cyan"))
    print(color_text(f"Maximum Capital Limit: {max_capital:.2f} zł", "cyan"))


def display_profit_risk_info(take_profit_price, profit_risk_ratio):
    """Display Take Profit Price and Profit/Risk Ratio."""
    print(color_text(f"Take Profit Price: {take_profit_price:.2f} zł", "cyan"))
    print(
        color_text(f"Profit/Risk Ratio (Profit/Risk): {profit_risk_ratio:.2f}", "cyan")
    )


def display_results_table(results, risk_levels):
    """Display the results in a table format."""
    print(color_text("\n--- Calculation Results ---", "green"))
    table_data = [
        [
            f"{risk * 100:.1f}%",
            data["max_shares_restricted"],
            f"{data['engaged_capital']:.2f} zł",
            f"{data['actual_loss']:.2f} zł",
            f"{data['actual_loss_percentage']:.2f}%",
        ]
        for risk, data in results.items()
    ]
    headers = [
        "Risk Level",
        "Max Shares",
        "Engaged Capital",
        "Actual Loss",
        "Actual % Loss",
    ]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))


def calculate_max_shares(entry_price, stop_loss_price, initial_capital, risk):
    """Calculate maximum shares to trade based on entry and stop-loss prices."""
    loss_per_share = entry_price - stop_loss_price
    max_loss = risk * initial_capital
    max_shares_based_on_loss = int(max_loss / loss_per_share)
    max_shares_based_on_capital = int(initial_capital / entry_price)

    max_shares_restricted = min(max_shares_based_on_loss, max_shares_based_on_capital)

    return max_shares_restricted, loss_per_share


def calculate_results(
    entry_price, stop_loss_price, initial_capital, max_capital, risk_levels
):
    """Calculate and return stock investment scenarios."""
    stock_results = {}
    for risk in risk_levels:
        max_shares_restricted, loss_per_share = calculate_max_shares(
            entry_price, stop_loss_price, initial_capital, risk
        )

        # Calculate engaged capital and actual loss
        engaged_capital = max_shares_restricted * entry_price
        actual_loss = max_shares_restricted * loss_per_share
        actual_loss_percentage = (actual_loss / initial_capital) * 100

        # Store results for the current risk level
        stock_results[risk] = {
            "max_shares_restricted": max_shares_restricted,
            "engaged_capital": engaged_capital,
            "actual_loss": actual_loss,
            "actual_loss_percentage": actual_loss_percentage,
            "exceeds_capital": engaged_capital > max_capital,
        }

    return stock_results


def calculate_take_profit(entry_price, highest_price, lowest_price):
    """Calculate the take profit price based on the highest and lowest points."""
    price_range = highest_price - lowest_price
    take_profit_price = entry_price + (2 / 3) * price_range
    return take_profit_price


def generate_adjusted_prices(entry_price, adjustment_range=0.02, step_percentage=0.001):
    """Generate a list of adjusted entry prices within a specified range."""
    start_price = entry_price * (1 - adjustment_range)
    end_price = entry_price * (1 + adjustment_range)
    adjusted_prices = [
        start_price + i * (step_percentage * entry_price)
        for i in range(
            int((end_price - start_price) / (step_percentage * entry_price)) + 1
        )
    ]
    return adjusted_prices


def calculate_results_for_adjusted_price(
    adjusted_price, stop_loss_price, initial_capital, max_capital, risk
):
    """Calculate results for a given adjusted price and return formatted data."""
    results = calculate_results(
        adjusted_price, stop_loss_price, initial_capital, max_capital, [risk]
    )
    data = results[risk]

    return [
        f"{adjusted_price:.2f} zł",
        data["max_shares_restricted"],
        f"{data['engaged_capital']:.2f} zł",
        f"{data['actual_loss']:.2f} zł",
        f"{data['actual_loss_percentage']:.2f}%",
    ]


def extended_calculation(
    entry_price, stop_loss_price, initial_capital, max_capital, risk_levels
):
    """Perform extended calculations for entry price adjustments."""
    print(color_text("\n--- Extended Calculation: Entry Price Adjustments ---", "cyan"))
    adjusted_prices = generate_adjusted_prices(entry_price)

    for risk in risk_levels:
        table_data = [
            calculate_results_for_adjusted_price(
                adjusted_price, stop_loss_price, initial_capital, max_capital, risk
            )
            for adjusted_price in adjusted_prices
        ]

        headers = [
            "Entry Price",
            "Max Shares",
            "Engaged Capital",
            "Actual Loss",
            "Actual % Loss",
        ]
        print(color_text(f"\n--- Risk Level: {risk * 100:.1f}% ---", "green"))
        print(tabulate(table_data, headers=headers, tablefmt="grid"))


def main():
    # Initialize constants for the calculations
    initial_capital = 207000
    entry_price = 11.32
    stop_loss_price = 10.99
    risk_levels = [0.005, 0.03, 0.025, 0.02, 0.015, 0.01]
    ten_session_trade_volume = 10000000
    max_capital = ten_session_trade_volume / 100
    highest_point = 12.5
    lowest_point = 10.0

    display_trade_info(initial_capital, entry_price, stop_loss_price, max_capital)

    results = calculate_results(
        entry_price, stop_loss_price, initial_capital, max_capital, risk_levels
    )

    take_profit_price = calculate_take_profit(entry_price, highest_point, lowest_point)

    # Calculate profit/risk metrics
    profit = take_profit_price - entry_price
    risk = entry_price - stop_loss_price
    profit_risk_ratio = profit / risk

    display_profit_risk_info(take_profit_price, profit_risk_ratio)
    display_results_table(results, risk_levels)

    # Warning for low profit/risk ratio
    if profit_risk_ratio <= 4:
        print(
            color_text(
                "\nWarning: Profit/Risk Ratio is less than or equal to 4. Consider revising your strategy.",
                "red",
            )
        )

    # Prompt for extended calculations
    choice = input(
        color_text(
            "\nDo you want to perform extended calculations with entry price adjustments? (yes/no): ",
            "blue",
        )
    )
    if choice.lower() == "yes":
        extended_calculation(
            entry_price, stop_loss_price, initial_capital, max_capital, risk_levels
        )
    else:
        print(color_text("Skipping extended calculations.", "red"))


if __name__ == "__main__":
    main()
