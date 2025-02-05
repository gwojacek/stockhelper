from core import calculator, risk_manager, DisplayHandler
from strategies.base_strategy import BaseStrategy


class ForexStrategy(BaseStrategy):
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
                pip_size=self.config.pip_size,
                position_type=self.config.position_type,
                instrument_type="forex",
            )

        self.take_profit = risk_manager.calculate_take_profit(
            self.config.entry,
            self.config.high,
            self.config.low,
            self.config.position_type,
        )

        max_lots = self.results[min(self.config.risk_levels)]["lots"]

        # Convert price difference into pips by dividing by pip_size
        pips_reward = abs(self.take_profit - self.config.entry) / self.config.pip_size
        self.profit = pips_reward * max_lots * self.config.pip_value

        self.profit_pct = (self.profit / self.config.capital) * 100

    def display_results(self):
        disp = DisplayHandler(self.config)
        # Change header to use name or pair if needed:
        disp.show_header(f"{self.config.pair} {self.config.position_type}")
        disp.show_results(self.results)
        disp.show_take_profit(
            self.config.entry,
            self.take_profit,
            self.profit / self.results[min(self.config.risk_levels)]["potential_loss"],
            self.profit,
            self.profit_pct,
        )
        disp.show_warning(
            self.profit / self.results[min(self.config.risk_levels)]["potential_loss"]
        )
