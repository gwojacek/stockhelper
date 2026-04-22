import argparse

from chart_tools.level_selector import run_level_selector
from configs.stocks import CCC
from core.factory import StrategyFactory
from configs.commodities import Lockhead_Martin_long


def analyze(config_module):
    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


def _build_parser():
    parser = argparse.ArgumentParser(description="stockhelper entrypoint")
    parser.add_argument("--chart", help="Launch interactive chart selector for symbol/config slug")
    return parser


if __name__ == "__main__":
    parser = _build_parser()
    args, unknown = parser.parse_known_args()

    if args.chart:
        selector_args = [args.chart, *unknown]
        result = run_level_selector(selector_args)
        print("Chart workflow completed:", result)
    else:
        # analyze(CCC)
        analyze(Lockhead_Martin_long)
