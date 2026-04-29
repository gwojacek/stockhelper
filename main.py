import argparse
from importlib import util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

from core.factory import StrategyFactory


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


def _normalize_config_key(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _resolve_market_config_path(config_input: str) -> Path:
    candidate = Path(config_input)
    if candidate.suffix == ".py" and candidate.exists():
        return candidate

    raw = (config_input or "").strip().replace(".py", "")
    normalized_input = _normalize_config_key(raw)
    search_dirs = [PROJECT_ROOT / "configs" / "commodities", PROJECT_ROOT / "configs" / "forex"]

    exact_matches = []
    prefix_matches = []
    for directory in search_dirs:
        for path in directory.glob("*.py"):
            key = _normalize_config_key(path.stem)
            if key == normalized_input:
                exact_matches.append(path)
            if key.startswith(normalized_input):
                prefix_matches.append(path)

    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    if len(exact_matches) > 1 or len(prefix_matches) > 1:
        ambiguous = exact_matches if len(exact_matches) > 1 else prefix_matches
        candidates = ", ".join(sorted(p.stem for p in ambiguous))
        raise FileNotFoundError(
            f"Ambiguous config '{config_input}'. Matches: {candidates}. Please pass a full path."
        )

    raise FileNotFoundError(
        f"Config not found: {config_input}. Searched in commodities/ and forex/ with case-insensitive normalized matching."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run commodity/forex analysis")
    parser.add_argument("config", nargs="?", help="Config path or slug (e.g. configs/commodities/Cocoa_short.py or cocoa_short)")
    parser.add_argument("--config", dest="config_flag", help="(Legacy) config path or slug")
    args = parser.parse_args()

    config_input = args.config_flag or args.config
    if config_input:
        analyze(_load_config_module(str(_resolve_market_config_path(config_input))))
        return 0

    from configs.commodities import Lockhead_Martin_long

    analyze(Lockhead_Martin_long)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
