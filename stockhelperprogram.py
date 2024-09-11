from utils.color_coding import color_text


def calculate_stock():
    """Function to calculate the maximum number of shares and detailed risk."""
    print(color_text("\n--- Calculating Maximum Number of Shares ---", "blue"))

    # Initial available capital
    capital = 232000

    # Stock purchase and SL details
    entry_price = 155
    stop_loss_price = 145


    # Define risk levels as percentages
    risk_levels = [0.03, 0.005, 0.01, 0.02]  # 3%, 0.5%, 1%, 2%

    # Calculate the loss per share
    loss_per_share = entry_price - stop_loss_price
    print(color_text(f"Loss per share: {loss_per_share:.2f} zł\n", "magenta"))

    # Additional Information
    print(color_text(f"Total Available Capital: {capital} zł", "green"))
    print(color_text(f"Entry Price: {entry_price} zł", "green"))
    print(color_text(f"Stop Loss Price: {stop_loss_price} zł", "green"))
    print(color_text("Risk Levels:", "green"))
    for risk in risk_levels:
        max_loss = risk * capital
        print(color_text(f"  Risk {risk * 100:.1f}% allows a maximum loss of: {max_loss:.2f} zł", "yellow"))

    # Calculate dynamic risk based on the percentage difference between entry and SL
    dynamic_risk_percentage = (loss_per_share / entry_price) * 100
    dynamic_risk_decimal = dynamic_risk_percentage / 100

    print(color_text(f"\nDynamic risk level: {dynamic_risk_percentage:.2f}%\n", "cyan"))

    # Initialize data storage for results
    results = {}

    for risk in risk_levels:
        max_loss = risk * capital

        # Calculate maximum number of shares based on risk level
        max_shares = int(max_loss / loss_per_share)

        # Calculate engaged capital
        engaged_capital = max_shares * entry_price

        # Calculate actual loss
        actual_loss = max_shares * loss_per_share
        actual_percentage_loss = (actual_loss / capital) * 100

        # Store results
        results[risk] = {
            "max_shares": max_shares,
            "engaged_capital": engaged_capital,
            "actual_loss": actual_loss,
            "actual_percentage_loss": actual_percentage_loss,
            "exceeds_capital": engaged_capital > capital
        }

    # Calculate dynamic risk scenario
    dynamic_shares = int(capital / entry_price)
    dynamic_engaged_capital = dynamic_shares * entry_price
    dynamic_actual_loss = dynamic_shares * loss_per_share
    dynamic_actual_percentage_loss = (dynamic_actual_loss / capital) * 100

    results["dynamic"] = {
        "max_shares": dynamic_shares,
        "engaged_capital": dynamic_engaged_capital,
        "actual_loss": dynamic_actual_loss,
        "actual_percentage_loss": dynamic_actual_percentage_loss,
        "risk_type": "Dynamic",
        "exceeds_capital": False  # Dynamic risk won't exceed capital by definition
    }

    # Display results for dynamic risk
    print(color_text("\n--- Dynamic Risk Level (when diff buy/sl does not reach expected level of loss with available capital) ---", "cyan"))
    print(color_text(f"Dynamic risk level: {dynamic_risk_percentage:.2f}% for the current capital", "cyan"))
    print(color_text(f"  Maximum number of shares to purchase: {results['dynamic']['max_shares']}", "green"))
    print(color_text(f"  Engaged capital: {results['dynamic']['engaged_capital']:.2f} zł", "green"))
    print(color_text(f"  Actual loss at SL: {results['dynamic']['actual_loss']:.2f} zł", "yellow"))
    print(color_text(f"  Actual percentage loss: {results['dynamic']['actual_percentage_loss']:.2f}%", "yellow"))

    # Display results for standard risks within capital constraints
    print(color_text("\n--- Standard Risk Levels (within capital) ---", "green"))
    for risk, data in results.items():
        if risk != "dynamic" and not data["exceeds_capital"]:
            print(color_text(f"Risk {risk * 100:.1f}%:", "red"))
            print(color_text(f"  Maximum number of shares to purchase: {data['max_shares']}", "green"))
            print(color_text(f"  Engaged capital: {data['engaged_capital']:.2f} zł", "green"))
            print(color_text(f"  Actual loss at SL: {data['actual_loss']:.2f} zł", "yellow"))
            print(color_text(f"  Actual percentage loss: {data['actual_percentage_loss']:.2f}%", "yellow"))

    # Display risks that exceed capital
    print(color_text("\n--- These Risks Exceed Available Capital ---", "red"))
    for risk, data in results.items():
        if risk != "dynamic" and data["exceeds_capital"]:
            print(color_text(f"Risk {risk * 100:.1f}%:", "red"))
            print(color_text(f"  Maximum number of shares to purchase: {data['max_shares']}", "green"))
            print(color_text(f"  Engaged capital: {data['engaged_capital']:.2f} zł", "green"))
            print(color_text(f"  Actual loss at SL: {data['actual_loss']:.2f} zł", "yellow"))
            print(color_text(f"  Actual percentage loss: {data['actual_percentage_loss']:.2f}%", "yellow"))


def main():
    # Execute the calculation once
    print(color_text("\n--- Menu ---", "blue"))
    print(color_text("2. Calculate maximum number of shares to purchase", "magenta"))
    calculate_stock()


if __name__ == "__main__":
    main()
