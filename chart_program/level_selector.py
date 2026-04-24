from __future__ import annotations

import argparse
import importlib.util
import json
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


def _session_path(config_path: Path) -> Path:
    return Path("data/sessions") / f"{config_path.stem}.json"


def _load_session_state(config_path: Path) -> dict:
    path = _session_path(config_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_session_state(config_path: Path, values: dict):
    path = _session_path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = {k: v for k, v in (values or {}).items() if k != "__finished__"}
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _infer_forex_pip_size(pair: str) -> float:
    pair_upper = (pair or "").upper().replace("/", "")
    return 0.01 if "JPY" in pair_upper else 0.0001


def _resolve_stock_name(symbol: str, fallback_target: str) -> str:
    overrides = {
        "ENA.WA": "Enea",
    }
    key = (symbol or "").upper()
    if key in overrides:
        return overrides[key]
    cleaned = (fallback_target or "").replace("_", " ").strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else key


EMERGING_FX = {"PLN", "HUF", "CZK", "TRY", "ZAR", "MXN", "BRL", "CLP", "INR", "THB", "ILS", "RON"}
COMMODITY_SPECS = {
    "GOLD": {"contract_size": 100, "pip_size": 0.01, "leverage": 20},
    "XAUUSD": {"contract_size": 100, "pip_size": 0.01, "leverage": 20},
    "XAU/USD": {"contract_size": 100, "pip_size": 0.01, "leverage": 20},
    "SILVER": {"contract_size": 5000, "pip_size": 0.01, "leverage": 10},
    "XAGUSD": {"contract_size": 5000, "pip_size": 0.01, "leverage": 10},
    "COCOA": {"contract_size": 10, "pip_size": 0.001, "leverage": 10},
    "CC.F": {"contract_size": 10, "pip_size": 0.001, "leverage": 10},
    "COFFEE": {"contract_size": 37500, "pip_size": 0.01, "leverage": 10},
    "KC.F": {"contract_size": 37500, "pip_size": 0.01, "leverage": 10},
    "SUGAR": {"contract_size": 112000, "pip_size": 0.0001, "leverage": 10},
    "SB.F": {"contract_size": 112000, "pip_size": 0.0001, "leverage": 10},
    "COTTON": {"contract_size": 50000, "pip_size": 0.0001, "leverage": 10},
    "CT.F": {"contract_size": 50000, "pip_size": 0.0001, "leverage": 10},
    "WHEAT": {"contract_size": 5000, "pip_size": 0.25, "leverage": 10},
    "ZW.F": {"contract_size": 5000, "pip_size": 0.25, "leverage": 10},
}


def _fx_to_pln_rate(currency: str, data_source: str, api_key: str | None) -> float:
    curr = (currency or "").upper().replace("/", "")
    if curr == "PLN":
        return 1.0
    pair = f"{curr}/PLN"
    df, _, _ = load_or_update_daily_data(symbol=pair, instrument_type="forex", persist=False, api_key=api_key, data_source=data_source)
    close = float(df.iloc[-1]["Close"])
    return close


def _compute_margin_defaults(instrument_type: str, symbol: str, source_ticker: str | None, price: float, data_source: str, api_key: str | None):
    if price <= 0:
        return None, None

    if instrument_type == "commodity":
        candidates = [
            (symbol or "").upper().replace(" ", ""),
            (source_ticker or "").upper().replace(" ", ""),
        ]
        spec = None
        for key in candidates:
            if key in COMMODITY_SPECS:
                spec = COMMODITY_SPECS[key]
                break
        if spec is None:
            spec = {"contract_size": 100, "pip_size": 0.01, "leverage": 10}
        contract_size = spec["contract_size"]
        leverage = spec["leverage"]
        margin_currency_to_pln = _fx_to_pln_rate("USD", data_source, api_key)
        pip_size = spec["pip_size"]
        quote_to_pln = margin_currency_to_pln
    elif instrument_type == "forex":
        pair = (symbol or "").upper()
        compact = pair.replace("/", "")
        if len(compact) < 6:
            return None, None
        base = compact[:3]
        quote = compact[3:6]
        contract_size = 100000
        leverage = 20 if (base in EMERGING_FX or quote in EMERGING_FX) else 30
        margin_currency_to_pln = _fx_to_pln_rate(base, data_source, api_key)
        pip_size = _infer_forex_pip_size(pair)
        quote_to_pln = _fx_to_pln_rate(quote, data_source, api_key)
    else:
        return None, None

    notional_value = price * contract_size
    deposit_margin = notional_value / leverage
    lot_cost = deposit_margin * margin_currency_to_pln
    pip_value = (contract_size * pip_size) * quote_to_pln
    return round(lot_cost, 2), round(pip_value, 2)


def run_level_selector(raw_args=None):
    args = _parse_args(raw_args)

    maybe_config_path = Path(args.config) if args.config else None
    instrument_type = args.instrument or detect_instrument_type(args.target, maybe_config_path)

    target_base_slug = None
    inferred_position = None

    if maybe_config_path:
        config_path = maybe_config_path
    else:
        target_slug = args.target
        if instrument_type in ("commodity", "forex"):
            lowered = target_slug.lower()
            suffix_pos = "long"
            base_slug = lowered
            if lowered.endswith("_long"):
                suffix_pos = "long"
                base_slug = lowered[: -len("_long")]
            elif lowered.endswith("_short"):
                suffix_pos = "short"
                base_slug = lowered[: -len("_short")]
            pos = (args.position_type or suffix_pos).lower()
            pos = "short" if pos == "short" else "long"
            target_base_slug = base_slug
            inferred_position = pos
            target_slug = f"{base_slug}_{pos}"
        config_path = resolve_config_path(instrument_type, target_slug)

    existing = _load_existing_config_values(config_path)
    session_state = _load_session_state(config_path)
    if session_state:
        existing.update(session_state)

    if instrument_type == "forex":
        symbol = existing.get("pair", args.target if "/" in args.target else f"{args.target[:3].upper()}/{args.target[3:6].upper()}")
    elif instrument_type == "stock":
        symbol = existing.get("symbol", args.target.upper() if "." in args.target else f"{args.target.upper()}.WA")
    else:
        symbol = existing.get("name", args.target.upper())

    df, data_path, fetch_info = load_or_update_daily_data(
        symbol=symbol,
        instrument_type=instrument_type,
        persist=True,
        api_key=args.api_key,
        data_source=args.data_source,
    )

    if instrument_type in ("commodity", "forex"):
        last_close = float(df.iloc[-1]["Close"]) if not df.empty else 0.0
        lot_cost_auto, pip_value_auto = _compute_margin_defaults(
            instrument_type=instrument_type,
            symbol=symbol,
            source_ticker=fetch_info.get("symbol"),
            price=last_close,
            data_source=args.data_source,
            api_key=args.api_key,
        )
        if lot_cost_auto is not None:
            existing["lot_cost"] = lot_cost_auto
        if pip_value_auto is not None:
            existing["pip_value"] = pip_value_auto

    ui = ChartLevelSelectorUI(
        symbol=symbol,
        dataframe=df,
        instrument_type=instrument_type,
        preset_values=existing,
        source_ticker=fetch_info.get("symbol"),
        source_name=fetch_info.get("name"),
    )
    selected = ui.run()
    _save_session_state(config_path, selected)


    if not selected.get("__finished__"):
        return {
            "instrument_type": instrument_type,
            "config_path": None,
            "data_path": str(data_path),
            "chart_path": None,
            "data_source": fetch_info.get("source"),
            "data_symbol": fetch_info.get("symbol"),
            "data_name": fetch_info.get("name"),
            "message": f"No changes saved (Finish was not clicked). Downloaded data was cached: {data_path}",
        }

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
        values.update({"name": _resolve_stock_name(symbol, args.target), "symbol": symbol})
    elif instrument_type == "commodity":
        chosen_pos = selected.get("position_type", args.position_type or inferred_position or "long")
        chosen_pos = "short" if str(chosen_pos).lower() == "short" else "long"
        values.update(
            {
                "name": symbol,
                "position_type": chosen_pos,
                "lot_cost": selected.get("lot_cost", args.lot_cost),
                "pip_value": selected.get("pip_value", args.pip_value),
                "spread": selected.get("spread", selected.get("spread_multiplier", args.spread) * selected.get("pip_value", args.pip_value)),
                "spread_multiplier": selected.get("spread_multiplier", args.spread),
            }
        )
    else:
        pair = symbol
        auto_pip_size = _infer_forex_pip_size(pair)
        chosen_pos = selected.get("position_type", args.position_type or inferred_position or "long")
        chosen_pos = "short" if str(chosen_pos).lower() == "short" else "long"
        values.update(
            {
                "pair": pair,
                "position_type": chosen_pos,
                "lot_cost": selected.get("lot_cost", args.lot_cost),
                "pip_value": selected.get("pip_value", args.pip_value),
                "spread": selected.get("spread", selected.get("spread_multiplier", args.spread) * selected.get("pip_value", args.pip_value)),
                "spread_multiplier": selected.get("spread_multiplier", args.spread),
                "pip_size": auto_pip_size,
            }
        )

    final_config_path = config_path
    if not maybe_config_path and instrument_type in ("commodity", "forex") and target_base_slug:
        final_position = values.get("position_type", inferred_position or "long")
        final_config_path = resolve_config_path(instrument_type, f"{target_base_slug}_{final_position}")
        if final_config_path != config_path:
            _save_session_state(final_config_path, selected)

    snapshot_name = f"{final_config_path.stem}_levels.png"
    chart_path = Path("charts") / snapshot_name

    config_existed, config_backup = _snapshot_file(final_config_path)
    chart_existed, chart_backup = _snapshot_file(chart_path)
    data_existed, data_backup = _snapshot_file(data_path)

    try:
        path = write_or_update_config(instrument_type=instrument_type, config_path=final_config_path, values=values)
        ui.save_chart_snapshot(selected, chart_path)

        data_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(data_path, index=False)
    except Exception:
        _restore_file(final_config_path, config_existed, config_backup)
        _restore_file(chart_path, chart_existed, chart_backup)
        _restore_file(data_path, data_existed, data_backup)
        raise

    return {
        "instrument_type": instrument_type,
        "config_path": str(path),
        "data_path": str(data_path),
        "chart_path": str(chart_path),
        "data_source": fetch_info.get("source"),
        "data_symbol": fetch_info.get("symbol"),
        "data_name": fetch_info.get("name"),
    }
