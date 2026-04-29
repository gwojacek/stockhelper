import argparse
from importlib import util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

from core.factory import StrategyFactory

# Default quick-start example when no --config is provided.
DEFAULT_STOCK_CONFIG = "BFT"


def _normalize_config_key(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


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

    stock_dir = PROJECT_ROOT / "configs" / "stocks"
    raw = (config_input or "").strip().replace(".py", "")
    normalized_input = _normalize_config_key(raw)

    exact_matches = [
        path for path in stock_dir.glob("*.py") if _normalize_config_key(path.stem) == normalized_input
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]

    prefix_matches = [
        path for path in stock_dir.glob("*.py") if _normalize_config_key(path.stem).startswith(normalized_input)
    ]
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    if len(exact_matches) > 1 or len(prefix_matches) > 1:
        ambiguous = exact_matches if len(exact_matches) > 1 else prefix_matches
        candidates = ", ".join(sorted(p.stem for p in ambiguous))
        raise FileNotFoundError(
            f"Ambiguous stock config '{config_input}'. Matches: {candidates}. "
            "Please pass a full path."
        )

    raise FileNotFoundError(
        f"Stock config not found: {config_input}. "
        f"Searched in {stock_dir} using case-insensitive and normalized matching."
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
