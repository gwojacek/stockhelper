from __future__ import annotations

import argparse
import importlib.util
import json
import re
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


def _default_currency_conversion_fee(instrument_type: str, symbol: str) -> bool:
    cleaned = (symbol or "").upper().strip()
    if instrument_type == "stock":
        return not cleaned.endswith(".WA") and not cleaned.endswith(".PL")
    if instrument_type == "forex":
        compact = cleaned.replace("/", "")
        return "PLN" not in compact
    return False


def _resolve_stock_name(symbol: str, fallback_target: str) -> str:
    overrides = {
        "ENA.WA": "Enea",
        "MBR.WA": "Mobruk",
        "ALGT.US": "Allegiant Travel Company",
        "ALGT": "Allegiant Travel Company",
    }
    key = (symbol or "").upper()
    if key in overrides:
        return overrides[key]
    cleaned = (fallback_target or "").replace("_", " ").strip()
    return cleaned[:1].upper() + cleaned[1:] if cleaned else key


EMERGING_FX = {"PLN", "HUF", "CZK", "TRY", "ZAR", "MXN", "BRL", "CLP", "INR", "THB", "ILS", "RON"}
COMMODITY_BROKER_DEFAULTS = {
    "COCOA": {"lot_cost": 12379.74, "pip_value": 36.19},
    "COFFEE": {"lot_cost": 218982.66, "pip_value": 7238.10},
    "CORN": {"lot_cost": 84096.38, "pip_value": 1809.58},
    "COTTON": {"lot_cost": 14326.01, "pip_value": 1809.58},
    "SOYBEAN": {"lot_cost": 127757.99, "pip_value": 1085.78},
    "SOYOIL": {"lot_cost": 15439.26, "pip_value": 2171.73},
    "SOYBEAN_OIL": {"lot_cost": 15439.26, "pip_value": 2171.73},
    "SUGAR": {"lot_cost": 5671.09, "pip_value": 4053.34},
    "WHEAT": {"lot_cost": 89524.98, "pip_value": 1447.54},
    "GASOLINE": {"lot_cost": 49926.79, "pip_value": 15.20},
    "LSGASOIL": {"lot_cost": 41536.61, "pip_value": 361.86},
    "NATGAS": {"lot_cost": 29202.51, "pip_value": 108556.50},
    "NATURAL_GAS": {"lot_cost": 29202.51, "pip_value": 108556.50},
    "OIL.WTI": {"lot_cost": 34226.14, "pip_value": 3618.85},
    "WTI": {"lot_cost": 34226.14, "pip_value": 3618.85},
    "OIL": {"lot_cost": 35631.20, "pip_value": 3618.75},
    "ALUMINIUM": {"lot_cost": 65265.96, "pip_value": 180.94},
    "COPPER": {"lot_cost": 144260.73, "pip_value": 108.56},
    "NICKEL": {"lot_cost": 67963.47, "pip_value": 36.18},
    "ZINC": {"lot_cost": 63049.75, "pip_value": 180.92},
    "GOLD": {"lot_cost": 85171.26, "pip_value": 361.86},
    "XAUUSD": {"lot_cost": 85171.26, "pip_value": 361.86},
    "XAU/USD": {"lot_cost": 85171.26, "pip_value": 361.86},
    "PALLADIUM": {"lot_cost": 53950.45, "pip_value": 361.87},
    "PLATINUM": {"lot_cost": 108511.94, "pip_value": 542.72},
    "SILVER": {"lot_cost": 137626.31, "pip_value": 18100.75},
    "XAGUSD": {"lot_cost": 137626.31, "pip_value": 18100.75},
}
INDEX_BROKER_DEFAULTS = {
    "BRACOMP": {"lot_cost": 136461.58, "pip_value": 7.28, "spread_multiplier": 75.0},
    "US500": {"lot_cost": 65323.11, "pip_value": 182.08, "spread_multiplier": 0.7},
    "MEXCOMP": {"lot_cost": 73245.18, "pip_value": 10.92, "spread_multiplier": 131.0},
    "VIX": {"lot_cost": 58874.96, "pip_value": 14565.40, "spread_multiplier": 0.2},
    "US30": {"lot_cost": 44540.05, "pip_value": 18.21, "spread_multiplier": 3.0},
    "US100": {"lot_cost": 99716.59, "pip_value": 72.83, "spread_multiplier": 1.54},
    "HK.CASH": {"lot_cost": 46948.38, "pip_value": 18.21, "spread_multiplier": 9.0},
    "SG20CASH": {"lot_cost": 16149.96, "pip_value": 364.13, "spread_multiplier": 0.25},
    "AU200.CASH": {"lot_cost": 28375.68, "pip_value": 65.06, "spread_multiplier": 6.0},
    "CHN.CASH": {"lot_cost": 31609.69, "pip_value": 36.41, "spread_multiplier": 9.0},
    "JP225": {"lot_cost": 33892.18, "pip_value": 11.43, "spread_multiplier": 16.0},
    "W20": {"lot_cost": 6854.00, "pip_value": 20.00, "spread_multiplier": 2.7},
    "WIG20": {"lot_cost": 6854.00, "pip_value": 20.00, "spread_multiplier": 2.7},
    "UK100": {"lot_cost": 25364.12, "pip_value": 49.18, "spread_multiplier": 2.1},
    "ITA40": {"lot_cost": 100279.33, "pip_value": 21.30, "spread_multiplier": 23.0},
    "DE40": {"lot_cost": 128369.90, "pip_value": 106.48, "spread_multiplier": 1.7},
    "FRA40": {"lot_cost": 16953.20, "pip_value": 42.59, "spread_multiplier": 1.9},
    "NED25": {"lot_cost": 85112.27, "pip_value": 851.77, "spread_multiplier": 0.21},
    "SUI20": {"lot_cost": 94820.75, "pip_value": 72.83, "spread_multiplier": 5.0},
    "SPA35": {"lot_cost": 74994.09, "pip_value": 42.59, "spread_multiplier": 8.0},
    "EU50": {"lot_cost": 12273.00, "pip_value": 43.00, "spread_multiplier": 2.8},
}
INDEX_DISPLAY_NAMES = {
    "JP225": "Nikkei 225",
    "NKX": "Nikkei 225",
    "^NKX": "Nikkei 225",
}
COMMODITY_TICKER_ALIASES = {
    "GC=F": "GOLD",
    "SI=F": "SILVER",
    "PA=F": "PALLADIUM",
    "PL=F": "PLATINUM",
    "CC=F": "COCOA",
    "KC=F": "COFFEE",
    "SB=F": "SUGAR",
    "CT=F": "COTTON",
    "ZC=F": "CORN",
    "ZW=F": "WHEAT",
    "ZS=F": "SOYBEAN",
    "ZL=F": "SOYOIL",
    "CL=F": "OIL.WTI",
    "BZ=F": "OIL",
    "RB=F": "GASOLINE",
    "NG=F": "NATGAS",
    "HG=F": "COPPER",
    "ALI=F": "ALUMINIUM",
    "CC.F": "COCOA",
    "KC.F": "COFFEE",
    "SB.F": "SUGAR",
    "CT.F": "COTTON",
    "ZC.F": "CORN",
    "ZW.F": "WHEAT",
    "ZS.F": "SOYBEAN",
    "ZL.F": "SOYOIL",
    "CL.F": "OIL.WTI",
    "CB.F": "OIL",
    "RB.F": "GASOLINE",
    "NG.F": "NATGAS",
    "QS.F": "LSGASOIL",
    "ALI.F": "ALUMINIUM",
    "NI.F": "NICKEL",
    "ZN.F": "ZINC",
    "^BVP": "BRACOMP",
    "^SPX": "US500",
    "^IPC": "MEXCOMP",
    "VI.C": "VIX",
    "^DJI": "US30",
    "^NDX": "US100",
    "^HSI": "HK.CASH",
    "^STI": "SG20CASH",
    "^AOR": "AU200.CASH",
    "0EL.C": "CHN.CASH",
    "^NKX": "JP225",
    "^UKX": "UK100",
    "^FMIB": "ITA40",
    "^DAX": "DE40",
    "^CAC": "FRA40",
    "^AEX": "NED25",
    "^SMI": "SUI20",
    "^IBEX": "SPA35",
    "FX.F": "EU50",
}


