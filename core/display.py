from tabulate import tabulate
from colorama import Fore, Style, init

init(autoreset=True)


class DisplayHandler:
    def __init__(self, config):
        self.config = config
        self.pip_decimals = self._get_pip_decimals()

    def _get_pip_decimals(self):
        if hasattr(self.config, "pip_size"):
            if getattr(self.config, "instrument_type", "") == "forex":
                return 3
            return 4 if self.config.pip_size < 0.001 else 2
        return 2

    def show_header(self, title):
        print(f"\n{Fore.CYAN}=== {title.upper()} ==={Style.RESET_ALL}")

    def show_results(self, results):
        headers = [
            "Risk Level",
            "Position Size",
            "Engaged Capital",
            "Potential Loss With Spread",
            "Loss %",
        ]

        table_data = []
        for risk, data in sorted(results.items(), key=lambda item: item[0], reverse=True):
            position_value = data.get("lots", data.get("shares", 0))
            if "lots" in data:
                lot_decimals = 3 if getattr(self.config, "instrument_type", "") in {"commodity", "forex"} else 2
            else:
                lot_decimals = 0
            row = [
                # Risk Level (no color)
                f"{risk * 100:.1f}%",
                # Position Size (yellow value only)
                f"{Fore.YELLOW}{position_value:.{lot_decimals}f}{Style.RESET_ALL} {'Lots' if 'lots' in data else 'Shares'}",
                # Engaged Capital (magenta value only)
                f"{Fore.MAGENTA}{data['capital_used']:,.2f}{Style.RESET_ALL} {self._get_currency()}",
                # Potential Loss (red value only)
                f"{Fore.RED}{data['potential_loss']:,.2f}{Style.RESET_ALL} {self._get_currency()}",
                # Loss % (light red value only)
                f"{Fore.LIGHTRED_EX}{data['risk_percent']:.2f}{Style.RESET_ALL}%",
            ]
            table_data.append(row)

        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def _get_currency(self):
        display_currency = getattr(self.config, "display_currency", None)
        if display_currency:
            return display_currency
        return "PLN" if hasattr(self.config, "pip_value") else "zł"

    def show_take_profit(self, entry, tp, ratio, profit, profit_pct, stop_loss=None, include_entry_stop=True):
        print(f"\n{Fore.BLUE}--- Position Analysis ---{Style.RESET_ALL}")
        if include_entry_stop:
            print(
                f"Entry Price: {Fore.YELLOW}{entry:.{self.pip_decimals}f}{Style.RESET_ALL}"
            )
            if stop_loss is not None:
                print(
                    f"Stop_loss: {Fore.RED}{stop_loss:.{self.pip_decimals}f}{Style.RESET_ALL}"
                )
        print(f"Take Profit: {Fore.GREEN}{tp:.{self.pip_decimals}f}{Style.RESET_ALL}")
        print(f"Z/R Ratio: {Fore.MAGENTA}{ratio:.2f}:1{Style.RESET_ALL}")
        print(
            f"Potential profit on trade: {Fore.CYAN}{profit:,.2f} {self._get_currency()}{Style.RESET_ALL}"
        )
        print(
            f"Whole wallet profit potential: {Fore.LIGHTBLUE_EX}{profit_pct:.2f}%{Style.RESET_ALL}"
        )

    def show_warning(self, ratio):
        if ratio <= 4:
            print(f"\n{Fore.RED}WARNING: Risk/Reward ratio <= 4:1{Style.RESET_ALL}")
