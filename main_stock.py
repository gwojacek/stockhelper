import argparse
from importlib import util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

from core.factory import StrategyFactory

# Default quick-start example when no --config is provided.
DEFAULT_STOCK_CONFIG = "BFT"


def analyze(config_module):
    strategy = StrategyFactory.create(config_module.TradingConfig())
    strategy.calculate()
    strategy.display_results()


def _load_config_module(config_path: str):
    path = Path(config_path).resolve()
    spec = util.spec_from_file_location(f"cfg_{path.stem}", path)
    if not spec or not spec.loader:
        raise ValueError(f"Unable to load config module from: {path}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module




def _resolve_stock_config_path(config_input: str) -> Path:
    candidate = Path(config_input)
    if candidate.suffix == ".py" and candidate.exists():
        return candidate

    normalized = config_input.strip().lower().replace(".py", "")
    slug_path = PROJECT_ROOT / "configs" / "stocks" / f"{normalized}.py"
    if slug_path.exists():
        return slug_path

    raise FileNotFoundError(
        f"Stock config not found: {config_input}. "
        f"Tried explicit path and {slug_path}"
    )

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run stock analysis",
        epilog=f"Default demo config (when --config is omitted): {DEFAULT_STOCK_CONFIG}",
    )
    parser.add_argument("config", nargs="?", help="Stock config path or slug (e.g. configs/stocks/bft.py or bft)")
    parser.add_argument("--config", dest="config_flag", help="(Legacy) stock config path or slug")
    args = parser.parse_args()

    config_input = args.config_flag or args.config
    if config_input:
        analyze(_load_config_module(str(_resolve_stock_config_path(config_input))))
        return 0

    from configs.stocks import BFT

    analyze(BFT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
