from colorama import Fore, Style
import math

from core import DisplayHandler, calculator, risk_manager
from strategies.base_strategy import BaseStrategy
from utilities.yahoo_finance import (
    get_avg_daily_turnover_yahoo,
    get_daily_turnovers_yahoo,
    get_fx_to_pln_rate_yahoo,
    get_symbol_currency_yahoo,
)


class StockStrategy(BaseStrategy):
    """Strategia dla akcji z kontrolą płynności i progów kapitału."""
    # Przybliżone relacje GDP(PPP) do Polski (PL=1.0) na podstawie rankingu krajów.
    GDP_PPP_VALUE = {
        "PL": 2120569,
        "US": 31821293,
        "DE": 6323531,
        "FR": 4657190,
        "CN": 43491520,
    }

    SUFFIX_TO_COUNTRY = {
        "WA": "PL",
        "US": "US",
        "DE": "DE",
        "PA": "FR",
        "SS": "CN",
    }

    def _get_country_code(self) -> str:
        """Zwraca kod kraju na podstawie sufiksu symbolu Yahoo."""
        symbol = getattr(self.config, "symbol", "") or ""
        if "." not in symbol:
            return "US"
        suffix = symbol.split(".")[-1].upper()
        return self.SUFFIX_TO_COUNTRY.get(suffix, "US")

    def _get_min_capital_threshold(self, base_threshold: float) -> float:
        """Przelicza próg bazowy PLN o mnożnik GDP(PPP) względem Polski."""
        return base_threshold * self._get_gdp_multiplier()

    def _get_gdp_multiplier(self) -> float:
        """Zwraca mnożnik GDP(PPP) kraju względem Polski."""
        country_code = self._get_country_code()
        pl_gdp_ppp = self.GDP_PPP_VALUE["PL"]
        country_gdp_ppp = self.GDP_PPP_VALUE.get(country_code, pl_gdp_ppp)
        return country_gdp_ppp / pl_gdp_ppp

    def _get_liquidity_threshold(self) -> float:
        """Zwraca próg płynności dla Ichimoku (bazowo 300k PLN, GDP-adjusted)."""
        return self._get_min_capital_threshold(300000)

    def calculate(self):
        """Liczy pozycje, max kapitał i metryki płynności (w PLN)."""
        self.used_default_turnover = False
        self.currency_pair_used = "PLNPLN=X"
        self.fx_rate_to_pln = 1.0
        self.stock_currency = "PLN"

        try:
            avg_daily_turnover = get_avg_daily_turnover_yahoo(
                self.config.symbol, period="10d"
            )
            daily_turnovers_20d = get_daily_turnovers_yahoo(
                self.config.symbol, period="20d"
            )
            self.stock_currency = get_symbol_currency_yahoo(self.config.symbol)
            self.currency_pair_used, self.fx_rate_to_pln = get_fx_to_pln_rate_yahoo(
                self.stock_currency
            )
            if not math.isfinite(avg_daily_turnover) or avg_daily_turnover <= 0:
                raise ValueError(
                    f"Nieprawidłowy średni dzienny obrót z Yahoo: {avg_daily_turnover}"
                )
            if not math.isfinite(self.fx_rate_to_pln) or self.fx_rate_to_pln <= 0:
                raise ValueError(
                    f"Nieprawidłowy kurs FX do PLN z Yahoo: {self.fx_rate_to_pln}"
                )
        except Exception as e:
            print(f"Błąd podczas pobierania danych z Yahoo Finance: {e}")
            # Fallback: użycie domyślnego średniego obrotu
            avg_daily_turnover = 30000000
            daily_turnovers_20d = []
            self.currency_pair_used = "PLNPLN=X"
            self.fx_rate_to_pln = 1.0
            self.stock_currency = "PLN"
            self.used_default_turnover = True

        avg_daily_turnover_pln = avg_daily_turnover * self.fx_rate_to_pln
        daily_turnovers_20d_pln = [
            turnover * self.fx_rate_to_pln for turnover in daily_turnovers_20d
        ]
        self.entry_pln = self.config.entry * self.fx_rate_to_pln
        self.stop_loss_pln = self.config.stop_loss * self.fx_rate_to_pln
        self.high_pln = self.config.high * self.fx_rate_to_pln
        self.low_pln = self.config.low * self.fx_rate_to_pln

        # Obliczenie max_capital jako 1% średniego dziennego obrotu
        self.config.max_capital = avg_daily_turnover_pln * 0.01

        # Ichimoku używa tego samego max_capital (z 10d), ale ma osobny safeguard płynności 20d
        self.liquidity_threshold_ichimoku = self._get_liquidity_threshold()
        self.low_turnover_days_ichimoku = sum(
            1
            for turnover in daily_turnovers_20d_pln
            if turnover < self.liquidity_threshold_ichimoku
        )

        # Take profit do wyświetlania liczymy tylko, jeśli optional line_cross_value jest ustawione.
        line_cross_value = getattr(self.config, "line_cross_value", None)
        self.check_zr_value = getattr(
            self.config, "check_zr_value_fibo_or_elevation", None
        )
        self.take_profit_display = None

        for risk in self.config.risk_levels:
            self.results[risk] = calculator.calculate_stock_position(
                self.entry_pln,
                self.stop_loss_pln,
                self.config.capital,
                risk,
                self.config.max_capital,
            )

        self.profit = 0.0
        self.profit_pct = 0.0
        if line_cross_value is not None:
            self.take_profit_display = risk_manager.calculate_take_profit(
                self.config.entry,
                self.config.high,
                self.config.low,
                "long",
                start_value=line_cross_value,
            )

            base_shares = self.results[min(self.config.risk_levels)]["shares"]
            self.profit = (
                base_shares
                * (self.take_profit_display - self.config.entry)
                * self.fx_rate_to_pln
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
        """Wyświetla tabelę wyników, warningi i analizę take-profit."""
        disp = DisplayHandler(self.config)
        disp.show_header(f"{self.config.name} Stock")
        disp.show_results(self.results)

        if getattr(self, "used_default_turnover", False):
            default_info = f"{Fore.RED}(użyto domyślnej wartości){Style.RESET_ALL}"
        else:
            default_info = ""

        min_capital = self._get_min_capital_threshold(5000)
        min_capital_ichimoku = self._get_min_capital_threshold(7000)
        gdp_multiplier = self._get_gdp_multiplier()
        country_code = self._get_country_code()

        print(
            f"\nCalculated Max Capital: {self.config.max_capital:,.2f} {disp._get_currency()} {default_info}"
        )
        if self.config.max_capital < min_capital:
            print(
                f"{Fore.RED}{Style.BRIGHT}WARNING: Calculated Max Capital is below minimum {min_capital:,.0f} PLN (GDP-adjusted)!{Style.RESET_ALL}"
            )
        if self.stock_currency != "PLN":
            print(
                f"FX conversion used: {self.currency_pair_used} = {self.fx_rate_to_pln:.4f} (daily turnover converted from {self.stock_currency} to PLN)"
            )
        print(f"GDP multiplier used ({country_code}/PL): {gdp_multiplier:.4f}x")

        if self.config.max_capital < min_capital_ichimoku:
            print(
                f"{Fore.RED}{Style.BRIGHT}WARNING: Calculated Max Capital for Ichimoku is below minimum {min_capital_ichimoku:,.0f} PLN (GDP-adjusted)!{Style.RESET_ALL}"
            )
        if self.low_turnover_days_ichimoku > 2:
            print(
                f"{Fore.RED}{Style.BRIGHT}WARNING: Ichimoku liquidity check failed ({self.low_turnover_days_ichimoku} days below {self.liquidity_threshold_ichimoku:,.0f} PLN turnover in last 20 days).{Style.RESET_ALL}"
            )

        notes: list[str] = []
        if self.check_zr_ratio is not None:
            print(f"\n{Fore.BLUE}--- Additional Z/R Check ---{Style.RESET_ALL}")
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

        if self.take_profit_display is None:
            print(
                f"\nEntry Price: {Fore.YELLOW}{self.config.entry:.{disp.pip_decimals}f}{Style.RESET_ALL}"
            )
            print(
                f"Stop_loss: {Fore.RED}{self.config.stop_loss:.{disp.pip_decimals}f}{Style.RESET_ALL}"
            )
            notes.append(
                "Take Profit was not calculated because optional line_cross_value is not set in TradingConfig."
            )
            if notes:
                print(f"\n{Fore.BLUE}--- Notes ---{Style.RESET_ALL}")
                for note in notes:
                    print(f"- {Fore.YELLOW}{note}{Style.RESET_ALL}")
            return

        potential_loss = self.results[min(self.config.risk_levels)]["potential_loss"]
        ratio = self.profit / potential_loss if potential_loss != 0 else 0

        disp.show_take_profit(
            self.config.entry,
            self.take_profit_display,
            ratio,
            self.profit,
            self.profit_pct,
            stop_loss=self.config.stop_loss,
        )
        disp.show_warning(ratio)
        if notes:
            print(f"\n{Fore.BLUE}--- Notes ---{Style.RESET_ALL}")
            for note in notes:
                print(f"- {Fore.YELLOW}{note}{Style.RESET_ALL}")

    def extended_analysis(self):
        """Zwraca analizę wrażliwości wyników dla kilku wariantów ceny wejścia."""
        adjusted_prices = [
            self.entry_pln * (1 + adj) for adj in [-0.02, -0.01, 0, 0.01, 0.02]
        ]

        return [
            {
                "price": price,
                **calculator.calculate_stock_position(
                    price,
                    self.stop_loss_pln,
                    self.config.capital,
                    min(self.config.risk_levels),
                    self.config.max_capital,
                ),
            }
            for price in adjusted_prices
        ]
