from core.factory import StrategyFactory
from configs.stocks import pepco, CCC, kruk, jsw, opl


def analyze(config_module):
    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


if __name__ == "__main__":
    analyze(kruk)
