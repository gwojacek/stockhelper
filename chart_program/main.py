import argparse



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone chart-based level selection tool")
    parser.add_argument("target", nargs="?", help="Symbol, pair, or config slug (e.g. jsw, coffee_long, AUD/USD)")
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
    return parser


def main() -> int:
    parser = build_parser()
    args, unknown = parser.parse_known_args()

    target = args.target
    if not target:
        target = input("Enter symbol/config (e.g. jsw, coffee_long, AUD/USD): ").strip()

    if not target:
        parser.error("Target is required.")

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
    forwarded.extend(unknown)

    from chart_program.level_selector import run_level_selector

    result = run_level_selector(forwarded)
    if isinstance(result, dict) and result.get("message"):
        print(result["message"])
    else:
        print("Chart workflow completed:", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
