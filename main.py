from configs.stocks import kghm
from core.factory import StrategyFactory
from configs.commodities import wheat_short, silver_long, copper_long, sugar_long
from configs.forex import (
    gbpusd_long,
    eurjpy_short,
    eurchf_short,
    eurgbp_long,
    gbpchf_long, eurchf_long, audusd_long, eurpln_long,
)


def analyze(config_module):
    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


if __name__ == "__main__":
    # analyze(silver_long)
    # analyze(wheat_short)
    analyze(kghm)
    # analyze(eurgbp_long)
    # analyze(copper_long)
