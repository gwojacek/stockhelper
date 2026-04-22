from core import DisplayHandler, calculator, risk_manager
from strategies.base_strategy import BaseStrategy
from colorama import Fore, Style


class CommodityStrategy(BaseStrategy):
    def calculate(self):
        for risk in self.config.risk_levels:
            self.results[risk] = calculator.calculate_position_size(
                entry=self.config.entry,
                stop_loss=self.config.stop_loss,
                capital=self.config.capital,
                risk_percent=risk,
                pip_value=self.config.pip_value,
                lot_cost=self.config.lot_cost,
                spread=self.config.spread,
                position_type=self.config.position_type,
                instrument_type="commodity",
            )

        self.line_cross_value = getattr(self.config, "line_cross_value", None)
        self.check_zr_value = getattr(
            self.config, "check_zr_value_fibo_or_elevation", None
        )

        self.take_profit = None
        self.profit = 0.0
        self.profit_pct = 0.0

        if self.line_cross_value is not None:
            self.take_profit = risk_manager.calculate_take_profit(
                self.config.entry,
                self.config.high,
                self.config.low,
                self.config.position_type,
                start_value=self.line_cross_value,
            )

            max_lots = self.results[min(self.config.risk_levels)]["lots"]
            self.profit = (
                abs(self.take_profit - self.config.entry)
                * max_lots
                * self.config.pip_value
            )
            self.profit_pct = (self.profit / self.config.capital) * 100

        self.check_zr_ratio = None
        if self.check_zr_value is not None:
            self.check_zr_ratio = risk_manager.calculate_distance_ratio(
                self.config.entry,
                self.config.stop_loss,
                self.check_zr_value,
            )

    def display_results(self):
        disp = DisplayHandler(self.config)
        disp.show_header(f"{self.config.name} {self.config.position_type}")
        disp.show_results(self.results)

        notes: list[str] = []

        def show_notes():
            if not notes:
                return
            print(f"\n{Fore.BLUE}--- Notes ---{Style.RESET_ALL}")
            for note in notes:
                print(f"- {Fore.YELLOW}{note}{Style.RESET_ALL}")

        # Find which risk levels have invalid positions
        invalid_risks = [
            f"{risk * 100:.1f}%"
            for risk, data in self.results.items()
            if data.get("lots") == 0 or data.get("potential_loss") == 0
        ]

        # Show warning about invalid risk levels if any exist
        if invalid_risks:
            print(
                f"\n{Fore.RED}Warning: No valid position could be calculated for risk levels: {', '.join(invalid_risks)}{Style.RESET_ALL}"
            )
            print(
                f"Reason: Entry ({self.config.entry}) and Stop Loss ({self.config.stop_loss}) are either too close or to far away"
            )

        # Only proceed with profit calculations if we have at least one valid position
        valid_results = [
            data for data in self.results.values() if data.get("lots", 0) > 0
        ]
        if not valid_results:
            notes.append(
                "Take Profit and additional Z/R checks were skipped because no valid position size was calculated."
            )
            show_notes()
            return

        # Use the smallest valid risk level for profit calculations
        base_risk = min(
            [risk for risk, data in self.results.items() if data.get("lots", 0) > 0]
        )
        base_result = self.results[base_risk]

        if self.take_profit is not None:
            try:
                ratio = self.profit / base_result["potential_loss"]
                disp.show_take_profit(
                    self.config.entry,
                    self.take_profit,
                    ratio,
                    self.profit,
                    self.profit_pct,
                    stop_loss=self.config.stop_loss,
                )
                disp.show_warning(ratio)
            except ZeroDivisionError:
                notes.append(
                    "Risk/reward ratio could not be calculated."
                )
        else:
            print(
                f"\nEntry Price: {Fore.YELLOW}{self.config.entry:.{disp.pip_decimals}f}{Style.RESET_ALL}"
            )
            print(
                f"Stop_loss: {Fore.RED}{self.config.stop_loss:.{disp.pip_decimals}f}{Style.RESET_ALL}"
            )
            notes.append(
                "Take Profit was not calculated because optional line_cross_value is not set in TradingConfig."
            )

        if self.check_zr_ratio is not None:
            print(
                f"Additional Z/R check (check_zr_value_fibo_or_elevation): {Fore.MAGENTA}{self.check_zr_ratio:.2f}:1{Style.RESET_ALL}"
            )
            if self.check_zr_ratio <= 4:
                print(
                    f"{Fore.RED}WARNING: Additional Z/R ratio is <= 4:1 for check_zr_value_fibo_or_elevation.{Style.RESET_ALL}"
                )
        else:
            notes.append(
                "Optional check_zr_value_fibo_or_elevation is not set, so additional Z/R>=4 validation was skipped."
            )

        show_notes()
