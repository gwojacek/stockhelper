import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_program import main as chart_main


def test_chart_program_accepts_ichimoku_mode_without_consuming_value_as_modifier(monkeypatch):
    captured = {}
    fake_level_selector = types.ModuleType("chart_program.level_selector")

    def fake_run_level_selector(args):
        captured["args"] = args
        return {}

    fake_level_selector.run_level_selector = fake_run_level_selector
    monkeypatch.setitem(sys.modules, "chart_program.level_selector", fake_level_selector)
    monkeypatch.setattr(sys, "argv", ["chart_program", "OPL", "--ichimoku-mode", "on"])

    assert chart_main.main() == 0
    assert captured["args"][0] == "OPL"
    assert "--ichimoku-mode" in captured["args"]
    assert captured["args"][captured["args"].index("--ichimoku-mode") + 1] == "on"


def test_chart_program_forwards_report_chart_overlays(monkeypatch):
    captured = {}
    fake_level_selector = types.ModuleType("chart_program.level_selector")

    def fake_run_level_selector(args):
        captured["args"] = args
        return {}

    fake_level_selector.run_level_selector = fake_run_level_selector
    monkeypatch.setitem(sys.modules, "chart_program.level_selector", fake_level_selector)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chart_program",
            "AEP.US",
            "--ichimoku-mode",
            "off",
            "--fibo-lines",
            "5",
            "--fibo-anchor-start",
            "2026-01-05",
            "--fibo-anchor-end",
            "2026-02-20",
            "--fibo-right",
        ],
    )

    assert chart_main.main() == 0
    assert captured["args"][0] == "AEP.US"
    for expected in [
        "--ichimoku-mode",
        "off",
        "--fibo-lines",
        "5",
        "--fibo-anchor-start",
        "2026-01-05",
        "--fibo-anchor-end",
        "2026-02-20",
        "--fibo-right",
    ]:
        assert expected in captured["args"]
