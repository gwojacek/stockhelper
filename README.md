# StockHelper

StockHelper is a Python project for **position sizing, risk analysis, and trade planning** across three instrument groups:

- **Stocks**
- **Forex**
- **Commodities / CFDs**

It combines:
1. A configurable strategy engine (`main.py`, `main_stock.py`, `core/`, `strategies/`),
2. A launcher (`run`) that auto-detects config/instrument and exposes scanner/debug workflows, and
3. An interactive chart workflow (`chart_program/`) to select levels and generate/update configs.

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

### 2) Currency handling for foreign stocks
- If **FX conversion fee is enabled** for a foreign stock, StockHelper sizes the position with round-trip conversion fees included (buy + sell at stop), and prints how much the position was reduced because of fees.
- If **FX conversion fee is disabled**, StockHelper assumes you already hold the instrument currency (e.g. USD). In that case stock table money values are shown in the instrument currency instead of PLN.
- In that OFF mode, account capital is internally translated from PLN to instrument currency using current FX so risk percentages stay consistent (no artificial 3-4x position inflation).

### 3) Strategy factory
`core.factory.StrategyFactory` picks the right strategy implementation based on `instrument_type` from the config.

### 4) Multi-risk evaluation
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

### Chart window behavior

- Chart UI renders a capped recent window of about **1.5 years** (~548 calendar days) for responsiveness.
- Full candle history is still kept in local CSV cache and used by scanner flows where required.

### Ichimoku scanner (`-ichimoku_search`)

You can run bulk scanner workflows directly from launcher:

```bash
python run -ichimoku_search indexes
python run -ichimoku_search commodities
python run -ichimoku_search wig
python run -ichimoku_search dax
python run -ichimoku_search ndx
```

Scanner details:
- scanner calculations are based on full cached CSV history (refresh + read-cache flow),
- scanner/fibo flows explicitly request older history (`fetch_older_data=True`) before calculations,
- supports dedicated universes for `wig`, `dax/dax40`, `ndx/us100`,
- writes CSV outputs to `chart_program/data/search/ichimoku/` (Ichimoku) and `chart_program/data/search/fibo/` (Fibonacci),
- prints **WYNIKI** and **WYNIKI 2** (flip results),
- prints per-row Stooq chart links and can open all links after confirmation.

For large `wig` runs, scanner uses VPN-friendly chunking (165-size parts) with confirmation between chunks.

You can also run explicit parts (parallel-friendly):

```bash
python run -ichimoku_search wig_part1
python run -ichimoku_search wig_part2
python run -ichimoku_search wig_part3
```



### Parallel / xdist-friendly scanner commands

For large universes you can split and run parts in parallel terminals (or CI jobs):

```bash
python run -ichimoku_search wig_part1
python run -ichimoku_search wig_part2
python run -ichimoku_search wig_part3
```

Batch/non-interactive mode (auto-continue at checkpoints):

```bash
STOCKHELPER_BATCH_MODE=1 python run -ichimoku_search wig
```

`-allsearch` also supports scoped parallel workflows (e.g. separate jobs per `wig`, `dax`, `us100`, `forex`, `commodities`).

### Quick liquidity check (`-checkavg`)

You can quickly ask for the **Avg10d PLN** metric for a single instrument:

```bash
python run -checkavg ena
python run -checkavg eurusd
python run -checkavg gold
```

What it does:
- auto-detects instrument type (stock / forex / commodity),
- downloads/loads daily data,
- calculates turnover (`Close * Volume`) for each day,
- converts to PLN and prints `Avg10d PLN` from the last 10 bars.

### Combined scanner report (`-allsearch`)

Use `-allsearch` to run a combined **Ichimoku + Fibonacci** scan and produce combined **MD + HTML** reports.

```bash
python run -allsearch all
python run -allsearch wig
python run -allsearch dax
python run -allsearch us100
python run -allsearch forex
python run -allsearch commodities
```

Behavior:
- `-allsearch` **always runs both** scanners (Ichimoku + Fibonacci) for the selected scope(s),
- `-allsearch all` runs all major scopes: `wig`, `dax`, `us100`, `forex`, `commodities`,
- per-scope outputs are written under `chart_program/data/all_insturments_search/`,
- combined reports are saved under `chart_program/data/all_insturments_search/allsearch/`,
- report filename is scope-aware:
  - `python run -allsearch all` -> `allsearch_latest_all.md` + `allsearch_latest_all.html`,
  - `python run -allsearch us100` -> `allsearch_latest_us100.md` + `allsearch_latest_us100.html`,
- HTML report is auto-opened after generation,
- HTML includes per-market grouped tables (`WYNIKI 1/2 ICHIMOKU`, `WYNIKI FIBO #1/#2`), search/filter, and sortable columns.
- in HTML report, `stockhelper_chart` commands for **commodities** use mapped Stooq symbols (e.g. `COFFEE` -> `KC.F`) so chart opening works correctly,
- PDF export button sets a date-based filename suggestion, e.g. `stockhelper_report_2026-05-24.pdf` (depends on browser print dialog behavior).

If you want only one scanner:
- Ichimoku only: `python run -ichimoku_search <scope>`
- Fibonacci only: `python run -fibo_search <scope>`

### Fibonacci debug (why setup is or is not matched)

To debug a single symbol with step-by-step explanations from the FIBO detector:

```bash
python - <<'PY'
import scanner_search
scanner_search.run_fibo_explain('single', 'MPWR.US')
PY
```

What this prints:
- result for each offset (`0, 5, 10, 15, 20, 30, 40`) as `MATCH`/`NO MATCH`,
- detected status/pattern/touch date for matches,
- detailed rejection reasons for non-matches (e.g. stale impulse start, non-dominant peak).

### Stooq debug / scraper helpers

To inspect Stooq/captcha/debug artifacts:

```bash
python run --debug-stooq coffee
python run --debug-stooq coffee --inspector
python run -ichimoku_search commodities --search-debug
```

Notes:
- `--inspector` enables interactive captcha/debug flow in browser.
- `--search-debug` enables verbose Stooq scraper logs via `STOCKHELPER_STOOQ_DEBUG=1`.
- For selected symbols, loader may use Playwright web path (`stooq_web`) when API responses are insufficient.


### Stocks

Run with a generated or existing stock config:

```bash
python -m main_stock bft
```

(Compatibility alias also works: `python -m mainstock bft`.)

You can also pass a full path (`python -m main_stock configs/stocks/bft.py`).

Case-insensitive and normalized matching is supported (e.g. `python -m main_stock dnp` -> `configs/stocks/DNP.py`). Prefix matching is also supported if unambiguous (e.g. `python -m main_stock ena` -> `configs/stocks/enea.py`).

If you run without config argument, the default demo config is used (`BFT`).

### Commodities / Forex

```bash
python -m main cocoa_short
python -m main eurusd_long
```

You can also pass full paths, e.g. `python -m main configs/commodities/Cocoa_short.py`.

If you run without config argument, `main.py` currently falls back to `configs/commodities/Lockhead_Martin_long.py`.

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
