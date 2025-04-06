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

        self.take_profit = risk_manager.calculate_take_profit(
            self.config.entry,
            self.config.high,
            self.config.low,
            self.config.position_type,
        )

        max_lots = self.results[min(self.config.risk_levels)]["lots"]
        self.profit = (
            abs(self.take_profit - self.config.entry) * max_lots * self.config.pip_value
        )
        self.profit_pct = (self.profit / self.config.capital) * 100

    def display_results(self):
        disp = DisplayHandler(self.config)
        disp.show_header(f"{self.config.name} {self.config.position_type}")
        disp.show_results(self.results)

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
            return

        # Use the smallest valid risk level for profit calculations
        base_risk = min(
            [risk for risk, data in self.results.items() if data.get("lots", 0) > 0]
        )
        base_result = self.results[base_risk]

        try:
            ratio = self.profit / base_result["potential_loss"]
            disp.show_take_profit(
                self.config.entry,
                self.take_profit,
                ratio,
                self.profit,
                self.profit_pct,
            )
            disp.show_warning(ratio)
        except ZeroDivisionError:
            print(
                f"\n{Fore.YELLOW}Note: Risk/reward ratio could not be calculated{Style.RESET_ALL}"
            )
