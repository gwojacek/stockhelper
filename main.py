import argparse

def analyze(config_module):
    from core.factory import StrategyFactory

    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


def _build_parser():
    parser = argparse.ArgumentParser(description="stockhelper entrypoint")
    parser.add_argument("--chart", help="Launch interactive chart selector for symbol/config slug")
    parser.add_argument(
        "--analyze-default",
        action="store_true",
        help="Run legacy default analysis flow (Lockhead_Martin_long)",
    )
    return parser


def _prompt_chart_target() -> str | None:
    try:
        target = input("Enter symbol/config for chart mode (e.g. jsw, coffee_long, AUD/USD): ").strip()
    except EOFError:
        return None
    return target or None


if __name__ == "__main__":
    parser = _build_parser()
    args, unknown = parser.parse_known_args()

    chart_target = args.chart
    if not chart_target and not args.analyze_default:
        chart_target = _prompt_chart_target()

    if chart_target:
        from chart_tools.level_selector import run_level_selector

        selector_args = [chart_target, *unknown]
        result = run_level_selector(selector_args)
        print("Chart workflow completed:", result)
    elif args.analyze_default:
        from configs.commodities import Lockhead_Martin_long

        analyze(Lockhead_Martin_long)
    else:
        parser.print_help()
