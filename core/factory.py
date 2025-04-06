from strategies.commodities import CommodityStrategy
from strategies.forex import ForexStrategy
from strategies.stock import StockStrategy


class StrategyFactory:
    @staticmethod
    def create(config):
        if hasattr(config, "instrument_type"):
            if config.instrument_type == "commodity":
                return CommodityStrategy(config)
            if config.instrument_type == "forex":
                return ForexStrategy(config)
            if config.instrument_type == "stock":
                return StockStrategy(config)
        # Fallback: jeśli konfiguracja ma symbol, uznajemy ją za akcje
        if hasattr(config, "symbol"):
            return StockStrategy(config)
        if hasattr(config, "max_capital"):  # legacy
            return StockStrategy(config)
        raise ValueError("Invalid configuration")
