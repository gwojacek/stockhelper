# StockHelper

StockHelper is a Python project for **position sizing, risk analysis, and trade planning** across three instrument groups:

- **Stocks**
- **Forex**
- **Commodities / CFDs**

It combines:
1. A configurable strategy engine (`main.py`, `main_stock.py`, `core/`, `strategies/`), and
2. An interactive chart workflow (`chart_program/`) to select levels and generate/update configs.

---

## Why this project exists

Trading ideas often fail because risk is not standardized. StockHelper helps you:

- Define entry, stop loss, high/low structure,
- Calculate risk at multiple risk levels,
- Compare position sizing consistently,
- Quickly move from chart annotation to executable config.

In short: **chart -> config -> analysis output**.

---

## Project structure

```text
stockhelper/
├── main.py                     # Commodity/forex analysis entrypoint
├── main_stock.py               # Stock analysis entrypoint
├── core/                       # Shared calculators, factory, display, risk manager
├── strategies/                 # Instrument-specific strategy classes
├── configs/
│   ├── stocks/                 # Stock config modules
│   ├── forex/                  # Forex config modules
│   └── commodities/            # Commodity/CFD config modules
├── chart_program/              # Interactive chart selection + config writer flow
├── utilities/                  # Helpers (e.g. fibo, Yahoo data helper)
├── utils/                      # Small utility helpers (color formatting)
└── data/, charts/              # Runtime-generated outputs (when workflow is used)
```

---

## Core concepts

### 1) Config-first workflow
Each instrument setup is encoded as a Python module with a `TradingConfig` dataclass. Example fields include:

- `entry`, `stop_loss`, `high`, `low`
- `capital`
- `risk_levels` (tuple of risk percentages)
- instrument-specific values (e.g. `symbol`, `pair`, `lot_cost`, `pip_value`, `position_type`)

This makes setups versionable and reproducible.

### 4) Currency handling for foreign stocks
- If **FX conversion fee is enabled** for a foreign stock, StockHelper sizes the position with round-trip conversion fees included (buy + sell at stop), and prints how much the position was reduced because of fees.
- If **FX conversion fee is disabled**, StockHelper assumes you already hold the instrument currency (e.g. USD). In that case stock table money values are shown in the instrument currency instead of PLN.
- In that OFF mode, account capital is internally translated from PLN to instrument currency using current FX so risk percentages stay consistent (no artificial 3-4x position inflation).

### 2) Strategy factory
`core.factory.StrategyFactory` picks the right strategy implementation based on `instrument_type` from the config.

### 3) Multi-risk evaluation
Strategies run calculations across a set of risk levels (default tuple is commonly used across generated configs), helping compare conservative vs aggressive sizing.

---

## Setup

## Requirements

- Python 3.10+ recommended
- Pip packages used by your environment (at minimum: pandas/matplotlib/yfinance-like stack depending on chosen data source and chart usage)

If you already run this repository locally, keep using your current environment.

### Install with Poetry (recommended)

```bash
poetry install
poetry shell
```

### Install with venv + pip (fallback)

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas numpy yfinance plotly dash flask tabulate tenacity colorama
```

> If you want to pin/update dependencies, run `poetry lock` and commit `poetry.lock`.

---

## Running analysis directly


## Super-short commands (auto-dispatch)

Use the new launcher script:

```bash
python run ena
python run eurusd_long
python run cocoa_short
```

It first checks existing files in `configs/stocks`, `configs/forex`, and `configs/commodities` (case-insensitive normalized matching), then falls back to symbol-based detection. It runs:
- stocks -> `main_stock.py`
- forex/commodities -> `main.py`

To open chart mode directly:

```bash
python run -c ena
python run -c eurusd_long
```


### Stocks

Run with a generated or existing stock config:

```bash
python -m mainstock bft
```

You can also pass a full path (`python -m mainstock configs/stocks/bft.py`).

Case-insensitive and normalized matching is supported (e.g. `python -m mainstock dnp` -> `configs/stocks/DNP.py`). Prefix matching is also supported if unambiguous (e.g. `python -m mainstock ena` -> `configs/stocks/enea.py`).

If you run without config argument, the default demo config is used (`BFT`).

### Commodities / Forex

```bash
python -m main cocoa_short
python -m main eurusd_long
```

You can also pass full paths, e.g. `python -m main configs/commodities/Cocoa_short.py`.

If you run without config argument, `main.py` uses a default demo commodity config.

---

## Interactive chart workflow (recommended)

The chart workflow helps you inspect candles, choose levels visually, and persist results.

### Start chart tool

```bash
python -m chart_program coffee_long --instrument commodity
```

or

```bash
python -m chart_program AUD/USD --instrument forex
```

or for stocks:

```bash
python -m chart_program jsw --instrument stock
```

### What happens after Finish

When you click **Finish** and data is saved:

1. Config is created/updated under `configs/<instrument>/...`
2. Chart snapshot is saved to `charts/`
3. Data cache is saved to `data/`
4. Matching analyzer runs automatically:
   - stock -> `main_stock.py`
   - commodity/forex -> `main.py`

To skip auto-run:

```bash
python -m chart_program jsw --instrument stock --no-run-after-save
```

---

## Config naming conventions

- Stocks: usually symbol-oriented files in `configs/stocks/`
- Commodity/Forex: often `<name>_long.py` or `<name>_short.py`

This convention is used by the chart tool when inferring target config path.

---

## Educational walkthrough: from idea to sizing

1. **Choose instrument** (`stock`, `commodity`, `forex`).
2. **Load candles** via chart tool (auto/yahoo/stooq source).
3. **Mark levels**: high, low, entry, stop loss.
4. **Persist** config and snapshot.
5. **Run strategy** (auto-run or manual `main*.py --config ...`).
6. **Review outputs** for risk tiers and decide whether trade profile fits your plan.

This closes the loop between discretionary chart reading and rules-based risk control.

---

## Troubleshooting

### “No changes saved (Finish was not clicked)”
You exited chart UI without finalizing. Re-open and click Finish to persist.

### Config import error
Ensure file exists and is a valid Python module containing `TradingConfig`.

### Data source issue
Try forcing a source:

```bash
python -m chart_program eurusd_long --instrument forex --data-source yahoo
```

### Different spread/pip assumptions
Edit generated config values (`spread`, `pip_value`, `lot_cost`) and rerun analysis.

### Why stock source may differ from turnover source
`Data source` shown in stock output follows the chart-selected market source saved in config (`market_data_source`). Liquidity/turnover internals may still fallback between providers.

---

## Recommended workflow for new instruments

1. Start in chart tool with symbol/pair.
2. Confirm inferred instrument type.
3. Save config.
4. Let auto-run print sizing output.
5. Iterate level selection if risk/reward is not acceptable.

---

## Notes for contributors

- Keep config modules simple and explicit.
- Prefer adding new instrument setups under `configs/` rather than hardcoding in entry scripts.
- Keep strategy logic in `strategies/` and calculation primitives in `core/`.
