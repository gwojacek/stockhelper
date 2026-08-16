from __future__ import annotations

import json
from pathlib import Path


INSTRUMENT_NAMES_FILE = Path(__file__).resolve().parents[1] / "data" / "instrument_names.json"


def instrument_name_for_ticker(*tickers: str | None) -> str | None:
    """Return the configured friendly name for the first matching ticker."""
    try:
        names = json.loads(INSTRUMENT_NAMES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    for ticker in tickers:
        raw = str(ticker or "").strip().upper()
        if not raw:
            continue
        candidates = [raw]
        if "/" in raw:
            candidates.extend(part.strip() for part in raw.split("/") if part.strip())
        if "." not in raw:
            candidates.append(f"{raw}.WA")
        for candidate in candidates:
            name = str(names.get(candidate, "")).strip()
            if name:
                return name
    return None
