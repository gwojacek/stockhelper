from tabulate import tabulate
from colorama import Fore, Style, init

init(autoreset=True)


class DisplayHandler:
    def __init__(self, config):
        self.config = config
        self.pip_decimals = self._get_pip_decimals()

    def _get_pip_decimals(self):
        if hasattr(self.config, 'pip_size'):
            return 4 if self.config.pip_size < 0.001 else 2
        return 2

    def show_header(self, title):
        print(f"\n{Fore.CYAN}=== {title.upper()} ==={Style.RESET_ALL}")

    def show_results(self, results):
        headers = [
            "Risk Level",
            "Position Size",
            "Engaged Capital",
            "Potential Loss",
            "Loss %"
        ]

        table_data = []
        for risk, data in results.items():
            row = [
                # Risk Level (no color)
                f"{risk * 100:.1f}%",

                # Position Size (yellow value only)
                f"{Fore.YELLOW}{data.get('lots', data.get('shares', 0)):.2f}{Style.RESET_ALL} {'Lots' if 'lots' in data else 'Shares'}",

                # Engaged Capital (magenta value only)
                f"{Fore.MAGENTA}{data['capital_used']:,.2f}{Style.RESET_ALL} {self._get_currency()}",

                # Potential Loss (red value only)
                f"{Fore.RED}{data['potential_loss']:,.2f}{Style.RESET_ALL} {self._get_currency()}",

                # Loss % (light red value only)
                f"{Fore.LIGHTRED_EX}{data['risk_percent']:.2f}{Style.RESET_ALL}%"
            ]
            table_data.append(row)

        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    def _get_currency(self):
        return "PLN" if hasattr(self.config, 'pip_value') else "zł"

    def show_take_profit(self, entry, tp, ratio, profit, profit_pct):
        print(f"\n{Fore.BLUE}--- Take Profit Analysis ---{Style.RESET_ALL}")
        print(f"Entry Price: {Fore.YELLOW}{entry:.{self.pip_decimals}f}{Style.RESET_ALL}")
        print(f"Take Profit: {Fore.GREEN}{tp:.{self.pip_decimals}f}{Style.RESET_ALL}")
        print(f"Z/R Ratio: {Fore.MAGENTA}{ratio:.2f}:1{Style.RESET_ALL}")
        print(f"Potential Profit: {Fore.CYAN}{profit:,.2f} {self._get_currency()}{Style.RESET_ALL}")
        print(f"Profit Potential: {Fore.LIGHTBLUE_EX}{profit_pct:.2f}%{Style.RESET_ALL}")

    def show_warning(self, ratio):
        if ratio <= 4:
            print(f"\n{Fore.RED}WARNING: Risk/Reward ratio <= 4:1{Style.RESET_ALL}")