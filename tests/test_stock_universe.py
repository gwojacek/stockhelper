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
