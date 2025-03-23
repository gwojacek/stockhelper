from utilities.yahoo_finance import get_avg_daily_turnover_yahoo
from core import DisplayHandler, calculator, risk_manager
from strategies.base_strategy import BaseStrategy
from colorama import Fore, Style


class StockStrategy(BaseStrategy):
    def calculate(self):
        self.used_default_turnover = False  # Flaga informująca, czy użyto fallbacku
        try:
            avg_daily_turnover = get_avg_daily_turnover_yahoo(self.config.symbol)
        except Exception as e:
            print(f"Błąd podczas pobierania danych z Yahoo Finance: {e}")
            # Fallback: użycie domyślnego średniego obrotu = 30,000,000
            avg_daily_turnover = 30000000
            self.used_default_turnover = True

        # Obliczenie max_capital jako 1% średniego dziennego obrotu
        calculated_max_capital = avg_daily_turnover * 0.01
        self.config.max_capital = calculated_max_capital

        # Używamy ręcznie ustawionych wartości entry, high, low (z pliku konfiguracyjnego)
        self.take_profit = risk_manager.calculate_take_profit(
            self.config.entry, self.config.high, self.config.low, "long"
        )

        for risk in self.config.risk_levels:
            self.results[risk] = calculator.calculate_stock_position(
                self.config.entry,
                self.config.stop_loss,
                self.config.capital,
                risk,
                self.config.max_capital,
            )

        base_shares = self.results[min(self.config.risk_levels)]["shares"]
        self.profit = base_shares * (self.take_profit - self.config.entry)
        self.profit_pct = (self.profit / self.config.capital) * 100

    def display_results(self):
        disp = DisplayHandler(self.config)
        disp.show_header(f"{self.config.name} Stock")
        disp.show_results(self.results)

        # Jeżeli użyto fallbacku, wyróżnij wartość kolorem (np. czerwonym)
        if getattr(self, 'used_default_turnover', False):
            default_info = f"{Fore.RED}(użyto domyślnej wartości){Style.RESET_ALL}"
        else:
            default_info = ""

        print(f"\nCalculated Max Capital: {self.config.max_capital:,.2f} {disp._get_currency()} {default_info}")

        potential_loss = self.results[min(self.config.risk_levels)]["potential_loss"]
        ratio = self.profit / potential_loss if potential_loss != 0 else 0

        disp.show_take_profit(
            self.config.entry,
            self.take_profit,
            ratio,
            self.profit,
            self.profit_pct,
        )
        disp.show_warning(ratio)

    def extended_analysis(self):
        adjusted_prices = [
            self.config.entry * (1 + adj) for adj in [-0.02, -0.01, 0, 0.01, 0.02]
        ]

        return [
            {
                "price": price,
                **calculator.calculate_stock_position(
                    price,
                    self.config.stop_loss,
                    self.config.capital,
                    min(self.config.risk_levels),
                    self.config.max_capital,
                ),
            }
            for price in adjusted_prices
        ]
