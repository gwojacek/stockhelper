from core.factory import StrategyFactory
from configs.stocks.opl_config import OPLConfig
from core.display import DisplayHandler


def stock_main():
    config = OPLConfig()
    strategy = StrategyFactory.create(config)
    strategy.calculate()
    strategy.display_results()

    if input("Run extended analysis? (y/n): ").lower() == 'y':
        analysis = strategy.extended_analysis()
        DisplayHandler(config).show_extended_analysis(analysis)


if __name__ == "__main__":
    stock_main()