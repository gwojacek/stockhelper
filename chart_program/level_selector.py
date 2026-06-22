from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from chart_program.chart_loader import load_or_update_daily_data
from chart_program.lightweight_chart_ui import LightweightChartLevelSelectorUI
from chart_program.config_writer import resolve_config_path, write_or_update_config
from chart_program.instrument_detector import detect_instrument_type




def _trim_chart_window(df: pd.DataFrame, max_days: int = 548) -> pd.DataFrame:
    if df is None or df.empty or "Date" not in df.columns:
        return df
    out = df.copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    if out.empty:
        return out
    latest = out["Date"].max()
    cutoff = latest - pd.Timedelta(days=max_days)
    trimmed = out[out["Date"] >= cutoff].reset_index(drop=True)
    return trimmed if not trimmed.empty else out.tail(min(len(out), 400)).reset_index(drop=True)
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
    parser.add_argument("--ichimoku-mode", choices=["on", "off"], default="off")
    parser.add_argument("--fibo-lines", type=int, default=0)
    parser.add_argument("--fibo-anchor-start")
    parser.add_argument("--fibo-anchor-end")
    parser.add_argument("--fibo-right", action="store_true")
    parser.add_argument("--wedge-lines", action="store_true")
    parser.add_argument("--wedge-upper-start")
    parser.add_argument("--wedge-upper-end")
    parser.add_argument("--wedge-lower-start")
    parser.add_argument("--wedge-lower-end")
    parser.add_argument("--wedge-right", action="store_true")
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
    return PROJECT_ROOT / "data" / "state" / "sessions" / f"{config_path.stem}.json"


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


