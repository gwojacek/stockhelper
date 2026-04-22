from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from chart_program.chart_loader import load_or_update_daily_data
from chart_program.chart_ui import ChartLevelSelectorUI
from chart_program.config_writer import resolve_config_path, write_or_update_config
from chart_program.instrument_detector import detect_instrument_type


def _load_existing_config_values(config_path: Path) -> dict:
    if not config_path.exists():
        return {}

    module_name = f"_cfg_{config_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, config_path)
    if not spec or not spec.loader:
        return {}

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cfg = module.TradingConfig()

    data = {}
    for key in (
        "high",
        "low",
        "entry",
        "stop_loss",
        "check_zr_value_fibo_or_elevation",
        "line_cross_value",
        "position_type",
        "capital",
        "lot_cost",
        "pip_value",
        "pip_size",
        "spread",
        "symbol",
        "pair",
        "name",
    ):
        if hasattr(cfg, key):
            data[key] = getattr(cfg, key)
    return data


def _parse_args(raw_args=None):
    parser = argparse.ArgumentParser(description="Interactive chart-based level selector")
    parser.add_argument("target", help="Target symbol or config slug. Examples: jsw, coffee_long, AUD/USD")
    parser.add_argument("--config", help="Explicit config path to update/create")
    parser.add_argument("--instrument", choices=["stock", "commodity", "forex"], help="Override instrument type")
    parser.add_argument("--position-type", choices=["long", "short"], help="Position type for commodity/forex")
    parser.add_argument("--capital", type=float, default=0.0)
    parser.add_argument("--lot-cost", type=float, default=0.0)
    parser.add_argument("--pip-value", type=float, default=0.0)
    parser.add_argument("--spread", type=float, default=0.0)
    parser.add_argument("--pip-size", type=float, default=0.0001)
    parser.add_argument("--api-key", help="Optional API key forwarded to Stooq query parameters")
    parser.add_argument("--data-source", choices=["auto", "yahoo", "stooq"], default="auto")
    return parser.parse_args(raw_args)


def _snapshot_file(path: Path):
    if path.exists():
        return True, path.read_bytes()
    return False, b""


def _restore_file(path: Path, existed_before: bool, content: bytes):
    if existed_before:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    elif path.exists():
        path.unlink()


def run_level_selector(raw_args=None):
    args = _parse_args(raw_args)

    maybe_config_path = Path(args.config) if args.config else None
    instrument_type = args.instrument or detect_instrument_type(args.target, maybe_config_path)

    config_path = maybe_config_path or resolve_config_path(instrument_type, args.target)
    existing = _load_existing_config_values(config_path)

    if instrument_type == "forex":
        symbol = existing.get("pair", args.target if "/" in args.target else f"{args.target[:3].upper()}/{args.target[3:6].upper()}")
    elif instrument_type == "stock":
        symbol = existing.get("symbol", args.target.upper() if "." in args.target else f"{args.target.upper()}.WA")
    else:
        symbol = existing.get("name", args.target.upper())

    df, data_path = load_or_update_daily_data(
        symbol=symbol,
        instrument_type=instrument_type,
        persist=False,
        api_key=args.api_key,
        data_source=args.data_source,
    )

    ui = ChartLevelSelectorUI(symbol=symbol, dataframe=df, instrument_type=instrument_type, preset_values=existing)
    selected = ui.run()

    values = {
        "instrument_type": instrument_type,
        "high": selected.get("high"),
        "low": selected.get("low"),
        "entry": selected.get("entry"),
        "stop_loss": selected.get("stop_loss"),
        "check_zr_value_fibo_or_elevation": selected.get("check_zr_value_fibo_or_elevation"),
        "line_cross_value": selected.get("line_cross_value"),
        "capital": selected.get("capital", args.capital),
    }

    if instrument_type == "stock":
        values.update({"name": args.target.lower(), "symbol": symbol})
    elif instrument_type == "commodity":
        values.update(
            {
                "name": symbol,
                "position_type": selected.get("position_type", args.position_type or "long"),
                "lot_cost": selected.get("lot_cost", args.lot_cost),
                "pip_value": selected.get("pip_value", args.pip_value),
                "spread": selected.get("spread", args.spread),
            }
        )
    else:
        values.update(
            {
                "pair": symbol,
                "position_type": selected.get("position_type", args.position_type or "long"),
                "lot_cost": selected.get("lot_cost", args.lot_cost),
                "pip_value": selected.get("pip_value", args.pip_value),
                "spread": selected.get("spread", args.spread),
                "pip_size": selected.get("pip_size", args.pip_size),
            }
        )

    snapshot_name = f"{config_path.stem}_levels.png"
    chart_path = Path("charts") / snapshot_name

    config_existed, config_backup = _snapshot_file(config_path)
    chart_existed, chart_backup = _snapshot_file(chart_path)
    data_existed, data_backup = _snapshot_file(data_path)

    try:
        path = write_or_update_config(instrument_type=instrument_type, config_path=config_path, values=values)
        ui.save_chart_snapshot(selected, chart_path)

        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(data_path, index=False)
    except Exception:
        _restore_file(config_path, config_existed, config_backup)
        _restore_file(chart_path, chart_existed, chart_backup)
        _restore_file(data_path, data_existed, data_backup)
        raise

    return {
        "instrument_type": instrument_type,
        "config_path": str(path),
        "data_path": str(data_path),
        "chart_path": str(chart_path),
    }
