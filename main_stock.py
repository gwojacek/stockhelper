from core.factory import StrategyFactory
from configs.stocks import pepco, CCC, kruk, jsw
from configs.stocks import opl  # opl should be a module exporting TradingConfig


def analyze(config_module):
    # Create an instance of TradingConfig from the module
    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


if __name__ == "__main__":
    # analyze(kruk)
    # analyze(CCC)
    analyze(jsw)
