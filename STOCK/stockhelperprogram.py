from utils.color_coding import color_text
from tabulate import tabulate


def calculate_stock(entry_price, stop_loss_price, initial_capital, max_capital, risk_levels):
    """Calculate maximum shares and detailed risk analysis."""
    loss_per_share = entry_price - stop_loss_price  # Loss per share
    stock_results = {}

    for risk in risk_levels:
        # Calculate maximum allowable loss based on risk level
        max_loss = risk * initial_capital

        # Calculate maximum shares based on loss and available capital
        max_shares_based_on_loss = int(max_loss / loss_per_share)
        max_shares_based_on_capital = int(initial_capital / entry_price)

        # Determine the restricted maximum shares
        max_shares_restricted = min(max_shares_based_on_loss, max_shares_based_on_capital)

        # Calculate engaged capital and actual loss
        engaged_capital = max_shares_restricted * entry_price
        actual_loss = max_shares_restricted * loss_per_share
        actual_loss_percentage = (actual_loss / initial_capital) * 100

        # Increment shares while respecting maximum loss and capital constraints
        while (max_shares_restricted + 1) * loss_per_share <= max_loss and (
                (max_shares_restricted + 1) * entry_price <= initial_capital):
            max_shares_restricted += 1
            engaged_capital = max_shares_restricted * entry_price
            actual_loss = max_shares_restricted * loss_per_share
            actual_loss_percentage = (actual_loss / initial_capital) * 100

        # Store results for the current risk level
        stock_results[risk] = {
            "max_shares_restricted": max_shares_restricted,
            "engaged_capital": engaged_capital,
            "actual_loss": actual_loss,
            "actual_loss_percentage": actual_loss_percentage,
            "exceeds_capital": engaged_capital > max_capital
        }

    return stock_results


def calculate_take_profit(entry_price, highest_price, lowest_price):
    """Calculate the take profit price based on the highest and lowest points."""
    price_range = highest_price - lowest_price
    take_profit_price = entry_price + (2 / 3) * price_range
    return take_profit_price, price_range


def extended_calculation(entry_price, stop_loss_price, initial_capital, max_capital, risk_levels):
    """Perform extended calculations for entry price adjustments."""
    step_percentage = 0.001  # Increment for adjusting entry price
    adjustment_range = 0.02  # Range for entry price adjustments (±2%)

    # Calculate adjusted entry prices
    start_price = entry_price * (1 - adjustment_range)
    end_price = entry_price * (1 + adjustment_range)
    adjusted_prices = [
        start_price + i * (step_percentage * entry_price)
        for i in range(int((end_price - start_price) / (step_percentage * entry_price)) + 1)
    ]

    print(color_text("\n--- Extended Calculation: Entry Price Adjustments ---", "cyan"))
    print(color_text(f"Evaluating entry prices from {start_price:.2f} zł to {end_price:.2f} zł", "cyan"))

    for risk in risk_levels:
        table_data = []
        for adjusted_price in adjusted_prices:
            results = calculate_stock(adjusted_price, stop_loss_price, initial_capital, max_capital, [risk])
            data = results[risk]
            table_data.append([
                f"{adjusted_price:.2f} zł",
                data['max_shares_restricted'],
                f"{data['engaged_capital']:.2f} zł",
                f"{data['actual_loss']:.2f} zł",
                f"{data['actual_loss_percentage']:.2f}%"
            ])

        headers = ["Entry Price", "Max Shares", "Engaged Capital", "Actual Loss", "Actual % Loss"]
        print(color_text(f"\n--- Risk Level: {risk * 100:.1f}% ---", "green"))
        print(tabulate(table_data, headers=headers, tablefmt="grid"))


def main():
    # Initialize constants for the calculations
    initial_capital = 207000  # Total capital available for investment
    entry_price = 11.32  # The price at which stocks are purchased
    stop_loss_price = 10.99  # The price at which stocks are sold to limit losses
    risk_levels = [0.005, 0.03, 0.025, 0.02, 0.015, 0.01]  # Different risk levels as a fraction of initial capital

    # Define the maximum capital limit based on 10-session trade volume
    ten_session_trade_volume = 10000000  # Example trade volume for the stock
    max_capital = ten_session_trade_volume / 100  # Maximum capital allowed for investment

    # Define highest and lowest points for the price
    highest_point = 12.5  # Example highest price, replace with actual value
    lowest_point = 10.0  # Example lowest price, replace with actual value

    # Calculate the maximum shares we can engage based on the initial capital and entry price
    max_shares_based_on_capital = int(initial_capital / entry_price)
    maximum_engaged_capital = max_shares_based_on_capital * entry_price

    # Calculate the difference between max_capital and maximum_engaged_capital
    capital_difference = max_capital - maximum_engaged_capital

    # Display crucial trade information
    print(color_text("\n--- Trade Information ---", "blue"))
    print(color_text(f"Initial Capital: {initial_capital:.2f} zł", "magenta"))
    print(color_text(f"Entry Price: {entry_price:.2f} zł", "cyan"))
    print(color_text(f"Stop Loss Price: {stop_loss_price:.2f} zł", "cyan"))
    print(color_text(f"Maximum Capital Limit (based on 10-session trade volume): {max_capital:.2f} zł", "cyan"))
    print(color_text(f"Risk Levels: {', '.join([f'{risk * 100:.1f}%' for risk in risk_levels])}", "cyan"))

    # Calculate stock investment scenarios
    results = calculate_stock(entry_price, stop_loss_price, initial_capital, max_capital, risk_levels)
    take_profit_price, price_range = calculate_take_profit(entry_price, highest_point, lowest_point)

    # Calculate profit/risk metrics
    profit = take_profit_price - entry_price
    risk = entry_price - stop_loss_price
    profit_risk_ratio = profit / risk

    # Display calculation results
    print(color_text("\n--- Calculation Results ---", "green"))
    for risk in risk_levels:
        risk_data = results[risk]
        print(color_text(f"Risk Level {risk * 100:.1f}% (Restricted by Max Capital):", "red"))
        print(color_text(f"  Maximum number of shares to purchase: {risk_data['max_shares_restricted']}", "green"))
        print(color_text(f"  Engaged capital: {risk_data['engaged_capital']:.2f} zł", "green"))
        print(color_text(f"  Actual loss at stop loss: {risk_data['actual_loss']:.2f} zł", "yellow"))
        print(color_text(f"  Actual percentage loss: {risk_data['actual_loss_percentage']:.2f}%", "yellow"))

    print(color_text(f"\nTake Profit Price: {take_profit_price:.2f} zł", "cyan"))
    print(color_text(f"Profit/Risk Ratio (Profit/Risk): {profit_risk_ratio:.2f}", "cyan"))

    # Warning for low profit/risk ratio
    if profit_risk_ratio <= 4:
        print(color_text(
            "\nWarning: The Profit/Risk Ratio (Profit/Risk) is less than or equal to 4. Consider revising your strategy.",
            "red"))

    # Ask the user if they want to perform extended calculations
    choice = input(color_text("\nDo you want to perform extended calculations with entry price adjustments? (yes/no): ", "blue"))

    if choice.lower() == "yes":
        extended_calculation(entry_price, stop_loss_price, initial_capital, max_capital, risk_levels)
    else:
        print(color_text("Skipping extended calculations.", "red"))


if __name__ == "__main__":
    main()