from core import DisplayHandler, calculator, risk_manager
from strategies.base_strategy import BaseStrategy


class StockStrategy(BaseStrategy):
    def calculate(self):
        self.take_profit = risk_manager.calculate_take_profit(
            self.config.entry,
            self.config.high,
            self.config.low,
            "long"
        )

        for risk in self.config.risk_levels:
            self.results[risk] = calculator.calculate_stock_position(
                self.config.entry,
                self.config.stop_loss,
                self.config.capital,
                risk,
                self.config.max_capital
            )

        base_shares = self.results[min(self.config.risk_levels)]['shares']
        self.profit = base_shares * (self.take_profit - self.config.entry)
        self.profit_pct = (self.profit / self.config.capital) * 100

    def display_results(self):
        disp = DisplayHandler(self.config)
        disp.show_header(f"{self.config.name} Stock")
        disp.show_results(self.results)
        disp.show_take_profit(
            self.config.entry,
            self.take_profit,
            self.profit / self.results[min(self.config.risk_levels)]['potential_loss'],
            self.profit,
            self.profit_pct
        )
        disp.show_warning(self.profit / self.results[min(self.config.risk_levels)]['potential_loss'])

    def extended_analysis(self):
        adjusted_prices = [
            self.config.entry * (1 + adj)
            for adj in [-0.02, -0.01, 0, 0.01, 0.02]
        ]

        return [
            {
                "price": price,
                **calculator.calculate_stock_position(
                    price,
                    self.config.stop_loss,
                    self.config.capital,
                    min(self.config.risk_levels),
                    self.config.max_capital
                )
            } for price in adjusted_prices
        ]