def _commodity_candidates(symbol: str, source_ticker: str | None) -> list[str]:
    candidates = [
        (symbol or "").upper().replace(" ", ""),
        (source_ticker or "").upper().replace(" ", ""),
    ]
    expanded = list(candidates)
    for key in candidates:
        aliased = COMMODITY_TICKER_ALIASES.get(key)
        if aliased:
            expanded.append(aliased)
        if key.endswith(".F"):
            expanded.append(key.replace(".F", "=F"))
        if key.endswith("=F"):
            expanded.append(key.replace("=F", ".F"))
    return [c for c in expanded if c]


def _index_defaults(symbol: str, source_ticker: str | None) -> dict | None:
    for key in _commodity_candidates(symbol, source_ticker):
        default = INDEX_BROKER_DEFAULTS.get(key)
        if default:
            return default
    return None


def _display_identity(symbol: str, source_ticker: str | None, searched_target: str) -> tuple[str | None, str | None]:
    searched = (searched_target or "").strip().upper()
    for key in _commodity_candidates(symbol, source_ticker):
        nice_name = INDEX_DISPLAY_NAMES.get(key)
        if nice_name:
            canonical = (source_ticker or "").upper() or key
            lookup = searched or key
            if canonical == lookup:
                return nice_name, canonical
            return nice_name, f"{canonical} / {lookup}"
    return None, source_ticker

