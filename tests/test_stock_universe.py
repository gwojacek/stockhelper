import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _wig_tickers():
    tree = ast.parse((ROOT / "scanner_search.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "WIG_SEARCH_TICKERS" for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("WIG_SEARCH_TICKERS not found")


def test_stale_wig_symbols_are_replaced_by_multiqure():
    tickers = _wig_tickers()
    names = json.loads((ROOT / "data" / "instrument_names.json").read_text(encoding="utf-8"))

    assert "MOJ" not in tickers
    assert "PUR" not in tickers
    assert "MQR" in tickers
    assert names["MQR.WA"] == "MultiQure SA"
    assert "MOJ.WA" not in names
    assert "PUR.WA" not in names


def test_grx_reviewed_sidetrends_are_persisted():
    state = json.loads((ROOT / "data" / "state" / "sessions" / "grx.json").read_text(encoding="utf-8"))

    corrected = {(item["start"], item["end"]) for item in state["__saved_sidetrends__"]}
    invalid = {(item["scannerStart"], item["scannerEnd"]) for item in state["__saved_invalid_sidetrends__"]}
    assert corrected == {
        ("2025-08-06", "2025-09-03"),
        ("2025-12-01", "2026-01-08"),
        ("2026-01-29", "2026-03-19"),
        ("2026-03-26", "2026-05-27"),
        ("2026-06-24", "2026-08-07"),
    }
    assert invalid == {
        ("2025-04-01", "2025-05-16"),
        ("2026-08-13", "2026-09-15"),
    }
