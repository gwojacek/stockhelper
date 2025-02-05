from core.factory import StrategyFactory
from configs.commodities import wheat_short, silver_long
from configs.forex import gbpusd_long, eurjpy_short, eurchf_short


def analyze(config_module):
    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


if __name__ == "__main__":
    analyze(silver_long)
    # analyze(wheat_short)
    # analyze(gbpusd_long)
    # analyze(eurjpy_short)
    # analyze(eurchf_short)