COMMODITY_SPECS = {
    "GOLD": {"contract_size": 100, "pip_contract_size": 100, "pip_size": 1.0, "leverage": 20},
    "XAUUSD": {"contract_size": 100, "pip_contract_size": 100, "pip_size": 1.0, "leverage": 20},
    "XAU/USD": {"contract_size": 100, "pip_contract_size": 100, "pip_size": 1.0, "leverage": 20},
    "SILVER": {"contract_size": 5000, "pip_contract_size": 5000, "pip_size": 1.0, "leverage": 10},
    "XAGUSD": {"contract_size": 5000, "pip_contract_size": 5000, "pip_size": 1.0, "leverage": 10},
    "PALLADIUM": {"contract_size": 100, "pip_contract_size": 100, "pip_size": 1.0, "leverage": 10},
    "XPDUSD": {"contract_size": 100, "pip_contract_size": 100, "pip_size": 1.0, "leverage": 10},
    "PLATINUM": {"contract_size": 150, "pip_contract_size": 150, "pip_size": 1.0, "leverage": 10},
    "PL.F": {"contract_size": 150, "pip_contract_size": 150, "pip_size": 1.0, "leverage": 10},
    "COCOA": {"contract_size": 10, "pip_contract_size": 10, "pip_size": 1.0, "leverage": 10},
    "CC.F": {"contract_size": 10, "pip_contract_size": 10, "pip_size": 1.0, "leverage": 10},
    "COFFEE": {"contract_size": 2000, "pip_contract_size": 2000, "pip_size": 1.0, "leverage": 10},
    "KC.F": {"contract_size": 2000, "pip_contract_size": 2000, "pip_size": 1.0, "leverage": 10},
    "SUGAR": {"contract_size": 1120, "pip_contract_size": 1120, "pip_size": 1.0, "leverage": 10},
    "SB.F": {"contract_size": 1120, "pip_contract_size": 1120, "pip_size": 1.0, "leverage": 10},
    "COTTON": {"contract_size": 500, "pip_contract_size": 500, "pip_size": 1.0, "leverage": 10},
    "CT.F": {"contract_size": 500, "pip_contract_size": 500, "pip_size": 1.0, "leverage": 10},
    "CORN": {"contract_size": 500, "pip_contract_size": 500, "pip_size": 1.0, "leverage": 10},
    "ZC.F": {"contract_size": 500, "pip_contract_size": 500, "pip_size": 1.0, "leverage": 10},
    "WHEAT": {"contract_size": 400, "pip_contract_size": 400, "pip_size": 1.0, "leverage": 10},
    "ZW.F": {"contract_size": 400, "pip_contract_size": 400, "pip_size": 1.0, "leverage": 10},
    "SOYBEAN": {"contract_size": 300, "pip_contract_size": 300, "pip_size": 1.0, "leverage": 10},
    "ZS.F": {"contract_size": 300, "pip_contract_size": 300, "pip_size": 1.0, "leverage": 10},
    "SOYOIL": {"contract_size": 600, "pip_contract_size": 600, "pip_size": 1.0, "leverage": 10},
    "SOYBEAN_OIL": {"contract_size": 600, "pip_contract_size": 600, "pip_size": 1.0, "leverage": 10},
    "ZL.F": {"contract_size": 600, "pip_contract_size": 600, "pip_size": 1.0, "leverage": 10},
    "OIL": {"contract_size": 1000, "pip_contract_size": 1000, "pip_size": 1.0, "leverage": 10},
    "OIL.WTI": {"contract_size": 1000, "pip_contract_size": 1000, "pip_size": 1.0, "leverage": 10},
    "WTI": {"contract_size": 1000, "pip_contract_size": 1000, "pip_size": 1.0, "leverage": 10},
    "CL=F": {"contract_size": 1000, "pip_contract_size": 1000, "pip_size": 1.0, "leverage": 10},
    "GASOLINE": {"contract_size": 420, "pip_contract_size": 420, "pip_size": 0.01, "leverage": 10},
    "RB.F": {"contract_size": 420, "pip_contract_size": 420, "pip_size": 0.01, "leverage": 10},
    "LSGASOIL": {"contract_size": 100, "pip_contract_size": 100, "pip_size": 1.0, "leverage": 10},
    "NATGAS": {"contract_size": 30000, "pip_contract_size": 30000, "pip_size": 1.0, "leverage": 10},
    "NATURAL_GAS": {"contract_size": 30000, "pip_contract_size": 30000, "pip_size": 1.0, "leverage": 10},
    "NG.F": {"contract_size": 30000, "pip_contract_size": 30000, "pip_size": 1.0, "leverage": 10},
    "ALUMINIUM": {"contract_size": 50, "pip_contract_size": 50, "pip_size": 1.0, "leverage": 10},
    "COPPER": {"contract_size": 30, "pip_contract_size": 30, "pip_size": 1.0, "leverage": 10},
    "HG=F": {"contract_size": 30, "pip_contract_size": 30, "pip_size": 1.0, "leverage": 10},
    "NICKEL": {"contract_size": 10, "pip_contract_size": 10, "pip_size": 1.0, "leverage": 10},
    "ZINC": {"contract_size": 50, "pip_contract_size": 50, "pip_size": 1.0, "leverage": 10},
    # Crypto CFDs (XTB-like): 1 BTC lot, but 300 DOGE minimum lot.
    "BTC": {"contract_size": 1, "pip_contract_size": 1, "pip_size": 1.0, "leverage": 2},
    "DOGE": {"contract_size": 300, "pip_contract_size": 300, "pip_size": 1.0, "leverage": 2},
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
        candidates = _commodity_candidates(symbol, source_ticker)
        for key in candidates:
            fixed = COMMODITY_BROKER_DEFAULTS.get(key)
            if fixed:
                return round(fixed["lot_cost"], 2), round(fixed["pip_value"], 2)
        spec = None
        for key in candidates:
            if key in COMMODITY_SPECS:
                spec = COMMODITY_SPECS[key]
                break
        if spec is None:
            spec = {"contract_size": 100, "pip_contract_size": 100, "pip_size": 0.01, "leverage": 10}
        contract_size = spec["contract_size"]
        pip_contract_size = spec.get("pip_contract_size", contract_size)
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
        pip_contract_size = contract_size
        leverage = 20 if (base in EMERGING_FX or quote in EMERGING_FX) else 30
        margin_currency_to_pln = _fx_to_pln_rate(base, data_source, api_key)
        pip_size = _infer_forex_pip_size(pair)
        quote_to_pln = _fx_to_pln_rate(quote, data_source, api_key)
        deposit_margin = contract_size / leverage
        lot_cost = deposit_margin * margin_currency_to_pln
        pip_value = (pip_contract_size * pip_size) * quote_to_pln
        return round(lot_cost, 2), round(pip_value, 2)
    else:
        return None, None

    notional_value = price * contract_size
    deposit_margin = notional_value / leverage
    lot_cost = deposit_margin * margin_currency_to_pln
    pip_value = (pip_contract_size * pip_size) * quote_to_pln
    return round(lot_cost, 2), round(pip_value, 2)


def run_level_selector(raw_args=None):
    args = _parse_args(raw_args)
    target_input = (args.target or "").strip()
    cfd_forced = bool(re.search(r"\s+CFD$", target_input, flags=re.IGNORECASE))
    base_target = re.sub(r"\s+CFD$", "", target_input, flags=re.IGNORECASE).strip()

    maybe_config_path = Path(args.config) if args.config else None
    instrument_type = args.instrument or ("commodity" if cfd_forced else detect_instrument_type(base_target, maybe_config_path))

    target_base_slug = None
    inferred_position = None

    if maybe_config_path:
        config_path = maybe_config_path
    else:
        target_slug = base_target
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
        symbol = existing.get("pair", base_target if "/" in base_target else f"{base_target[:3].upper()}/{base_target[3:6].upper()}")
    elif instrument_type == "stock":
        symbol = existing.get("symbol", base_target.upper() if "." in base_target else f"{base_target.upper()}.WA")
    else:
        symbol = existing.get("name", base_target.upper())
        symbol = re.sub(r"\s+CFD$", "", symbol, flags=re.IGNORECASE).strip()
        if symbol.upper() in {"GOLD", "XAU/USD", "XAUUSD"}:
            symbol = "XAUUSD"

    if instrument_type in ("stock", "forex"):
        if "apply_currency_conversion_fee" not in existing:
            existing["apply_currency_conversion_fee"] = _default_currency_conversion_fee(instrument_type, symbol)
        existing["currency_conversion_fee_pct"] = float(existing.get("currency_conversion_fee_pct", 0.01) or 0.01)
        existing["__currency_fee_eligible__"] = _default_currency_conversion_fee(instrument_type, symbol)

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
        index_defaults = _index_defaults(symbol, fetch_info.get("symbol"))
        if index_defaults:
            existing["lot_cost"] = round(index_defaults["lot_cost"], 2)
            existing["pip_value"] = round(index_defaults["pip_value"], 2)
            existing["spread_multiplier"] = round(index_defaults["spread_multiplier"], 4)
            existing["spread"] = round(existing["spread_multiplier"] * existing["pip_value"], 2)

    display_name, display_ticker = _display_identity(symbol, fetch_info.get("symbol"), base_target)

    ui = ChartLevelSelectorUI(
        symbol=symbol,
        dataframe=df,
        instrument_type=instrument_type,
        preset_values=existing,
        source_ticker=display_ticker,
        source_name=display_name or fetch_info.get("name"),
        source_provider=fetch_info.get("source"),
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
            "data_fallback_reason": fetch_info.get("fallback_reason"),
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
        values.update({"name": _resolve_stock_name(symbol, base_target), "symbol": symbol})
        if _default_currency_conversion_fee("stock", symbol):
            values.update(
                {
                    "apply_currency_conversion_fee": bool(selected.get("apply_currency_conversion_fee", existing.get("apply_currency_conversion_fee", False))),
                    "currency_conversion_fee_pct": float(selected.get("currency_conversion_fee_pct", existing.get("currency_conversion_fee_pct", 0.01))),
                }
            )
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
                "apply_currency_conversion_fee": bool(selected.get("apply_currency_conversion_fee", existing.get("apply_currency_conversion_fee", False))),
                "currency_conversion_fee_pct": float(selected.get("currency_conversion_fee_pct", existing.get("currency_conversion_fee_pct", 0.01))),
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
        "data_fallback_reason": fetch_info.get("fallback_reason"),
    }
