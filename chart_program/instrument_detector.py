from __future__ import annotations

from pathlib import Path
import re


INSTRUMENT_DIR_TO_TYPE = {
    "stocks": "stock",
    "commodities": "commodity",
    "forex": "forex",
}


def detect_from_config_path(config_path: Path | None) -> str | None:
    if not config_path:
        return None

    parts = [part.lower() for part in config_path.parts]
    for directory_name, instrument_type in INSTRUMENT_DIR_TO_TYPE.items():
        if directory_name in parts:
            return instrument_type
    return None


def detect_from_symbol(symbol_or_pair: str) -> str:
    cleaned = symbol_or_pair.strip().upper()
    if cleaned.endswith(" CFD"):
        return "commodity"
    known_commodity_tokens = {
        "GOLD",
        "XAUUSD",
        "XAU/USD",
        "SILVER",
        "XAGUSD",
        "XAG/USD",
        "COFFEE",
        "WHEAT",
        "ZW.F",
        "SUGAR",
        "COCOA",
        "CORN",
        "SOYBEAN",
        "SOYOIL",
        "ALUMINIUM",
        "NICKEL",
        "ZINC",
        "PALLADIUM",
        "PLATINUM",
        "GASOLINE",
        "LSGASOIL",
        "OIL",
        "OIL.WTI",
        "WTI",
        "NATGAS",
        "NATURAL_GAS",
        "CRUDE_OIL",
        "COPPER",
        "US500",
        "US100",
        "US30",
        "US500",
        "US100",
        "BRAComp".upper(),
        "MEXComp".upper(),
        "VIX",
        "HK.CASH",
        "SG20CASH",
        "AU200.CASH",
        "CHN.CASH",
        "JP225",
        "W20",
        "WIG20",
        "UK100",
        "ITA40",
        "DE40",
        "FRA40",
        "NED25",
        "SUI20",
        "SPA35",
        "EU50",
        "^BVP",
        "^SPX",
        "^IPC",
        "VI.C",
        "^DJI",
        "^NDX",
        "^HSI",
        "^STI",
        "^AOR",
        "0EL.C",
        "^NKX",
        "^UKX",
        "^FMIB",
        "^DAX",
        "^CAC",
        "^AEX",
        "^SMI",
        "^IBEX",
        "FX.F",
        "BTC",
        "DOGE",
    }
    if cleaned in known_commodity_tokens:
        return "commodity"

    if "/" in cleaned:
        return "forex"

    if re.fullmatch(r"[A-Z0-9_]+\.F", cleaned):
        return "commodity"

    if any(cleaned.endswith(suffix) for suffix in (".WA", ".US", ".L", ".DE", ".PL")):
        return "stock"

    if cleaned.isalpha() and len(cleaned) == 6:
        return "forex"

    return "stock"


def detect_instrument_type(symbol_or_pair: str, config_path: Path | None = None) -> str:
    detected = detect_from_config_path(config_path)
    if detected:
        return detected
    return detect_from_symbol(symbol_or_pair)
