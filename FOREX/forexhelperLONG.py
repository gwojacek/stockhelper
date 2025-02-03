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
    """Calculate maximum lot size to stay within specified risk levels for LONG trading."""
    results = {}

    for risk in risk_levels:
        max_loss = risk * initial_capital

        def calculate_loss_for_lots(lots):
            # Calculate pips between entry and stop loss
            pips = (entry_price - stop_loss_price) / pip_size
            loss_per_lot = abs(pips) * pip_value * lots
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
    """Calculate take profit level using 2/3 volatility rule for LONG positions."""
    h = highest_point - lowest_point
    return entry_price + (2 / 3) * h, h


def calculate_potential_profit(
    entry_price, take_profit_price, max_lots, pip_value, pip_size
):
    """Calculate profit potential in both currency and pips."""
    pips_earned = (take_profit_price - entry_price) / pip_size
    return pips_earned * pip_value * max_lots, pips_earned


def display_results(
    results,
    profit_risk_ratio,
    take_profit_price,
    potential_profit,
    profit_percentage,
    pips_earned,
    pip_size,
    commodity_name,
):
    """Display formatted results with pip size context."""
    pip_decimal_places = (
        4 if pip_size == 0.0001 else 2
    )  # Adjust display based on pip size

    print(
        f"\n{Fore.LIGHTRED_EX}--- Calculation Results ({commodity_name}) ---{Style.RESET_ALL}"
    )

    # Results table
    table_data = [
        [
            f"{risk * 100:.1f}%",
            f"{data['max_lots']:.2f}",
            f"{data['engaged_capital']:.2f} PLN",
            f"{data['actual_loss']:.2f} PLN",
            f"{data['actual_percentage_loss']:.2f}%",
        ]
        for risk, data in results.items()
    ]

    print(
        tabulate(
            table_data,
            headers=["Risk", "Lots", "Capital", "Loss", "Loss%"],
            tablefmt="grid",
        )
    )

    # Take profit info
    print(
        f"\n{Fore.BLUE}Take Profit: {take_profit_price:.{pip_decimal_places}f}{Style.RESET_ALL}"
    )
    print(
        f"{Fore.MAGENTA}Profit/Risk Ratio: {profit_risk_ratio:.2f}:1{Style.RESET_ALL}"
    )
    print(
        f"{Fore.GREEN}Potential Profit: {potential_profit:.2f} PLN ({pips_earned:.1f} pips){Style.RESET_ALL}"
    )
    print(
        f"{Fore.CYAN}Profit Potential: {profit_percentage:.2f}% of capital{Style.RESET_ALL}"
    )

    if profit_risk_ratio < 3:
        print(
            f"\n{Fore.RED}Warning: Risk/Reward ratio below 3:1 - Consider better trade setup{Style.RESET_ALL}"
        )


def main():
    # Instrument configuration guide:
    # - JPY pairs (USD/JPY): pip_size = 0.01 (2 decimal places display)
    # - Standard FX (EUR/USD): pip_size = 0.0001 (4 decimal places)
    # - Gold (XAU/USD): pip_size = 0.10 (2 decimal places)

    # Configuration for GBP/USD
    pip_size = 0.0001  # Standard forex pair
    pip_value = 40.67  # Value per pip in account currency
    spread_multiplier = 1.5  # Broker spread cost

    # Trading parameters
    initial_capital = 251000
    entry_price = 1.24240
    stop_loss_price = 1.23090
    lot_price = 16792.86  # Margin requirement per lot
    risk_levels = [0.005, 0.03, 0.025, 0.02, 0.015, 0.01]
    commodity_name = "GBP/USD Long"
    market_data = {"highest": 1.34231, "lowest": 1.21003}

    # Execute calculations
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

    take_profit_price, volatility = calculate_take_profit(
        entry_price=entry_price,
        highest_point=market_data["highest"],
        lowest_point=market_data["lowest"],
    )

    # Risk calculations
    risk_amount = entry_price - stop_loss_price
    reward_amount = take_profit_price - entry_price
    profit_risk_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

    # Profit potential
    max_lots = results[0.005]["max_lots"]
    potential_profit, pips_earned = calculate_potential_profit(
        entry_price=entry_price,
        take_profit_price=take_profit_price,
        max_lots=max_lots,
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
        pips_earned=pips_earned,
        pip_size=pip_size,
        commodity_name=commodity_name,
    )


if __name__ == "__main__":
    main()
