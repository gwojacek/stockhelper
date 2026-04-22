from __future__ import annotations

from pathlib import Path


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
    if "/" in cleaned:
        return "forex"

    if any(cleaned.endswith(suffix) for suffix in (".WA", ".US", ".L", ".DE", ".PL")):
        return "stock"

    known_commodity_tokens = {
        "GOLD",
        "SILVER",
        "COFFEE",
        "WHEAT",
        "SUGAR",
        "COCOA",
        "NATURAL_GAS",
        "CRUDE_OIL",
        "COPPER",
        "US500",
        "US100",
        "WIG20",
    }
    if cleaned in known_commodity_tokens:
        return "commodity"

    if cleaned.isalpha() and len(cleaned) == 6:
        return "forex"

    return "stock"


def detect_instrument_type(symbol_or_pair: str, config_path: Path | None = None) -> str:
    detected = detect_from_config_path(config_path)
    if detected:
        return detected
    return detect_from_symbol(symbol_or_pair)