def _display_identity(symbol: str, source_ticker: str | None, searched_target: str, resolved_name: str | None) -> tuple[str | None, str | None]:
    searched = (searched_target or "").strip().upper()
    canonical = (source_ticker or "").upper() or (symbol or "").upper()
    canonical_alias = COMMODITY_TICKER_ALIASES.get(canonical)

    if resolved_name:
        lookup = searched or canonical_alias or canonical
        if canonical == lookup and canonical_alias:
            return resolved_name, f"{canonical} / {canonical_alias}"
        if canonical == lookup:
            return resolved_name, canonical
        return resolved_name, f"{canonical} / {lookup}"
    for key in _commodity_candidates(symbol, source_ticker):
        canonical = (source_ticker or "").upper() or key
        lookup = searched or key
        if canonical == lookup:
            return None, canonical
        return None, f"{canonical} / {lookup}"
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
        if instrument_type == "stock":
            target_slug = re.sub(r"\.(WA|PL)$", "", target_slug, flags=re.IGNORECASE)
        config_path = resolve_config_path(instrument_type, target_slug)

    existing = _load_existing_config_values(config_path)
    session_state = _load_session_state(config_path)
    if session_state:
        existing.update(session_state)
    if cfd_forced:
        existing["__stock_cfd_mode__"] = True
        existing["__stock_cfd_forced__"] = True

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

    # First do a bounded latest-candle refresh with normal cache rules.
    # Search reports can discover a Yahoo candle before the bulk Stooq cache has
    # it; opening the chart should persist that newest candle instead of showing
    # an older cache-only view.
    prev_cache_only = os.environ.get("STOCKHELPER_CACHE_ONLY")
    try:
        os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
        _latest_df, data_path, latest_fetch_info = load_or_update_daily_data(
            symbol=symbol,
            instrument_type=instrument_type,
            persist=True,
            api_key=args.api_key,
            data_source=args.data_source,
            fetch_older_data=False,
        )

        # Then load the full cached history for charting without another remote
        # backfill.  The latest refresh above owns persistence; this cache-only
        # read is intentionally just for display/calculation history.
        os.environ["STOCKHELPER_CACHE_ONLY"] = "1"
        df, data_path, fetch_info = load_or_update_daily_data(
            symbol=symbol,
            instrument_type=instrument_type,
            persist=True,
            api_key=args.api_key,
            data_source=args.data_source,
            fetch_older_data=True,
        )
        fetch_info["source"] = "local_csv"
        fetch_info.setdefault("latest_refresh_source", latest_fetch_info.get("source"))
        fetch_info.setdefault("latest_refresh_reason", latest_fetch_info.get("fallback_reason"))
    finally:
        if prev_cache_only is None:
            os.environ.pop("STOCKHELPER_CACHE_ONLY", None)
        else:
            os.environ["STOCKHELPER_CACHE_ONLY"] = prev_cache_only
    existing["__show_ichimoku__"] = bool(args.ichimoku_mode == "on")

    # Chart UI should remain responsive: render at most ~2 years from latest bar.
    df = _trim_chart_window(df, max_days=548)

    if args.fibo_lines and args.fibo_anchor_start and args.fibo_anchor_end:
        try:
            s_ts = pd.to_datetime(args.fibo_anchor_start, errors="coerce")
            e_ts = pd.to_datetime(args.fibo_anchor_end, errors="coerce")
            if not pd.isna(s_ts) and not pd.isna(e_ts):
                dts = pd.to_datetime(df["Date"], errors="coerce")
                s_idx = int((dts - s_ts).abs().idxmin())
                e_idx = int((dts - e_ts).abs().idxmin())
                s_row = df.iloc[s_idx]
                e_row = df.iloc[e_idx]

                def _row_price(row, field: str, fallback: float = 0.0) -> float:
                    return float(row.get(field, row.get("Close", fallback)))

                def _row_mid(row) -> float:
                    return (_row_price(row, "Low") + _row_price(row, "High")) / 2.0

                is_short = _row_mid(e_row) < _row_mid(s_row)
                if is_short:
                    high_price = round(_row_price(s_row, "High"), 5)
                    low_price = round(_row_price(e_row, "Low"), 5)
                else:
                    low_price = round(_row_price(s_row, "Low"), 5)
                    high_price = round(_row_price(e_row, "High"), 5)

                x_start = pd.to_datetime(s_row["Date"], errors="coerce")
                x_end_raw = pd.to_datetime(e_row["Date"], errors="coerce")
                # Keep parity with the manual Fib tool: start the second-anchor lines
                # about two candles to the left, but keep the exact same Y levels.
                try:
                    e_idx_left = max(0, e_idx - 2)
                    e_row_left = df.iloc[e_idx_left]
                    x_end_left = pd.to_datetime(e_row_left["Date"], errors="coerce")
                    x_end = x_end_left if not pd.isna(x_end_left) else x_end_raw
                except Exception:
                    x_end = x_end_raw
                x_right = pd.to_datetime(df.iloc[-1]["Date"], errors="coerce")
                if pd.isna(x_start):
                    x_start = s_ts
                if pd.isna(x_end):
                    x_end = e_ts
                if pd.isna(x_right):
                    x_right = e_ts
                span = abs(x_end - x_start)
                if span == pd.Timedelta(0):
                    span = pd.Timedelta(days=7)
                extension = max(span * 6, pd.Timedelta(days=2880))
                x_common_end = x_right + extension if args.fibo_right else x_right
                levels = [0.0, 0.382, 0.5, 0.618, 1.0][: max(1, min(args.fibo_lines, 5))]
                fib_color = '#64748b'
                fib_golden_color = '#facc15'
                objs = []
                gid = "auto-fibo"
                delta = high_price - low_price
                for idx, r in enumerate(levels):
                    pct_label = f"FIB {r*100:.1f}%".replace(".0%", "%")
                    y_val = round(low_price + delta * r, 5) if is_short else round(high_price - delta * r, 5)
                    interp_idx = int(round(s_idx + (e_idx - s_idx) * (1.0 - r)))
                    interp_idx = max(0, min(len(df) - 1, interp_idx))
                    x_level_start = pd.to_datetime(df.iloc[interp_idx]["Date"], errors="coerce")
                    x0_txt = str(pd.to_datetime(x_level_start, errors="coerce").date()) if not pd.isna(pd.to_datetime(x_level_start, errors="coerce")) else str(s_row["Date"])
                    x1_txt = str(pd.to_datetime(x_common_end, errors="coerce").date()) if not pd.isna(pd.to_datetime(x_common_end, errors="coerce")) else str(df.iloc[-1]["Date"])
                    objs.append({
                        "id": f"auto-fibo-{int(r*1000)}",
                        "type": "fib",
                        "label": f"{pct_label} ({y_val})",
                        "x0": x0_txt,
                        "x1": x1_txt,
                        "y0": y_val,
                        "y1": y_val,
                        "price": y_val,
                        "color": fib_golden_color if r == 0.618 else fib_color,
                        "group_id": gid,
                        "direction": "short" if is_short else "long",
                    })
                objs.append({
                    "id": "auto-fibo-boundary",
                    "type": "fib-boundary",
                    "label": "FIB anchor",
                    "x0": str(pd.to_datetime(x_start, errors="coerce").date()) if not pd.isna(pd.to_datetime(x_start, errors="coerce")) else str(s_row["Date"]),
                    "x1": str(pd.to_datetime(x_end_raw, errors="coerce").date()) if not pd.isna(pd.to_datetime(x_end_raw, errors="coerce")) else str(e_row["Date"]),
                    "y0": round(high_price if is_short else low_price, 5),
                    "y1": round(low_price if is_short else high_price, 5),
                    "color": fib_color,
                    "group_id": gid,
                })
                existing["drawn_objects"] = objs
                print(f"[chart] auto-fibo preloaded: {len(objs) - 1} lines, anchors={args.fibo_anchor_start}->{args.fibo_anchor_end}, direction={'short' if is_short else 'long'}")
        except Exception as exc:
            print(f"[chart] auto-fibo preload failed: {exc}")


    def _saved_wedge_is_active() -> bool:
        objects = existing.get("drawn_objects") if isinstance(existing, dict) else None
        if not isinstance(objects, list) or df.empty:
            return False
        wedges = [obj for obj in objects if isinstance(obj, dict) and (obj.get("type") == "wedge" or obj.get("group_id") == "auto-wedge")]
        if len(wedges) < 2:
            return False
        upper = next((obj for obj in wedges if "upper" in str(obj.get("label", "")).lower()), wedges[0])
        lower = next((obj for obj in wedges if "lower" in str(obj.get("label", "")).lower() and obj is not upper), None)
        if lower is None:
            lower = next((obj for obj in wedges if obj is not upper), None)
        if lower is None:
            return False

        def _anchors(obj):
            ax = obj.get("anchor_x")
            ay = obj.get("anchor_y")
            if isinstance(ax, list) and isinstance(ay, list) and len(ax) >= 2 and len(ay) >= 2:
                return (str(ax[0])[:10], float(ay[0])), (str(ax[1])[:10], float(ay[1]))
            return (str(obj.get("x0"))[:10], float(obj.get("y0"))), (str(obj.get("x1"))[:10], float(obj.get("y1")))

        try:
            up0, up1 = _anchors(upper)
            lo0, lo1 = _anchors(lower)
        except Exception:
            return False
        dates = [str(pd.to_datetime(d).date()) for d in df["Date"]]
        idx_by_date = {d: i for i, d in enumerate(dates)}
        if up0[0] not in idx_by_date or up1[0] not in idx_by_date or lo0[0] not in idx_by_date or lo1[0] not in idx_by_date:
            return False
        upper_a = (idx_by_date[up0[0]], up0[1]); upper_b = (idx_by_date[up1[0]], up1[1])
        lower_a = (idx_by_date[lo0[0]], lo0[1]); lower_b = (idx_by_date[lo1[0]], lo1[1])
        if upper_a[0] == upper_b[0] or lower_a[0] == lower_b[0]:
            return False

        def _line(idx: int, a: tuple[int, float], b: tuple[int, float]) -> float:
            return float(a[1]) + (float(b[1]) - float(a[1])) * ((idx - a[0]) / (b[0] - a[0]))

        closes = pd.to_numeric(df["Close"], errors="coerce").to_numpy()
        highs = pd.to_numeric(df["High"], errors="coerce").to_numpy()
        lows = pd.to_numeric(df["Low"], errors="coerce").to_numpy()
        start_idx = max(min(upper_a[0], upper_b[0]), min(lower_a[0], lower_b[0]))
        breakout_idx = None
        breakout_direction = None
        for idx in range(start_idx, len(df)):
            close = closes[idx]
            if pd.isna(close):
                continue
            up = _line(idx, upper_a, upper_b)
            lo = _line(idx, lower_a, lower_b)
            eps = max(abs(float(close)) * 1e-6, 1e-9)
            if close > up + eps or close < lo - eps:
                direction = "long" if close > up + eps else "short"
                if idx < len(df) - 6:
                    return False
                if breakout_idx is None:
                    breakout_idx = idx
                    breakout_direction = direction
                elif direction != breakout_direction:
                    return False
            if breakout_idx is not None and idx > breakout_idx:
                breakout_up = _line(breakout_idx, upper_a, upper_b)
                breakout_lo = _line(breakout_idx, lower_a, lower_b)
                probable_stop = (breakout_up + breakout_lo) / 2.0
                stop_eps = max(abs(float(probable_stop)) * 1e-6, eps)
                if breakout_direction == "long" and not pd.isna(lows[idx]) and float(lows[idx]) <= probable_stop + stop_eps:
                    return False
                if breakout_direction == "short" and not pd.isna(highs[idx]) and float(highs[idx]) >= probable_stop - stop_eps:
                    return False
        return True

    if args.wedge_lines:
        try:
            if _saved_wedge_is_active():
                print("[chart] kept saved manual wedge lines (active/recent breakout)")
                raise StopIteration

            def _parse_wedge_point(raw: str | None) -> tuple[pd.Timestamp, float] | None:
                if not raw or "," not in raw:
                    return None
                d_txt, p_txt = raw.split(",", 1)
                ts = pd.to_datetime(d_txt.strip(), errors="coerce")
                if pd.isna(ts):
                    return None
                return ts, float(p_txt.strip())

            up0 = _parse_wedge_point(args.wedge_upper_start)
            up1 = _parse_wedge_point(args.wedge_upper_end)
            lo0 = _parse_wedge_point(args.wedge_lower_start)
            lo1 = _parse_wedge_point(args.wedge_lower_end)
            if up0 and up1 and lo0 and lo1:
                chart_dates = pd.to_datetime(df["Date"], errors="coerce").reset_index(drop=True) if not df.empty else pd.Series(dtype="datetime64[ns]")
                has_weekend_data = bool((chart_dates.dt.weekday >= 5).any()) if not chart_dates.empty else False

                def _nearest_idx(ts: pd.Timestamp) -> int | None:
                    if chart_dates.empty:
                        return None
                    return int((chart_dates - ts).abs().idxmin())

                def _snap_wedge_anchor(point: tuple[pd.Timestamp, float], side: str) -> tuple[pd.Timestamp, float]:
                    # Report commands can carry rounded prices or be opened with
                    # fresher provider data.  Auto-wedge anchors must still be
                    # glued to the actual candle extremes on the displayed chart.
                    idx = _nearest_idx(point[0])
                    if idx is None or idx < 0 or idx >= len(df):
                        return point
                    row = df.iloc[idx]
                    price_col = "High" if side == "upper" else "Low"
                    price = pd.to_numeric(pd.Series([row.get(price_col)]), errors="coerce").iloc[0]
                    if pd.isna(price):
                        return point
                    return pd.to_datetime(chart_dates.iloc[idx]), float(price)

                up0 = _snap_wedge_anchor(up0, "upper")
                up1 = _snap_wedge_anchor(up1, "upper")
                lo0 = _snap_wedge_anchor(lo0, "lower")
                lo1 = _snap_wedge_anchor(lo1, "lower")

                def _date_for_index(idx: int) -> pd.Timestamp:
                    if chart_dates.empty:
                        return pd.Timestamp.today().normalize()
                    if 0 <= idx < len(chart_dates):
                        return pd.to_datetime(chart_dates.iloc[idx])
                    last = pd.to_datetime(chart_dates.iloc[-1])
                    extra = idx - (len(chart_dates) - 1)
                    if extra <= 0:
                        return pd.to_datetime(chart_dates.iloc[max(0, idx)])
                    if has_weekend_data:
                        return last + pd.Timedelta(days=extra)
                    return last + pd.tseries.offsets.BDay(extra)

                def _line_price_at_index(p0: tuple[pd.Timestamp, float], p1: tuple[pd.Timestamp, float], idx: int) -> float:
                    i0 = _nearest_idx(p0[0])
                    i1 = _nearest_idx(p1[0])
                    if i0 is None or i1 is None:
                        return float(p0[1])
                    span = i1 - i0
                    if span == 0:
                        span = 1
                    return float(p0[1]) + (float(p1[1]) - float(p0[1])) * ((idx - i0) / span)

                def _slope_intercept(p0: tuple[pd.Timestamp, float], p1: tuple[pd.Timestamp, float]) -> tuple[float, float] | None:
                    i0 = _nearest_idx(p0[0])
                    i1 = _nearest_idx(p1[0])
                    if i0 is None or i1 is None or i0 == i1:
                        return None
                    slope = (float(p1[1]) - float(p0[1])) / (i1 - i0)
                    return slope, float(p0[1]) - slope * i0

                def _wedge_cross_index() -> int | None:
                    upper_line = _slope_intercept(up0, up1)
                    lower_line = _slope_intercept(lo0, lo1)
                    if upper_line is None or lower_line is None:
                        return None
                    upper_slope, upper_intercept = upper_line
                    lower_slope, lower_intercept = lower_line
                    denom = upper_slope - lower_slope
                    if abs(denom) < 1e-9:
                        return None
                    cross_idx = int(math.ceil((lower_intercept - upper_intercept) / denom))
                    last_idx = len(chart_dates) - 1
                    if cross_idx <= last_idx:
                        return None
                    # Keep the line long enough to show the wedge ending/cross, but
                    # cap pathological projections so the chart remains usable.
                    max_projection = last_idx + max(len(chart_dates), 80)
                    return min(cross_idx + 5, max_projection)

                common_wedge_end_idx = _wedge_cross_index() if args.wedge_right else None

                def _line_object_points(p0: tuple[pd.Timestamp, float], p1: tuple[pd.Timestamp, float]) -> tuple[list[str], list[float]]:
                    i0 = _nearest_idx(p0[0])
                    i1 = _nearest_idx(p1[0])
                    if i0 is None or i1 is None:
                        return [str(p0[0].date()), str(p1[0].date())], [round(float(p0[1]), 5), round(float(p1[1]), 5)]
                    first_idx = min(i0, i1)
                    second_idx = max(i0, i1)
                    if args.wedge_right:
                        extension = max(abs(i1 - i0) * 2, 80)
                        fallback_end_idx = (len(chart_dates) - 1) + extension
                        end_idx = max(common_wedge_end_idx or fallback_end_idx, fallback_end_idx)
                    else:
                        end_idx = second_idx
                    # Build a polyline on every trading/index step. With Plotly
                    # rangebreaks this avoids calendar-time interpolation drift and
                    # keeps the auto line glued to the same candles at every zoom.
                    indexes = list(range(first_idx, end_idx + 1))
                    x_vals = [str(pd.to_datetime(_date_for_index(i)).date()) for i in indexes]
                    y_vals = [round(_line_price_at_index(p0, p1, i), 5) for i in indexes]
                    # Keep both anchor candles glued to their true chart extremes.
                    # This avoids any visual rift at the second anchor after the
                    # line has been sampled/extended for chart rendering.
                    for anchor_idx, anchor_price in ((i0, p0[1]), (i1, p1[1])):
                        if anchor_idx in indexes:
                            y_vals[indexes.index(anchor_idx)] = round(float(anchor_price), 5)
                    return x_vals, y_vals

                upper_x, upper_y = _line_object_points(up0, up1)
                lower_x, lower_y = _line_object_points(lo0, lo1)
                existing["drawn_objects"] = [
                    {"id": "auto-wedge-upper", "type": "wedge", "label": "Falling wedge upper", "x": upper_x, "y": upper_y, "x0": upper_x[0], "x1": upper_x[-1], "y0": upper_y[0], "y1": upper_y[-1], "anchor_x": [str(up0[0].date()), str(up1[0].date())], "anchor_y": [round(float(up0[1]), 5), round(float(up1[1]), 5)], "price": upper_y[-1], "color": "#dc2626", "group_id": "auto-wedge"},
                    {"id": "auto-wedge-lower", "type": "wedge", "label": "Falling wedge lower", "x": lower_x, "y": lower_y, "x0": lower_x[0], "x1": lower_x[-1], "y0": lower_y[0], "y1": lower_y[-1], "anchor_x": [str(lo0[0].date()), str(lo1[0].date())], "anchor_y": [round(float(lo0[1]), 5), round(float(lo1[1]), 5)], "price": lower_y[-1], "color": "#2563eb", "group_id": "auto-wedge"},
                ]
                print("[chart] auto-wedge preloaded: upper/lower falling wedge lines")
        except StopIteration:
            pass
        except Exception as exc:
            print(f"[chart] auto-wedge preload failed: {exc}")

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

    if cfd_forced and not df.empty:
        try:
            last_close = float(df.iloc[-1]["Close"])
            existing.setdefault("lot_cost", round(last_close / 5.0, 2))
        except Exception:
            pass
        existing["pip_value"] = 1.0
        existing.setdefault("spread_multiplier", 0.0)

    display_name, display_ticker = _display_identity(symbol, fetch_info.get("symbol"), base_target, fetch_info.get("name"))

    ui = LightweightChartLevelSelectorUI(
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
            "message": f"Session changes saved. Finish was not clicked, so config/chart files were not updated. Downloaded data was cached: {data_path}",
        }

    required_position_fields = ("high", "low", "entry", "stop_loss")
    if any(selected.get(field) in (None, "") for field in required_position_fields):
        return {
            "instrument_type": instrument_type,
            "config_path": None,
            "data_path": str(data_path),
            "chart_path": None,
            "data_source": fetch_info.get("source"),
            "data_symbol": fetch_info.get("symbol"),
            "data_name": fetch_info.get("name"),
            "data_fallback_reason": fetch_info.get("fallback_reason"),
            "message": "Session changes saved. Position levels were incomplete, so config/chart files were not updated.",
        }

    stock_cfd_selected = bool(selected.get("__stock_cfd_mode__")) and (instrument_type == "stock" or cfd_forced)
    save_instrument_type = "commodity" if stock_cfd_selected else instrument_type

    values = {
        "instrument_type": save_instrument_type,
        "high": selected.get("high"),
        "low": selected.get("low"),
        "entry": selected.get("entry"),
        "stop_loss": selected.get("stop_loss"),
        "check_zr_value_fibo_or_elevation": selected.get("check_zr_value_fibo_or_elevation"),
        "line_cross_value": selected.get("line_cross_value"),
        "capital": selected.get("capital", args.capital),
    }

    if save_instrument_type == "stock":
        values.update(
            {
                "name": _resolve_stock_name(symbol, base_target),
                "symbol": symbol,
                "market_data_source": (fetch_info.get("source") or args.data_source or "auto"),
            }
        )
        if _default_currency_conversion_fee("stock", symbol):
            values.update(
                {
                    "apply_currency_conversion_fee": bool(selected.get("apply_currency_conversion_fee", existing.get("apply_currency_conversion_fee", False))),
                    "currency_conversion_fee_pct": float(selected.get("currency_conversion_fee_pct", existing.get("currency_conversion_fee_pct", 0.01))),
                }
            )
    elif save_instrument_type == "commodity":
        chosen_pos = selected.get("position_type", args.position_type or inferred_position or "long")
        chosen_pos = "short" if str(chosen_pos).lower() == "short" else "long"
        spread_value = selected.get("spread", selected.get("spread_multiplier", args.spread) * selected.get("pip_value", args.pip_value))
        values.update(
            {
                "name": symbol,
                "stock_cfd_mode": bool(stock_cfd_selected),
                "position_type": chosen_pos,
                "lot_cost": selected.get("lot_cost", args.lot_cost),
                "spread": spread_value,
                "spread_multiplier": selected.get("spread_multiplier", args.spread),
            }
        )
        if stock_cfd_selected:
            values["spread_pips"] = round(float(spread_value or 0) / 0.01, 2)
        else:
            values["pip_value"] = selected.get("pip_value", args.pip_value)
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
    if stock_cfd_selected:
        final_position = values.get("position_type", inferred_position or "long")
        cfd_slug = (target_base_slug or base_target or symbol).lower()
        final_config_path = resolve_config_path("commodity", f"{cfd_slug}_{final_position}")
        if final_config_path != config_path:
            _save_session_state(final_config_path, selected)
    elif not maybe_config_path and instrument_type in ("commodity", "forex") and target_base_slug:
        final_position = values.get("position_type", inferred_position or "long")
        final_config_path = resolve_config_path(instrument_type, f"{target_base_slug}_{final_position}")
        if final_config_path != config_path:
            _save_session_state(final_config_path, selected)

    snapshot_name = f"{final_config_path.stem}_levels.png"
    chart_path = Path("charts") / snapshot_name
    calculation_path = PROJECT_ROOT / "chart_program" / "data" / "calculations" / f"{final_config_path.stem}_position_calculations.json"

    config_existed, config_backup = _snapshot_file(final_config_path)
    chart_existed, chart_backup = _snapshot_file(chart_path)
    calculation_existed, calculation_backup = _snapshot_file(calculation_path)

    try:
        path = write_or_update_config(instrument_type=save_instrument_type, config_path=final_config_path, values=values)
        ui.save_chart_snapshot(selected, chart_path)

        calculation = selected.get("position_calculations")
        if calculation:
            calculation_path.parent.mkdir(parents=True, exist_ok=True)
            calculation_path.write_text(json.dumps(calculation, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        # `load_or_update_daily_data(..., persist=True)` is the single owner of
        # market-data cache writes.  Do not write the chart dataframe back here:
        # it is intentionally trimmed for UI responsiveness and can be older
        # than a freshly merged Yahoo candle, so saving it would regress the CSV
        # cache after opening/saving a chart.
    except Exception:
        _restore_file(final_config_path, config_existed, config_backup)
        _restore_file(chart_path, chart_existed, chart_backup)
        _restore_file(calculation_path, calculation_existed, calculation_backup)
        raise

    return {
        "instrument_type": save_instrument_type,
        "config_path": str(path),
        "data_path": str(data_path),
        "chart_path": str(chart_path),
        "calculation_path": str(calculation_path) if selected.get("position_calculations") else None,
        "data_source": fetch_info.get("source"),
        "data_symbol": fetch_info.get("symbol"),
        "data_name": fetch_info.get("name"),
        "data_fallback_reason": fetch_info.get("fallback_reason"),
    }
