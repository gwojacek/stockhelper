from utils.color_coding import color_text
from tabulate import tabulate

def calculate_stock(entry_price, stop_loss_price, initial_capital, max_capital, risk_levels):
    """Calculate maximum shares and detailed risk analysis."""
    loss_per_share = entry_price - stop_loss_price
    results = {}

    for risk in risk_levels:
        max_loss = risk * initial_capital
        max_shares_by_capital = int(max_capital / entry_price)
        max_shares_by_loss = int(max_loss / loss_per_share)
        max_shares_restricted = min(max_shares_by_capital, max_shares_by_loss)

        engaged_capital_restricted = max_shares_restricted * entry_price
        actual_loss = max_shares_restricted * loss_per_share
        actual_percentage_loss = (actual_loss / initial_capital) * 100

        results[risk] = {
            "max_shares_restricted": max_shares_restricted,
            "engaged_capital": engaged_capital_restricted,
            "actual_loss": actual_loss,
            "actual_percentage_loss": actual_percentage_loss,
            "exceeds_capital": engaged_capital_restricted > max_capital
        }

    return results

def calculate_take_profit(entry_price, highest_point, lowest_point):
    """Calculate the take profit price based on highest and lowest points."""
    h = highest_point - lowest_point
    take_profit_price = entry_price + (2 / 3) * h
    return take_profit_price, h

def extended_calculation(entry_price, stop_loss_price, initial_capital, max_capital, risk_levels):
    """Perform extended calculation for entry price adjustments."""
    step_percentage = 0.001  # The incremental step for adjusting entry price in extended calculations
    adjustment_range = 0.02  # The range (±2%) for entry price adjustments

    start_price = entry_price * (1 - adjustment_range)
    end_price = entry_price * (1 + adjustment_range)
    adjusted_prices = [start_price + i * (step_percentage * entry_price)
                       for i in range(int((end_price - start_price) / (step_percentage * entry_price)) + 1)]

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
                f"{data['actual_percentage_loss']:.2f}%"
            ])

        headers = ["Entry Price", "Max Shares", "Engaged Capital", "Actual Loss", "Actual % Loss"]
        print(color_text(f"\n--- Risk Level: {risk * 100:.1f}% ---", "green"))
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

def main():
    initial_capital = 207000  # The total capital available for investment
    entry_price = 11.32  # The price at which stocks are purchased
    stop_loss_price = 10.47  # The price at which stocks are sold to limit losses
    risk_levels = [0.005, 0.03]  # Risk levels: 0.5% and 3% of initial capital

    ten_session_trade_volume = 1000000  # The 10-session trade volume for the stock
    max_capital = ten_session_trade_volume / 100  # Maximum capital allowed for investment based on trade volume

    # Define highest and lowest points manually
    highest_point = 12.5  # Example value, replace with actual value
    lowest_point = 10.0   # Example value, replace with actual value

    print(color_text("\n--- Menu ---", "blue"))
    print(color_text(f"My capital for investment: {initial_capital}", "magenta"))
    print(color_text(f"Maximum capital limit due to 10 session trade: {max_capital:.2f} zł", "cyan"))

    results = calculate_stock(entry_price, stop_loss_price, initial_capital, max_capital, risk_levels)
    take_profit_price, h = calculate_take_profit(entry_price, highest_point, lowest_point)

    profit = take_profit_price - entry_price
    risk = entry_price - stop_loss_price
    profit_risk_ratio = profit / risk

    print(color_text("\n--- Calculation Results ---", "green"))
    risk_0_5_data = results[0.005]
    print(color_text(f"Risk 0.5% (Restricted by Max Capital):", "red"))
    print(color_text(f"  Maximum number of shares to purchase: {risk_0_5_data['max_shares_restricted']}", "green"))
    print(color_text(f"  Engaged capital: {risk_0_5_data['engaged_capital']:.2f} zł", "green"))
    print(color_text(f"  Actual loss at SL: {risk_0_5_data['actual_loss']:.2f} zł", "yellow"))
    print(color_text(f"  Actual percentage loss: {risk_0_5_data['actual_percentage_loss']:.2f}%", "yellow"))

    print(color_text(f"\nTake Profit Price: {take_profit_price:.2f} zł", "cyan"))
    print(color_text(f"Profit/Risk Ratio (Z/R): {profit_risk_ratio:.2f}", "cyan"))

    if profit_risk_ratio <= 4:
        print(color_text("\nWarning: The Profit/Risk Ratio (Z/R) is less than or equal to 4. Consider revising your strategy.", "red"))

    risk_3_data = results[0.03]
    print(color_text(f"\nRisk 3% (Restricted by Max Capital):", "red"))
    print(color_text(f"  Maximum number of shares to purchase: {risk_3_data['max_shares_restricted']}", "green"))
    print(color_text(f"  Engaged capital: {risk_3_data['engaged_capital']:.2f} zł", "green"))
    print(color_text(f"  Actual loss at SL: {risk_3_data['actual_loss']:.2f} zł", "yellow"))
    print(color_text(f"  Actual percentage loss: {risk_3_data['actual_percentage_loss']:.2f}%", "yellow"))

    choice = input(color_text("\nDo you want to perform extended calculation with entry price adjustments? (yes/no): ", "blue"))

    if choice.lower() == "yes":
        extended_calculation(entry_price, stop_loss_price, initial_capital, max_capital, risk_levels)
    else:
        print(color_text("Skipping extended calculation.", "red"))

if __name__ == "__main__":
    main()
