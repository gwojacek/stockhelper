from __future__ import annotations

import re
from pathlib import Path

DEFAULT_RISK_LEVELS = (0.005, 0.03, 0.025, 0.02, 0.015, 0.01)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIG_SUBDIR_BY_INSTRUMENT = {
    "stock": "stocks",
    "commodity": "commodities",
    "forex": "forex",
}


def _format_value(value):
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, tuple):
        return f"({', '.join(str(v) for v in value)})"
    return str(value)


def _build_template(instrument_type: str, values: dict) -> str:
    risk_levels = values.get("risk_levels", DEFAULT_RISK_LEVELS)
    filename = values.get("filename", "")

    if instrument_type == "stock":
        symbol = (values.get("symbol") or "").upper()
        include_fee_fields = not (symbol.endswith(".WA") or symbol.endswith(".PL"))
        fee_lines = ""
        if include_fee_fields:
            fee_lines = (
                f'    apply_currency_conversion_fee: bool = {values.get("apply_currency_conversion_fee", False)}\n'
                f'    currency_conversion_fee_pct: float = {values.get("currency_conversion_fee_pct", 0.01)}\n'
            )
        return f'''from dataclasses import dataclass

filename = "{filename}"


@dataclass
class TradingConfig:
    name: str = "{values["name"]}"
    symbol: str = "{values["symbol"]}"
    market_data_source: str = "{values.get("market_data_source", "auto")}"
    instrument_type: str = "stock"
{fee_lines}    capital: float = {values.get("capital", 0)}
    entry: float = {values["entry"]}
    stop_loss: float = {values["stop_loss"]}
    high: float = {values["high"]}
    low: float = {values["low"]}
    check_zr_value_fibo_or_elevation: float = {values.get("check_zr_value_fibo_or_elevation", values["entry"])}
    line_cross_value: float = {values.get("line_cross_value", values["entry"])}
    risk_levels: tuple = {risk_levels}
'''

    if instrument_type == "commodity":
        return f'''from dataclasses import dataclass

filename = "{filename}"


@dataclass
class TradingConfig:
    instrument_type: str = "commodity"
    position_type: str = "{values.get("position_type", "long")}"
    name: str = "{values["name"]}"

    capital: float = {values.get("capital", 0)}

    entry: float = {values["entry"]}
    stop_loss: float = {values["stop_loss"]}
    high: float = {values["high"]}
    low: float = {values["low"]}

    lot_cost: float = {values.get("lot_cost", 0.0)}
    pip_value: float = {values.get("pip_value", 0.0)}
    spread: float = {values.get("spread_expression", values.get("spread", 0.0))}
    check_zr_value_fibo_or_elevation: float = {values.get("check_zr_value_fibo_or_elevation", values["entry"])}
    line_cross_value: float = {values.get("line_cross_value", values["entry"])}
    risk_levels: tuple = {risk_levels}
'''

    return f'''from dataclasses import dataclass

filename = "{filename}"


@dataclass
class TradingConfig:
    instrument_type: str = "forex"
    position_type: str = "{values.get("position_type", "long")}"
    pair: str = "{values["pair"]}"
    apply_currency_conversion_fee: bool = {values.get("apply_currency_conversion_fee", False)}
    currency_conversion_fee_pct: float = {values.get("currency_conversion_fee_pct", 0.01)}

    capital: float = {values.get("capital", 0)}

    entry: float = {values["entry"]}
    stop_loss: float = {values["stop_loss"]}
    high: float = {values["high"]}
    low: float = {values["low"]}

    lot_cost: float = {values.get("lot_cost", 0.0)}
    pip_value: float = {values.get("pip_value", 0.0)}
    pip_size: float = {values.get("pip_size", 0.0001)}
    spread: float = {values.get("spread_expression", values.get("spread", 0.0))}
    check_zr_value_fibo_or_elevation: float = {values.get("check_zr_value_fibo_or_elevation", values["entry"])}
    line_cross_value: float = {values.get("line_cross_value", values["entry"])}
    risk_levels: tuple = {risk_levels}
'''


def _update_existing_text(content: str, values: dict) -> str:
    updated = content
    filename_value = values.get("filename")
    if filename_value:
        filename_line = f'filename = "{filename_value}"'
        if re.search(r"^filename\s*=\s*['\"].*['\"]\s*$", updated, flags=re.MULTILINE):
            updated = re.sub(r"^filename\s*=\s*['\"].*['\"]\s*$", filename_line, updated, flags=re.MULTILINE)
        else:
            import_line_match = re.search(r"^from\s+dataclasses\s+import\s+dataclass\s*$", updated, flags=re.MULTILINE)
            if import_line_match:
                insert_at = import_line_match.end()
                updated = updated[:insert_at] + f"\n\n{filename_line}" + updated[insert_at:]
            else:
                updated = filename_line + "\n\n" + updated

    for key, value in values.items():
        if key == "filename":
            continue
        pattern = rf"^(\s*{re.escape(key)}\s*:\s*[^=]+?=\s*).*$"
        rendered_value = value if key == "spread" and isinstance(value, str) and "pip_value" in value else _format_value(value)
        replacement = rf"\g<1>{rendered_value}"
        updated, count = re.subn(pattern, replacement, updated, flags=re.MULTILINE)
        if count == 0:
            insert_line = f"    {key}: float = {_format_value(value)}\n"
            if "risk_levels" in updated:
                updated = updated.replace("    risk_levels", insert_line + "    risk_levels", 1)
            else:
                updated += "\n" + insert_line

    if "risk_levels" not in updated:
        updated += f"\n    risk_levels: tuple = {_format_value(DEFAULT_RISK_LEVELS)}\n"

    return updated


def resolve_config_path(instrument_type: str, target_name: str) -> Path:
    subdir = CONFIG_SUBDIR_BY_INSTRUMENT[instrument_type]
    safe_name = target_name.lower().replace("/", "").replace(".", "_")
    return PROJECT_ROOT / "configs" / subdir / f"{safe_name}.py"


def write_or_update_config(instrument_type: str, config_path: Path, values: dict) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    values = dict(values)
    values["filename"] = config_path.stem
    values["risk_levels"] = DEFAULT_RISK_LEVELS
    if "spread_multiplier" in values:
        values["spread"] = values["spread_multiplier"]

    if config_path.exists():
        content = config_path.read_text(encoding="utf-8")
        updated = _update_existing_text(content, values)
        config_path.write_text(updated, encoding="utf-8")
    else:
        rendered = _build_template(instrument_type=instrument_type, values=values)
        config_path.write_text(rendered, encoding="utf-8")

    return config_path
