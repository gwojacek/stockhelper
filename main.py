from configs.stocks import kghm, CCC
from core.factory import StrategyFactory
from configs.commodities import (
    wheat_short,
    silver_long,
    copper_long,
    sugar_long,
    coffee_long, wig20_long, us100, Cocoa, US500_long, smci_long, Lockhead_Martin_long, natural_gas_long,
    crude_oil_long, Cocoa_short,
)
from configs.forex import (
    gbpusd_long,
    eurjpy_long,
    eurchf_short,
    eurgbp_long,
    gbpchf_long,
    eurchf_long,
    audusd_long,
    eurpln_long, usdjpy_long, usdpln_long, usd_pln_short, usdcad_long,
)


def analyze(config_module):
    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


if __name__ == "__main__":
    # analyze(CCC)
    analyze(Lockhead_Martin_long)
    # analyze(sugar_long)
