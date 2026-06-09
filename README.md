# StockHelper

StockHelper is a Python toolkit for quickly checking trade ideas and scanning markets.

It helps you:

- calculate position size, engaged capital, potential loss, and risk/reward for configured setups;
- work with stocks, forex pairs, commodities, and CFD/index-like instruments;
- download/cache daily market data from Stooq, Yahoo Finance, and Stooq web/table fallbacks;
- scan market groups for Ichimoku cloud, Fibonacci setups, and falling-wedge (Kliny) formations;
- generate compact Trójpolówki (3P) Fibo/Ichimoku watchlists plus a dedicated Kliny tab from the latest allsearch data;
- open an interactive chart tool, select price levels, save/update config files, and export chart snapshots;
- generate terminal output plus Markdown/HTML reports, cached CSV data, debug JSON/HTML/screenshots, and chart images.

The project is practical and config-driven: most workflows start from a ticker/config slug, write reusable files under `configs/`, cache market data under `data/`, and save reports under `chart_program/data/`.

## Quick command table

Use this table as the fastest path to the commands you will run most often. Detailed explanations and variants are later in [Most useful commands](#most-useful-commands).

| Use case | Command | Short description |
| --- | --- | --- |
| Install dependencies | `poetry install` | Create the Poetry environment from `pyproject.toml`. |
| Install Playwright browser | `poetry run playwright install chromium` | Required for Stooq web/debug/CAPTCHA flows. |
| Run a stock setup | `python run ena` | Auto-detects a stock config and prints position/risk output. |
| Run a forex/commodity setup | `python run eurpln_long` | Auto-detects a forex/commodity config and prints lot/risk output. |
| Open chart editor | `python run -c ena` | Opens the browser chart UI to select levels and save config/snapshot files. |
| Open chart with Ichimoku | `python run -c EUR/USD --ichimoku-mode on` | Opens chart mode with the Ichimoku overlay enabled. |
| Open stock as CFD | `python run -c AAPL.US cfd` | Opens a stock chart in CFD/commodity mode, with CFD sizing and spread as price units. |
| Run Ichimoku scan | `python run -ichimoku_search wig` | Scans a market group and writes an Ichimoku Markdown report. |
| Run Fibonacci scan | `python run -fibo_search wig` | Scans a market group and writes a Fibonacci Markdown report. |
| Build combined report | `python run -allsearch all` | Runs scanners and creates combined Markdown/HTML reports plus embedded 3P and Kliny tabs. |
| Reopen combined report | `python run --open-allsearch-report all` | Opens the latest existing HTML all-search report. |
| Explain one Fibo symbol | `python run -fibo_search single -explain MPWR.US` | Shows why one symbol matched or failed Fibonacci rules. |
| Check liquidity | `python run -checkavg XTB.WA` | Prints recent average turnover/liquidity for one instrument. |
| Debug Stooq page | `python run --debug-stooq CB.F` | Saves Stooq debug JSON/HTML/screenshot artifacts. |
| Use cache only | `python run -onlycache -ichimoku_search wig` | Avoids remote refresh/probing when you want to rely on local CSVs, including commodities. |
| Force refresh | `STOCKHELPER_FORCE_REMOTE_REFRESH=1 python run -fibo_search wig` | Ignores usable cache and refreshes market data. |
| Extend history | `python run --fetch-older-data --fetch-older-data-scope stocks --fetch-workers 4` | Backfills older stock CSV history. |
| Syntax check | `python -m py_compile main.py main_stock.py scanner_search.py chart_program/main.py chart_program/level_selector.py` | Fast Python syntax check without running scanners. |

## Features

- **Position/risk analysis** for stocks, forex, and commodities/CFDs.
- **Config-first workflow** using Python `TradingConfig` classes in `configs/stocks/`, `configs/forex/`, and `configs/commodities/`.
- **Short launcher**: `python run <slug>` auto-detects the config/instrument and calls the correct analysis script.
- **Market data download and cache**:
  - Stooq API/CSV-style downloads for many stocks/forex/commodities;
  - Yahoo Finance fallback where supported;
  - Stooq web/table fallback for selected commodity data;
  - local CSV cache in `data/stocks/`, `data/forex/`, `data/commodities/`, and `data/indices/`.
- **Ichimoku cloud scanner** for WIG, DAX/DAX40, Nasdaq-100/US100, forex, commodities, or a single instrument.
- **Fibonacci formation scanner** with long/short setup search, 23.6/61.8 retracement states, reversal-pattern checks, and an explain/debug mode.
- **Falling-wedge (Kliny) scanner** exported from the Fibo scan flow, including unbroken wedges and fresh breakouts (up to 5 candles after breakout), Avg10d liquidity filtering, touch/contact metrics, and chart commands that preload wedge lines.
- **Trójpolówki (3P) watchlists** generated from allsearch output, with compact Fibo columns, compact Ichimoku continuation/watch/cloud/retest columns, market ordering, top choices, per-column `📊` StockHelper bulk-open buttons, Stooq/Sheets controls, and PDF export from every report tab.
- **Liquidity/volume filters** for stock scanner output, including Avg10d PLN and GDP-adjusted thresholds.
- **Interactive chart tool** powered by TradingView Lightweight Charts, with manual level selection, optional Ichimoku overlay, optional Fibonacci/wedge lines, stock-CFD mode, clear-active-value controls, saved sessions, generated configs, and chart snapshots.
- **Reports and artifacts**:
  - Markdown scanner reports in `chart_program/data/search/ichimoku/` and `chart_program/data/search/fibo/`;
  - Trójpolówki Markdown watchlists in `Trojpolowki/fibo.md` and `Trojpolowki/ichimoku.md`;
  - combined Markdown/HTML scanner reports in `chart_program/data/all_insturments_search/allsearch/`;
  - chart snapshots in `charts/`;
  - manual/session state in `data/sessions/`;
  - Stooq debug JSON/HTML/screenshots in `debug/stooq/`.
- **CAPTCHA/rate-limit support** for Stooq web fallback, including OCR attempts and optional Playwright inspector/manual mode.

Falling wedges are first-class scanner/report items. A separate generic triangle scanner is not documented as an available feature.

## Repository layout

```text
stockhelper/
├── run                         # Main short launcher for analysis, charts, scanners, debug tools
├── main.py                     # Commodity/forex analysis entrypoint
├── main_stock.py               # Stock analysis entrypoint
├── mainstock.py                # Backward-compatible wrapper around main_stock.py
├── scanner_search.py           # Ichimoku/Fibonacci scanner implementation
├── core/                       # Shared calculator, display, factory, risk manager
├── strategies/                 # Stock, forex, commodity strategy classes
├── configs/                    # Versioned TradingConfig files
│   ├── stocks/
│   ├── forex/
│   └── commodities/
├── chart_program/              # Interactive chart UI and config writer
├── Trojpolowki/                # Generated compact 3P Fibo/Ichimoku watchlists
├── utilities/                  # Stooq/Yahoo/report/debug helpers
├── data/                       # Cached market data and chart sessions
└── charts/                     # Generated chart snapshots
```

## Installation

### Requirements

- Python `>=3.10,<4.0`
- Poetry is the recommended installer because dependencies are declared in `pyproject.toml`.
- Browser support for Stooq web fallback/debug flows requires Playwright browser binaries.

### Install with Poetry

```bash
poetry install
poetry run playwright install chromium
```

Use `poetry run ...` for commands, or activate the Poetry environment first:

```bash
poetry shell
```

### Install with `venv` + `pip` instead

There is no `requirements.txt` in this repository. If you do not use Poetry, install the dependencies listed in `pyproject.toml` manually:

```bash
python -m venv .venv
source .venv/bin/activate
pip install colorama curl_cffi dash flask numpy pandas plotly tabulate tenacity playwright yfinance opencv-python easyocr
python -m playwright install chromium
```

### Stooq bot-check downloads

For the fast Stooq CSV fetch path added for browser verification pages, make sure `curl_cffi` is installed in the Python environment that runs `python run ...`. Poetry installs it from the lock file, but an older or manually maintained `venv` may not have it yet.

```bash
python -m pip install -U curl_cffi
python - <<'PY'
import curl_cffi
print(curl_cffi.__version__)
PY
```

If you use Poetry instead of an activated `venv`, refresh the environment with:

```bash
poetry install
```

### Optional/system dependencies

These packages are used by specific workflows:

- `playwright`: Stooq web/table fallback, Stooq debug pages, CAPTCHA/inspector workflows.
- `opencv-python`: CAPTCHA image preprocessing.
- `easyocr`: CAPTCHA OCR attempts.
- `curl_cffi`: browser TLS/HTTP impersonation for Stooq CSV downloads when Stooq serves a browser-verification page.
- `yfinance`: Yahoo fallback data source.
- `flask`: local interactive chart UI powered by TradingView Lightweight Charts; `dash`/`plotly` remain available for legacy chart tooling and historical snapshot compatibility.
- `pyinstaller`: dev-only dependency for building an executable.

If chart snapshot export fails, install Plotly's image backend in your environment:

```bash
pip install kaleido
```

## Environment variables

Only variables referenced by the code are listed here.

| Variable | Example | Description |
| --- | --- | --- |
| `STOCKHELPER_CACHE_ONLY` | `1` | Forces scanner/data workflows to use local CSV cache instead of remote refresh. Some batch flows set/unset it internally. |
| `STOCKHELPER_FORCE_REMOTE_REFRESH` | `1` | Forces data refresh even when local CSV cache looks usable. |
| `STOCKHELPER_STOOQ_DEBUG` | `1` | Enables verbose Stooq scraper/debug logging. Also enabled by `python run --search-debug ...`. |
| `STOCKHELPER_STOOQ_CAPTCHA_DEBUG` | `1` | Prints extra CAPTCHA OCR/debug details and writes CAPTCHA debug screenshots. |
| `STOCKHELPER_STOOQ_CAPTCHA_ATTEMPTS` | `5` | Number of OCR CAPTCHA attempts before giving up/falling back. Default in code is `5`. |
| `STOCKHELPER_STOOQ_MAX_RUNTIME_S` | `900` | Watchdog timeout for Stooq web scraping. Code enforces at least 30 seconds. |
| `STOCKHELPER_COMMODITIES_WORKERS` | `2` | Worker count for bounded parallel commodity Stooq web scans. Default is `2`; increase only when Stooq is stable. |
| `STOCKHELPER_COMMODITIES_SEQUENTIAL` | `1` | Forces commodity scans to single-threaded Stooq web fetching. Useful when VPN/CAPTCHA prompts are noisy. |
| `STOCKHELPER_DEBUG_SYMBOL` | `XTB.WA` | Enables detailed scanner debug logs for one symbol. |
| `STOCKHELPER_DEFER_OPEN_LINKS` | `1` | Prevents scanner flows from prompting/opening all result links immediately. Used internally by batch reports. |
| `STOCKHELPER_BATCH_MODE` | `1` | Marks scanner execution as batch mode. Used internally by batch report workflows. |
| `PYTEST_XDIST_WORKER` | `gw0` | Optional sharding signal used by `--fetch-older-data`. |
| `PYTEST_XDIST_WORKER_COUNT` | `4` | Optional total shard count used by `--fetch-older-data`. |
| `XDIST_WORKER` | `gw0` | Alternative xdist worker variable used by `--fetch-older-data`. |
| `XDIST_WORKER_COUNT` | `4` | Alternative xdist worker-count variable used by `--fetch-older-data`. |
| `STOCKHELPER_FETCH_ONE_TIMEOUT_S` | `90` | Per-symbol timeout for `--fetch-older-data`. Default is `90`, minimum is `15`. |
| `STOCKHELPER_FETCH_VPN_PAUSE_S` | `120` | Pause before the retry pass in `--fetch-older-data` when no symbol was extended. |
| `STOCKHELPER_FETCH_RETRY_ON_ZERO_BACKFILL` | `0` | Set to `0` to disable the automatic retry pass when `--fetch-older-data` adds no older rows. |

### API keys

The chart tool has an `--api-key` option that is forwarded to Stooq query parameters:

```bash
python -m chart_program AAPL.US --instrument stock --api-key YOUR_KEY
```

The code also contains a built-in Stooq default API key in the data loader. No Stooq API-key environment variable was found.

## Most useful commands

Run the examples from the repository root.

### 1. Run analysis for an existing stock config

```bash
python run ena
```

**Description:**

- Finds a matching file in `configs/stocks/` using case-insensitive/normalized matching.
- Calls `main_stock.py` automatically.
- Calculates shares, engaged capital, potential loss, loss %, optional take-profit/risk-reward, stock liquidity metrics, and warnings.
- Uses Stooq-backed local data where possible and updates cache under `data/stocks/`.

**When to use it:**

- You already have a stock config and want a quick position-size/risk check.

**Output to expect:**

- A terminal table with risk levels and position sizes.
- Warnings if liquidity/risk-reward checks fail.
- Updated cached data in `data/stocks/` when data is refreshed.

**Common variants:**

```bash
python run xtb
python run configs/stocks/ena.py
python main_stock.py --config configs/stocks/ena.py
```

### 2. Run analysis for a forex or commodity config

```bash
python run eurpln_long
python run cocoa_short
```

**Description:**

- Finds a matching file in `configs/forex/` or `configs/commodities/`.
- Calls `main.py` automatically.
- Calculates lots, engaged capital, potential loss with spread, loss %, and risk/reward checks.

**When to use it:**

- You want to validate an existing forex/commodity/CFD setup.

**Output to expect:**

- A terminal risk table and position analysis.
- Updated cached data in `data/forex/` or `data/commodities/` when data is refreshed by the workflow.

**Common variants:**

```bash
python run usd_pln_short
python run gold_short
python main.py --config configs/commodities/Cocoa_short.py
```

### 3. Open the interactive chart/config tool

```bash
python run -c ena
```

**Description:**

- Opens the TradingView Lightweight Charts UI in your browser.
- Loads cached data first, with data provider fallback support.
- Lets you click/select levels such as high, low, entry, stop loss, optional check/risk-reward levels, and drawn objects; the active level can be cleared from the sidebar.
- Stock charts include a CFD mode toggle; `python run -c AAPL.US cfd` opens the same symbol directly with CFD sizing inputs enabled. Stock CFDs use lot/deposit cost plus spread entered as price units with pips shown as `spread / 0.01`, so no separate pip-value field is required.
- Saves a config and chart snapshot when you click **Finish**.

**When to use it:**

- You want to create or update a `TradingConfig` from chart levels instead of editing Python files manually.

**Output files created/updated:**

- Config: `configs/stocks/<slug>.py`, `configs/forex/<slug>_<long|short>.py`, or `configs/commodities/<slug>_<long|short>.py`.
- Chart snapshot: `charts/<config>_levels.png`.
- Session state: `data/sessions/<config>.json`.
- Cached market data: `data/<group>/<symbol>.csv`.

**Common variants:**

```bash
python run -c AAPL.US
python run -c AAPL.US cfd
python run -c EUR/USD --ichimoku-mode on
python run -c TRN --fibo-lines 5 --fibo-anchor-start 2026-01-30 --fibo-anchor-end 2026-05-21 --fibo-right
python -m chart_program jsw --instrument stock --data-source stooq --no-run-after-save
```

### 4. Run an Ichimoku scanner

```bash
python run -ichimoku_search wig
```

**Description:**

- Scans a market group for instruments that remain above/below the Ichimoku cloud.
- Adds retest status/pattern information and liquidity metrics where available.
- Probes data freshness before deciding whether to refresh remote data or use cache.

**When to use it:**

- You want a broad list of possible Ichimoku trend/retest candidates.

**Important scopes:**

```text
wig, dax, dax40, ndx, ndx100, us100, forex, commodities, indexes, single, all
```

**Output files created:**

- Markdown reports: `chart_program/data/search/ichimoku/search_<scope>_<YYYYMMDD>.md`.
- Cached CSV data in `data/`.
- Terminal output with result tables and Stooq chart links.

**Common variants:**

```bash
python run -ichimoku_search all
python run -ichimoku_search commodities
python run -ichimoku_search forex
STOCKHELPER_DEBUG_SYMBOL=XTB.WA python run -ichimoku_search wig
```

### 5. Run a Fibonacci scanner

```bash
python run -fibo_search wig
```

**Description:**

- Searches for Fibonacci pullback setups.
- Reports setups waiting between 23.6 and 61.8, valid recent reversal formations, ratios, first 61.8 touch dates, liquidity metrics, chart links, and ready-to-copy chart commands.

**When to use it:**

- You want candidates where a strong impulse and retracement may be forming.

**Output files created:**

- Markdown reports: `chart_program/data/search/fibo/fibo_search_<scope>_<YYYYMMDD>.md`.
- Cached CSV data in `data/`.
- Terminal output with result tables and chart-opening commands.

**Common variants:**

```bash
python run -fibo_search all
python run -fibo_search dax
python run -fibo_search us100
python run -fibo_search commodities
```

### 6. Explain one Fibonacci scanner result

```bash
python run -fibo_search single -explain MPWR.US
```

**Description:**

- Runs the Fibonacci detection logic for one instrument with explanation/debug output.
- Helps answer “why did this symbol match or not match?”

**When to use it:**

- A scanner result looks surprising.
- You expected a symbol to appear but it did not.

**Output to expect:**

- Terminal diagnostics about setup detection and rejection/acceptance reasons.

**Common variants:**

```bash
python run -fibo_search wig -explain XTB.WA
python run -fibo_search commodities -explain XAUUSD
```

### 7. Run combined Ichimoku + Fibonacci reports

```bash
python run -allsearch all
```

**Description:**

- Runs Ichimoku and Fibonacci scanning and combines the outputs.
- Regenerates compact Trójpolówki Markdown watchlists from the same allsearch run (no second instrument scan).
- Builds a browser-friendly HTML report and a Markdown report.
- Embeds four HTML tabs: `ALLSEARCH REPORT`, `3P FIBO`, `3P ICHIMOKU`, and `🔻 Kliny`.
- Adds top-choice sections, sortable/filterable tables, group Stooq-open buttons, StockHelper chart-open buttons, and a PDF export button that works from every tab.
- Opens/serves the HTML report via the local report server when possible.

**When to use it:**

- You want one report for daily/regular market review.

**Output files created:**

- `chart_program/data/all_insturments_search/allsearch/allsearch_latest_<scope>.md`
- `chart_program/data/all_insturments_search/allsearch/allsearch_latest_<scope>.html`
- `Trojpolowki/fibo.md`
- `Trojpolowki/ichimoku.md`

> Note: the directory name is spelled `all_insturments_search` in the repository.

**Trójpolówki details:**

- `Trojpolowki/fibo.md` uses three compact columns: steep/early `WYNIKI FIBO #0` setups, 23.6 warning-zone setups, and deep pullbacks near/over 75% toward 61.8.
- `Trojpolowki/ichimoku.md` uses compact continuation/watch/cloud/retest columns and keeps risk/context details only where they are relevant.
- The HTML report renders both 3P files as tabs, not as separate links; every 3P column and top-choice block has a `📊` StockHelper chart-open control, plus compact Stooq and Google-Sheets copy icons next to instruments.
- Top choices are intentionally selective: recent breakouts/patterns, returned-to-cloud/deep-cloud retest candidates, deeper Fibo pullbacks, and the strongest falling-wedge setups are prioritized.
- The `🔻 Kliny` tab groups falling wedges by market, keeps Stooq/StockHelper/Google-Sheets-copy controls next to each table, marks statuses as `⏳ unbroken` or `🚀 breakout`, and shows `Breakout date` plus `Breakout direction` (`long` for upper-line breakout, `short` for lower-line breakdown).
- Falling-wedge scanner rows are written at the end of Fibo markdown under `WYNIKI KLINY OPADAJĄCE`; wedges must pass the same Avg10d liquidity threshold used by Fibonacci formations, and the wedge tables include `Avg10d PLN`. A wedge remains valid only while no candle closes outside its boundaries, except for an accepted breakout/breakdown on the latest candle or within the last 5 candles, which becomes the absolute top-choice wedge case. The report keeps wedge table columns compact (months, touches, slope, breakout, size, score) and does not show fit/proximity/compression columns.
- WYNIKI 2 Ichimoku includes `Mies. respektu przed wybiciem`, showing how long the prior cloud side was respected before the breakout.
- Freshness probing samples up to five random instruments per run (instead of always the first five) so an interrupted refresh does not keep checking the same already-updated symbols on the next run.


**Common variants:**

```bash
python run -allsearch wig
python run -allsearch dax
python run -allsearch commodities
STOCKHELPER_COMMODITIES_WORKERS=3 python run -allsearch commodities
STOCKHELPER_COMMODITIES_SEQUENTIAL=1 python run -allsearch commodities
python run --open-allsearch-report all
```

### 8. Check average liquidity for one instrument

```bash
python run -checkavg XTB.WA
```

**Description:**

- Prints recent average turnover/liquidity metrics for a single instrument.

**When to use it:**

- You want to debug why a stock scanner result passed or failed liquidity filters.

**Output to expect:**

- Terminal liquidity metric output.

### 9. Debug Stooq web/table access

```bash
python run --debug-stooq CB.F
```

**Description:**

- Opens Stooq debug flow for one symbol.
- Captures attempted URLs, page content details, screenshot, and HTML/debug JSON artifacts.
- Does not update CSV cache unless `--debug-stooq-fetch` is added.

**When to use it:**

- Stooq web fallback returns no rows.
- You suspect CAPTCHA/rate limiting.
- Commodity data refresh is failing.

**Output files created:**

- `debug/stooq/<symbol>_debug.json`
- `debug/stooq/<symbol>.html`
- `debug/stooq/<symbol>.png`

**Common variants:**

```bash
python run --debug-stooq COFFEE
python run --debug-stooq CB.F --debug-stooq-fetch
python run --debug-stooq CB.F --inspector
STOCKHELPER_STOOQ_CAPTCHA_DEBUG=1 python run --debug-stooq CB.F
```

### 10. Fetch older cached history

```bash
python run --fetch-older-data --fetch-older-data-scope stocks --fetch-workers 4
```

**Description:**

- Extends local stock/forex CSV history by requesting older windows before the current oldest cached date.
- Commodities are intentionally excluded by the current implementation.
- Supports simple local parallelism and xdist-style sharding.

**When to use it:**

- Scanners need more history than currently cached. Broad scans do **not** perform older-history backfills automatically; this command is the explicit backfill path.
- You want a longer local history before running broad scans.

**Output files updated:**

- `data/stocks/*.csv`
- `data/forex/*.csv`

**Common variants:**

```bash
python run --fetch-older-data --fetch-older-data-scope forex
python run --fetch-older-data --xdist-worker-index 0 --xdist-worker-count 4
STOCKHELPER_FETCH_RETRY_ON_ZERO_BACKFILL=0 python run --fetch-older-data
```

## Debug commands

### Show CLI help

```bash
python run --help
python main.py --help
python main_stock.py --help
python -m chart_program --help
```

If these fail with `ModuleNotFoundError`, install dependencies first.

### Force cache-only mode

```bash
python run -onlycache -ichimoku_search wig
python run -onlycache -fibo_search commodities
python run -onlycache -allsearch all
```

Use this when remote data providers are slow, rate-limited, or unavailable and you trust local CSV files. `-onlycache` sets `STOCKHELPER_CACHE_ONLY=1` internally and skips the normal freshness probes, including the commodities freshness check.

### Force verbose Stooq logs

```bash
STOCKHELPER_STOOQ_DEBUG=1 python run -fibo_search commodities
```

Use this to see Stooq scraper progress and fallback decisions, including blank-page refreshes, VPN prompts, CAPTCHA attempts, and table extraction progress.

### Debug one scanner symbol

```bash
STOCKHELPER_DEBUG_SYMBOL=XTB.WA python run -ichimoku_search wig
```

Use this when a specific ticker is missing or has unexpected scanner status.

### Run a Stooq CAPTCHA/debug capture

```bash
STOCKHELPER_STOOQ_CAPTCHA_DEBUG=1 python run --debug-stooq CB.F --inspector
```

Use this when Stooq shows a CAPTCHA, limit page, blank table, or incomplete rows. `--inspector` is useful only in an environment with a desktop/X server. The source contains a manual-mode tip mentioning `STOCKHELPER_STOOQ_INTERACTIVE_CAPTCHA`, but the launcher-supported switch is `--inspector`.

In normal commodity scans, Stooq blank/no-table pages are handled before the inspector: the scraper refreshes a blank page before consent up to two times, then asks for VPN change and reloads, then tries OCR CAPTCHA solving before opening the headed inspector. CAPTCHA OCR attempts default to `5` and can be changed with `STOCKHELPER_STOOQ_CAPTCHA_ATTEMPTS`.

### Check syntax without running data downloads

```bash
python -m py_compile main.py main_stock.py scanner_search.py chart_program/main.py chart_program/level_selector.py
```

Use this after editing Python files. It compiles files but does not run imports/data downloads.

## Data sources and cache behavior

- `chart_program/chart_loader.py` is the main daily-data loader.
- Local CSV cache paths are generated by instrument type:
  - stocks: `data/stocks/<SYMBOL>.csv`
  - forex: `data/forex/<PAIR>.csv`
  - commodities: `data/commodities/<SYMBOL>.csv`
  - indices/memberships: `data/indices/`
- Chart mode deliberately loads cached data first (`STOCKHELPER_CACHE_ONLY=1` is set internally for the chart load) so the UI opens quickly.
- Scanner mode usually probes remote freshness first, then decides whether to refresh or use local cache; it refreshes the current window only and does not run older-history backfill implicitly.
- `--data-source auto|yahoo|stooq` is available in `chart_program` flows.

## Troubleshooting

### `ModuleNotFoundError: No module named 'pandas'` or `tabulate`

Dependencies are missing from the active Python environment.

```bash
poetry install
poetry run python run --help
```

Or activate your virtualenv and install the packages listed in `pyproject.toml`.

### `playwright` is installed but browser launch fails

Install the browser binaries:

```bash
poetry run playwright install chromium
```

If using `venv`:

```bash
python -m playwright install chromium
```

### Chart UI opens but snapshot export fails

Plotly static image export normally needs Kaleido:

```bash
pip install kaleido
```

Then re-run chart mode:

```bash
python run -c ena
```

### `Instrument config not found`

`python run <target>` only runs analysis for an existing config. Check the config folders:

```bash
find configs -maxdepth 2 -type f | sort
```

Create/update a config from chart mode:

```bash
python run -c <symbol-or-slug>
```

### Config name is ambiguous

The launcher accepts prefix/normalized matches. If a short slug matches multiple files, pass the full path:

```bash
python run configs/stocks/ena.py
```

### Scanner results look stale

Force a remote refresh:

```bash
STOCKHELPER_FORCE_REMOTE_REFRESH=1 python run -ichimoku_search wig
```

Or force cache-only if remote data is unreliable:

```bash
STOCKHELPER_CACHE_ONLY=1 python run -fibo_search wig
```

### Stooq returns blank pages, CAPTCHA, or rate-limit pages

Run debug capture:

```bash
STOCKHELPER_STOOQ_DEBUG=1 STOCKHELPER_STOOQ_CAPTCHA_DEBUG=1 python run --debug-stooq CB.F --inspector
```

Check `debug/stooq/` for JSON, HTML, and screenshots. If visible rows are correct and you want to merge them into commodity CSV cache, add `--debug-stooq-fetch`.

For `python run -allsearch commodities`, commodity Stooq web fetches run in bounded parallel mode by default (`STOCKHELPER_COMMODITIES_WORKERS=2`). If VPN/CAPTCHA handling becomes confusing, retry with `STOCKHELPER_COMMODITIES_SEQUENTIAL=1`; if Stooq is stable, you can cautiously increase workers. Blank/no-table pages before consent are refreshed twice before the VPN prompt is shown. When the scanner pauses for a VPN/CAPTCHA change, press **Enter** to continue after fixing the issue; type `q`/`n` only when you want to stop the scan.

### No scanner Markdown is created

Check that dependencies are installed and that the scanner scope is valid:

```bash
python run -ichimoku_search wig
python run -fibo_search wig
```

Expected report folders:

```text
chart_program/data/search/ichimoku/
chart_program/data/search/fibo/
Trojpolowki/
```

### Combined report does not open

Open the latest existing report manually:

```bash
python run --open-allsearch-report all
```

Or open the HTML file directly from:

```text
chart_program/data/all_insturments_search/allsearch/
```

The combined HTML includes tabs for the allsearch report, 3P Fibo, 3P Ichimoku, and `🔻 Kliny`. Use the `📄 Download PDF` button in the tab header to export the currently visible report view.

### Data history is too short

Extend stock/forex CSVs:

```bash
python run --fetch-older-data --fetch-older-data-scope stocks --fetch-workers 4
python run --fetch-older-data --fetch-older-data-scope forex --fetch-workers 4
```

Commodities are excluded from `--fetch-older-data` by the current implementation.

## Development notes

- Automated tests live under `tests/`; run `pytest -q` for the suite or targeted files such as `pytest -q tests/test_trojpolowki.py tests/test_stock_cfd_config.py`.
- Use `python -m py_compile ...` as a lightweight syntax check before/alongside tests.
- Avoid editing generated cache/report files unless the task specifically requires it.
- The executable launcher is named `run` and is intended to be called as `python run ...`.
