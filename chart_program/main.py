import argparse
import subprocess
import sys
from pathlib import Path



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chart_program", description="Standalone chart-based level selection tool")
    parser.add_argument("target", nargs="?", help="Symbol, pair, or config slug (e.g. jsw, coffee_long, AUD/USD)")
    parser.add_argument("chart_modifier", nargs="?", choices=["cfd", "CFD"], help="Use after a stock symbol to open it as CFD/commodity mode.")
    parser.add_argument("--config", help="Explicit config file path")
    parser.add_argument("--instrument", choices=["stock", "commodity", "forex"], help="Force instrument type")
    parser.add_argument("--position-type", choices=["long", "short"], help="Position type for commodity/forex")
    parser.add_argument("--capital", type=float, default=0.0)
    parser.add_argument("--lot-cost", type=float, default=0.0)
    parser.add_argument("--pip-value", type=float, default=0.0)
    parser.add_argument("--spread", type=float, default=0.0)
    parser.add_argument("--pip-size", type=float, default=0.0001)
    parser.add_argument("--api-key", help="Optional API key passed to data provider")
    parser.add_argument("--data-source", choices=["auto", "yahoo", "stooq"], default="auto")
    parser.add_argument("--ichimoku-mode", choices=["on", "off"], default="off")
    parser.add_argument("--fibo-lines", type=int, default=0)
    parser.add_argument("--fibo-anchor-start")
    parser.add_argument("--fibo-anchor-end")
    parser.add_argument("--fibo-right", action="store_true")
    parser.add_argument("--no-run-after-save", action="store_true", help="Do not run analysis script after saving config")
    parser.add_argument("--wedge-lines", action="store_true")
    parser.add_argument("--wedge-upper-start")
    parser.add_argument("--wedge-upper-end")
    parser.add_argument("--wedge-lower-start")
    parser.add_argument("--wedge-lower-end")
    parser.add_argument("--wedge-right", action="store_true")
    parser.add_argument("--journal-close-mode", action="store_true")
    parser.add_argument("--journal-entry-id")
    parser.add_argument("--journal-entry-price")
    parser.add_argument("--journal-direction", choices=["long", "short"])
    parser.add_argument("--journal-close-price")
    parser.add_argument("--journal-stop-loss")
    return parser


def _run_analysis_script(result: dict) -> None:
    config_path = result.get("config_path")
    instrument_type = result.get("instrument_type")
    if not config_path or instrument_type not in {"stock", "commodity", "forex"}:
        return

    project_root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, str(project_root / "run"), config_path]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = build_parser()
    args, unknown = parser.parse_known_args()

    target = args.target
    if not target:
        target = input("Enter symbol/config (e.g. jsw, coffee_long, AUD/USD): ").strip()

    if not target:
        parser.error("Target is required.")

    chart_modifier = (args.chart_modifier or "").strip().lower()
    if chart_modifier == "cfd" and not target.lower().endswith(" cfd"):
        target = f"{target} cfd"
        if not args.instrument:
            args.instrument = "commodity"
    forwarded = [target]
    if args.config:
        forwarded.extend(["--config", args.config])
    if args.instrument:
        forwarded.extend(["--instrument", args.instrument])
    if args.position_type:
        forwarded.extend(["--position-type", args.position_type])
    forwarded.extend(["--capital", str(args.capital)])
    forwarded.extend(["--lot-cost", str(args.lot_cost)])
    forwarded.extend(["--pip-value", str(args.pip_value)])
    forwarded.extend(["--spread", str(args.spread)])
    forwarded.extend(["--pip-size", str(args.pip_size)])
    if args.api_key:
        forwarded.extend(["--api-key", args.api_key])
    forwarded.extend(["--data-source", args.data_source])
    forwarded.extend(["--ichimoku-mode", args.ichimoku_mode])
    if args.fibo_lines:
        forwarded.extend(["--fibo-lines", str(args.fibo_lines)])
    if args.fibo_anchor_start:
        forwarded.extend(["--fibo-anchor-start", args.fibo_anchor_start])
    if args.fibo_anchor_end:
        forwarded.extend(["--fibo-anchor-end", args.fibo_anchor_end])
    if args.fibo_right:
        forwarded.append("--fibo-right")
    if args.wedge_lines:
        forwarded.append("--wedge-lines")
    for flag, value in [
        ("--wedge-upper-start", args.wedge_upper_start),
        ("--wedge-upper-end", args.wedge_upper_end),
        ("--wedge-lower-start", args.wedge_lower_start),
        ("--wedge-lower-end", args.wedge_lower_end),
    ]:
        if value:
            forwarded.extend([flag, value])
    if args.wedge_right:
        forwarded.append("--wedge-right")
    if args.journal_close_mode:
        forwarded.append("--journal-close-mode")
    for flag, value in [
        ("--journal-entry-id", args.journal_entry_id),
        ("--journal-entry-price", args.journal_entry_price),
        ("--journal-direction", args.journal_direction),
        ("--journal-close-price", args.journal_close_price),
        ("--journal-stop-loss", args.journal_stop_loss),
    ]:
        if value:
            forwarded.extend([flag, value])
    forwarded.extend(unknown)

    from chart_program.level_selector import run_level_selector

    result = run_level_selector(forwarded)
    if isinstance(result, dict) and result.get("message"):
        print(result["message"])

    if isinstance(result, dict) and result.get("config_path") and not args.no_run_after_save:
        _run_analysis_script(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
