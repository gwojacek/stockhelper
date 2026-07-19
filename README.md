# StockHelper

StockHelper is a Python toolkit for quickly checking trade ideas and scanning markets.

It helps you:

- calculate position size, engaged capital, potential loss, and risk/reward for configured setups;
- work with stocks, forex pairs, commodities, and CFD/index-like instruments;
- download/cache daily market data from Stooq, Yahoo Finance, and Stooq web/table fallbacks;
- scan market groups for Ichimoku cloud, Fibonacci setups, and falling-wedge (Kliny) formations with age-aware breakout/retest handling, stale-Fibo-anchor rejection, improved 5.0 wedge anchor scoring, and alternate-wedge review;
- generate compact Trójpolówki (3P) Fibo/Ichimoku watchlists plus a dedicated Kliny tab from the latest allsearch data, with searchable/filterable HTML tabs and grouped quick-chart buttons;
- open an interactive chart tool, select price levels, inspect/import/edit wedge lines, save/update config files, export chart snapshots, and create transaction journal entries;
- review a local transaction journal with opening/closing screenshots, close-adjust chart mode, estimated P/L, and update/delete actions;
- generate terminal output plus Markdown/HTML reports, cached CSV data, debug JSON/HTML/screenshots, journal HTML, and chart images.

The project is practical and config-driven: most workflows start from a ticker/config slug, write reusable files under `configs/`, cache market data under `data/`, and save reports under `chart_program/data/`.

## Quick command table

Use this table as the fastest path to the commands you will run most often. The recommended install is Docker-backed and the day-to-day command is `stock ...`. Copy a command from the **Recommended command** column and paste it into the terminal. Detailed explanations and variants are later in [Most useful commands](#most-useful-commands) and [Install with Docker (easiest)](#install-with-docker-easiest).

| Use case | Recommended command | Short description |
| --- | --- | --- |
| Build Docker image | `docker compose build` | Builds the StockHelper image with Python, Playwright Chromium, CPU PyTorch/EasyOCR, and native runtime libraries. |
| Install/update `stock` shortcut | `./scripts/install-stock-command.sh` | Installs `~/.local/bin/stock`; rerun after `git pull` so the wrapper has the latest behavior. |
| Show launcher help | `stock --help` | Confirms the Docker-backed shortcut works and prints available launcher options. |
| Run a stock setup | `stock ena` | Auto-detects a stock config and prints position/risk output. |
| Run a forex/commodity setup | `stock eurpln_long` | Auto-detects a forex/commodity config and prints lot/risk output. |
| Open chart editor | `stock -c ena` | Opens the browser chart UI to select levels and save config/snapshot files. |
| Open chart with Ichimoku | `stock -c EUR/USD --ichimoku-mode on` | Opens chart mode with the Ichimoku overlay enabled. |
| Open stock as CFD | `stock -c AAPL.US cfd` | Opens a stock chart in CFD/commodity mode, with CFD sizing and spread as price units. |
| Open transaction journal | `stock --journal-html` | Opens the live journal HTML through the local report server so update/delete/close buttons work. |
| Prepare PDF journal | `stock --journal-pdf` | Opens the journal HTML and prompts you to use the browser/PDF button to save it as PDF. |
| Run Ichimoku scan | `stock -ichimoku_search wig` | Scans a market group and writes an Ichimoku Markdown report. |
| Run Fibonacci scan | `stock -fibo_search wig` | Scans a market group and writes a Fibonacci Markdown report. |
| Build combined report | `stock -allsearch all` | Runs scanners, refreshes latest candles, creates combined Markdown/HTML reports, and auto-opens the local HTML report URL. |
| Reopen combined report | `stock --open-allsearch-report all` | Opens the latest existing HTML all-search report in a new browser window. |
| Explain one Fibo symbol | `stock -fibo_search single -explain MPWR.US` | Shows why one symbol matched or failed Fibonacci rules. |
| Check liquidity | `stock -checkavg XTB.WA` | Prints recent average turnover/liquidity for one instrument. |
| Debug Stooq page | `stock --debug-stooq CB.F` | Saves Stooq debug JSON/HTML/screenshot artifacts. |
| Refresh WIG/WIG20 from Stooq bulk | `stock --download-wig-bulk` | Downloads Stooq `d_pl_txt`, solves consent/CAPTCHA with Playwright/EasyOCR, refreshes WIG stock CSVs, and imports WIG20/index data from the same zip. |
| Trim WIG stock CSVs | `stock --trim-wig-csvs` | Trims existing `data/csv/stocks/*_WA.csv` files to the last two years without downloading Stooq bulk data. |
| Use cache only | `stock -onlycache -ichimoku_search wig` | Avoids remote refresh/probing when you want to rely on local CSVs, including commodities. |
| Force refresh | `STOCKHELPER_FORCE_REMOTE_REFRESH=1 stock -fibo_search wig` | Ignores usable cache and refreshes market data. |
| Extend history | `stock --fetch-older-data --fetch-older-data-scope stocks --fetch-workers 4` | Backfills older stock CSV history. |
| Fix old Docker file ownership | `stock --fix-permissions` | Repairs root-owned generated files from older Docker runs; run the printed `sudo chown ...` command if needed. |
| Clean Docker disk usage | `stock --cleanup` | Stops StockHelper report containers, removes dangling images, and prunes unused build cache. |

If you intentionally use a local Poetry/Python install instead of Docker, run `STOCKHELPER_IN_DOCKER=1 python run ...` inside that environment to bypass the Docker redirect and execute the Python app directly.

## Commodity FIBO refresh and Stooq/Tor fallback

Commodity FIBO scans are intentionally quiet and sequential by default so Stooq/Tor is not hit by many workers at once. Run:

```bash
stock -fibo_search commodities
```

The scanner first does a fast freshness check against Yahoo and sets `STOCKHELPER_COMMODITIES_REFRESH_TICKERS` only for missing/stale commodities. Fresh commodity CSVs are read from cache; only stale symbols are refreshed through the Stooq UI fallback.

For Stooq web fallback, StockHelper auto-detects a reachable Tor SOCKS proxy at `socks5://127.0.0.1:9050`, or you can point Docker at a host Tor service:

```bash
docker compose run --rm \
  --add-host=host.docker.internal:host-gateway \
  -e STOCKHELPER_STOOQ_TOR_PROXY='socks5://host.docker.internal:9050' \
  stockhelper -fibo_search commodities
```

Normal output is kept minimal: one captcha/consent line per symbol and page progress lines such as `[stooq-web] progress page=5 collected=200`. Use `STOCKHELPER_STOOQ_DEBUG=1` or `STOCKHELPER_STOOQ_CAPTCHA_DEBUG=1` when you need detailed proxy, blank-page, inspector, OCR, HTML, and screenshot diagnostics under `debug/stooq/`.

## Features

- **Position/risk analysis** for stocks, forex, and commodities/CFDs.
- **Config-first workflow** using Python `TradingConfig` classes in `configs/stocks/`, `configs/forex/`, and `configs/commodities/`.
- **Short launcher**: `stock <slug>` auto-detects the config/instrument and calls the correct analysis script.
- **Market data download and cache**:
  - Yahoo Finance primary routing for forex, global indexes, and canonical metal futures (`GOLD -> GC=F`, `SILVER -> SI=F`, `PALLADIUM -> PA=F`);
  - Stooq API/CSV-style downloads for many stocks/forex/commodities;
  - Stooq web/table fallback for selected commodity data;
  - Yahoo fresh-candle merges into Stooq/local bases for Warsaw stocks, WIG20, and selected commodities;
  - Stooq bulk `d_pl_txt` refresh for Warsaw/WIG stock CSVs from the archive `wse stocks` txt folder, automatically trimmed to two years from the run date;
  - Stooq bulk `wse indices/wig20.txt` import as `data/csv/commodities/WIG20.csv` (other WSE index txt files are intentionally ignored);
  - local CSV cache in `data/csv/stocks/`, `data/csv/forex/`, `data/csv/commodities/`, and `data/state/indices/`.
- **Ichimoku cloud scanner** for WIG, DAX/DAX40, Nasdaq-100/US100, forex, commodities, or a single instrument, with breakout/retest metadata that can be forwarded into chart Setup information.
- **Fibonacci formation scanner** with long/short setup search, 23.6/61.8 retracement states, reversal-pattern checks, stale-anchor rejection when the first month after an anchor is flat, and an explain/debug mode.
- **Scanner candle-pattern checks** for hammer/shooting-star style one-candle rejections, engulfing, harami, piercing-line/dark-cloud-cover, and morning/evening star variants used by Ichimoku retests and Fibo 61.8 reversals.
- **Falling-wedge (Kliny) scanner** exported from the Fibo scan flow, including unbroken wedges and fresh breakouts (up to 5 candles after breakout), Avg10d liquidity filtering, stricter wick/contact validation, improved anchor scoring, and chart commands that preload wedge lines.
- **Trójpolówki (3P) watchlists** generated from allsearch output, with compact Fibo columns, compact Ichimoku continuation/watch/cloud/retest columns, market ordering, top choices, per-cell market/scanner metadata for filtering, per-column `📊` StockHelper bulk-open buttons, Stooq/Sheets controls, and PDF export from every report tab.
- **Quick charts from `📊` groups** in HTML reports: a group button opens the first chart and carries the rest as an in-chart quick-navigation panel, with visually grouped buttons for the original report source/column.
- **Liquidity/volume filters** for stock scanner output, including Avg10d PLN and GDP-adjusted thresholds.
- **Interactive chart tool** powered by TradingView Lightweight Charts, with manual level selection, optional Ichimoku overlay, optional Fibonacci/wedge lines, manual wedge preservation/import, alternate-wedge cycling controls, stock-CFD mode, clear-active-value controls, saved sessions, generated configs, chart snapshots, and a transaction-journal panel.
- **Setup information panel** in the chart UI for scanner-loaded setups: Ichimoku shows scanner breakout/retest context plus CSV candles from the scanner check window, Fibo shows anchor dates/values and 61.8 diagnostics, and wedge/Kliny shows touch diagnostics plus CSV candles since the oldest wedge anchor.
- **Transaction journal** stored locally under `data/journal/`, with opening screenshots, close-adjust chart screenshots, Trade Summary autosave, long/short direction, estimated profit/loss, compressed review mode, year filtering, delete/update/close actions, and PDF-friendly HTML output.
- **Reports and artifacts**:
  - Markdown scanner reports in `chart_program/data/search/ichimoku/` and `chart_program/data/search/fibo/`;
  - Trójpolówki Markdown watchlists in `Trojpolowki/fibo.md` and `Trojpolowki/ichimoku.md`;
  - combined Markdown/HTML scanner reports in `chart_program/data/all_insturments_search/allsearch/`;
  - chart snapshots in `charts/`;
  - transaction journal JSON/HTML/screenshots in `data/journal/`;
  - manual/session state in `data/state/sessions/`;
  - Stooq debug JSON/HTML/screenshots in `debug/stooq/`.
- **CAPTCHA/rate-limit support** for Stooq web and bulk-download fallback, including OCR attempts, saved artifacts, and optional Playwright inspector/manual mode.

Falling wedges are first-class scanner/report items. A separate generic triangle scanner is not documented as an available feature.

## Scanner candle patterns

StockHelper's scanner pattern names are intentionally stored as machine-friendly strings in reports and debug output. The scanner currently recognizes:

| Direction | Pattern names | Where used | Summary |
| --- | --- | --- | --- |
| Bullish / long | `hammer`, `bullish_engulfing`, `bullish_piercing_line`, `bullish_harami`, `morning_star`, `morning_doji_star` | Ichimoku above-cloud retests and long Fibo 61.8 reversals | Bullish rejection/reversal patterns that must touch the active cloud/level zone and reclaim the relevant threshold. |
| Bearish / short | `shooting_star`, `bearish_hammer`, `bearish_engulfing`, `bearish_harami`, `dark_cloud_cover`, `evening_star`, `evening_doji_star` | Ichimoku below-cloud retests and short Fibo 61.8 reversals | Bearish rejection/reversal patterns that must touch the active cloud/level zone and lose the relevant threshold. |

For Ichimoku, retest patterns are tied to the current cloud side: above-cloud setups search bullish patterns against the cloud top/bottom zone, while below-cloud setups search bearish patterns against the cloud bottom/top zone. For Fibo, patterns are tied to the 61.8 retracement and must include the first 61.8 touch window. The chart Setup information panel prefers scanner-provided pattern metadata when it is available.

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
├── data/                       # Cached market data, chart sessions, and transaction journal
└── charts/                     # Generated chart snapshots
```

## Installation

### Requirements

- Python `>=3.12,<4.0` (Python 3.12 or newer is required; older 3.10/3.11 environments are not supported).
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

### Install with Docker (easiest)

Docker is the recommended installation path if you do not want to manage a local Python/Poetry/Playwright setup. The image contains:

- Python 3.12 runtime dependencies needed by StockHelper.
- Playwright Chromium installed inside the image at `/ms-playwright`.
- CPU-only PyTorch plus EasyOCR for Stooq CAPTCHA OCR, avoiding the multi-GB GPU/CUDA wheel stack.
- Native libraries needed by OpenCV, EasyOCR, Playwright/Chromium, and the local chart/report web UIs.

The Compose setup mounts this repository into the container at `/app`, so generated CSVs, reports, screenshots, journal files, configs, and code changes from `git pull` stay on your host machine. It also runs the container as your host UID/GID so newly generated files are editable and deletable from your IDE/terminal.

#### First-time Docker setup

Build the image once:

```bash
docker compose build
```

Install the short `stock` command:

```bash
./scripts/install-stock-command.sh
```

The installer writes `~/.local/bin/stock`. If your shell cannot find `stock`, add this to `~/.bashrc` or `~/.zshrc` and restart the terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

After that, use `stock ...` in a normal terminal. The fastest examples are in the [Quick command table](#quick-command-table) above.

#### Updating after `git pull`

After pulling code changes, reinstall the wrapper so `stock` gets the newest helper behavior:

```bash
git pull
./scripts/install-stock-command.sh
```

Rebuild the Docker image only when Docker/package dependencies changed (for example `Dockerfile`, `pyproject.toml`, `poetry.lock`, Playwright/browser setup, or CPU EasyOCR/PyTorch changes):

```bash
docker compose build
```

Regular code changes are mounted from your working tree, so they usually do not need an image rebuild.

#### Command translation

With Docker, keep the same arguments you used before, but put `stock` in front. These are copy-ready terminal commands:

| Old local form | Recommended Docker command |
| --- | --- |
| `python run ena` | `stock ena` |
| `python run -c ena` | `stock -c ena` |
| `python run -allsearch all` | `stock -allsearch all` |
| `python run --open-allsearch-report all` | `stock --open-allsearch-report all` |
| `python run -ichimoku_search wig` | `stock -ichimoku_search wig` |

If you do not use the helper, the equivalent Compose form is:

```bash
docker compose run --rm --no-deps stockhelper -allsearch all
```

The Compose file sets the container entrypoint to `python3 run`, so arguments like `-allsearch all` are passed to StockHelper and are not treated as executables.

#### Reports, charts, and browser opening

Use `stock -allsearch all` for the normal all-search workflow. When the HTML report is ready, the helper watches Docker output and opens the first local StockHelper report URL (`http://127.0.0.1:...` or `http://localhost:...`) in a new Chrome/Chromium window, falling back to `xdg-open`/`gio`.

The helper intentionally ignores non-localhost URLs printed in scraper diagnostics. For example, Stooq bulk logs may print `https://stooq.com/db/d/?b=d_pl_txt`; that URL is not a StockHelper report and should not be opened by the helper.

Keep the terminal command running while you view the report. The container owns the local report server, so press `Ctrl+C` in that terminal when you are done. The helper stops older StockHelper report containers before starting a new report command unless you set:

```bash
export STOCKHELPER_KEEP_OLD_REPORTS=1
```

Report buttons open the journal through the report server directly, and report chart buttons launch `chart_program` directly inside the warm report container. If the served report is recent (default: 24 hours), chart buttons use fast cache mode because `-allsearch` already refreshed the latest candle before writing the HTML report; stale reports fall back to normal chart freshness checks.

For commands that launch a local web UI, Compose uses host networking because StockHelper binds chart/report servers to dynamic `127.0.0.1` ports.

#### Data freshness notes

- Warsaw WIG/WIG20 data uses the Stooq `d_pl_txt` bulk archive when a bulk refresh is needed.
- A successful WIG bulk refresh imports WIG stocks and WIG20/index data from the same zip, so the later indexes phase should reuse the refreshed local WIG20 CSV instead of downloading the same zip again.
- Yahoo-only instruments now keep about 1.5 years of recent data in runtime/chart flows, rather than only about 1 year.
- All-search is the default way to refresh latest candles before viewing the HTML report; report-launched charts can then open faster from the freshly generated cache.

#### File ownership and permissions

The Compose service runs as your host UID/GID through `STOCKHELPER_UID` and `STOCKHELPER_GID`, which the `stock` wrapper exports automatically. This prevents new files in `data/`, `charts/`, `chart_program/data/`, `Trojpolowki/`, `debug/`, and `configs/` from being created as root.

If an older Docker run already created root-owned files such as `data/csv/stocks/ALL_WA.csv`, fix existing host file ownership once:

```shell
stock --fix-permissions
```

If that prints a `sudo chown ...` command, run the printed command once. Future `stock ...` runs should create files as your user.

#### Docker disk cleanup

Report commands intentionally keep a container alive while the report server is open. Use this when you are done with reports or need disk space:

```shell
stock --cleanup
```

It stops/removes StockHelper containers, removes dangling Docker images, and prunes unused build cache. Manual equivalent:

```bash
docker ps -aq --filter "name=stockhelper" | xargs -r docker rm -f
docker image prune -f
docker builder prune -f
```

#### Plain Docker without Compose

Compose is preferred. If you do not use Docker Compose, build and run the image directly:

```bash
docker build -t stockhelper .
docker run --rm -it --network host \
  -e PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
  -e HOME=/app/.docker-home \
  -u "$(id -u):$(id -g)" \
  -v "$PWD:/app" \
  stockhelper -allsearch all
```

For chart/report UI commands on Linux, keep `--network host`; on Docker Desktop, enable host networking first or prefer Compose.

### Install with `venv` + `pip` instead

There is no `requirements.txt` in this repository. If you do not use Poetry, install the dependencies listed in `pyproject.toml` manually:

```bash
python -m venv .venv
source .venv/bin/activate
pip install colorama dash flask numpy pandas plotly tabulate tenacity playwright yfinance opencv-python easyocr
python -m playwright install chromium
```

### Optional/system dependencies

These packages are used by specific workflows:

- `playwright`: Stooq web/table fallback, Stooq debug pages, CAPTCHA/inspector workflows.
- `opencv-python`: CAPTCHA image preprocessing.
- `easyocr`: CAPTCHA OCR attempts.
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
| `STOCKHELPER_STOOQ_DEBUG` | `1` | Enables verbose Stooq scraper/debug logging. Also enabled by `stock --search-debug ...`. |
| `STOCKHELPER_STOOQ_CAPTCHA_DEBUG` | `1` | Prints extra CAPTCHA OCR/debug details and writes CAPTCHA debug screenshots. |
| `STOCKHELPER_STOOQ_CAPTCHA_ATTEMPTS` | `5` | Number of OCR CAPTCHA attempts before giving up/falling back. Default in code is `5`. |
| `STOCKHELPER_STOOQ_MAX_RUNTIME_S` | `900` | Watchdog timeout for Stooq web scraping. Code enforces at least 30 seconds. |
| `STOCKHELPER_COMMODITIES_WORKERS` | `6` | Worker count for bounded parallel commodity Stooq web scans. Default is `6`; lower it when Stooq/VPN/CAPTCHA handling is noisy. |
| `STOCKHELPER_COMMODITIES_SEQUENTIAL` | `1` | Forces commodity scans to single-threaded Stooq web fetching. Useful when VPN/CAPTCHA prompts are noisy. |
| `STOCKHELPER_STOOQ_BLANK_AUTO_RETRIES` | `3` | Automatic blank/no-table and pre-inspector CAPTCHA/limit Stooq reload attempts before falling back to alternate browser/inspector handling. |
| `STOCKHELPER_STOOQ_BLANK_PROMPT` | `1` | Restores the old manual “press Enter after VPN change” pause for blank/no-table Stooq pages. Default is automatic retry (`0`). |
| `STOCKHELPER_STOOQ_PROXY` | `http://user:pass@host:port` | Global proxy for Stooq Playwright browser launches. Applies to Chromium, Firefox fallback, inspector, and debug captures. |
| `STOCKHELPER_STOOQ_PROXY_METALS` | `http://user:pass@host:port` | Proxy only for metal Stooq symbols (`xauusd`, `xagusd`, `pl.f`, `pa.f`). Overrides the global proxy for those symbols. |
| `STOCKHELPER_STOOQ_PROXY_XAUUSD` / `_XAGUSD` / `_PL_F` / `_PA_F` | `http://user:pass@host:port` | Symbol-specific Stooq Playwright proxy. Highest priority for the matching metal. |
| `STOCKHELPER_STOOQ_PROXY_COUNTRY`, `_COUNTRY_METALS`, `_COUNTRY_XAUUSD` etc. | `PL` | Optional replacement for `{country}` inside the selected proxy string. Country targeting itself is provider-specific. |
| `STOCKHELPER_COMMODITIES_MIN_ROWS` | `250` | Minimum row count used by the post-run commodities CSV health check. |
| `STOCKHELPER_DEBUG_SYMBOL` | `XTB.WA` | Enables detailed scanner debug logs for one symbol. |
| `STOCKHELPER_DEFER_OPEN_LINKS` | `1` | Prevents scanner flows from prompting/opening all result links immediately. Used internally by batch reports. |
| `STOCKHELPER_BATCH_MODE` | `1` | Marks scanner execution as batch mode. Used internally by batch report workflows. |
| `STOCKHELPER_SCAN_WORKERS` | `1` | Overrides scanner worker count. Use `1` for sequential `-allsearch indexes`/VPN-safe scans; the `--scan-workers` CLI flag sets this internally. |
| `STOCKHELPER_STOOQ_BULK_INSPECTOR` | `1` | Opens Playwright inspector/manual mode for Stooq bulk `d_pl_txt` downloads. Also set by `stock --download-wig-bulk --inspector`. |
| `STOCKHELPER_STOOQ_BULK_DEBUG_DIR` | `debug/stooq_bulk` | Directory for Stooq bulk CAPTCHA/download screenshots and HTML attempt artifacts. |
| `STOCKHELPER_DISABLE_WIG_BULK_REFRESH` | `1` | Disables automatic WIG/WIG20 Stooq bulk refresh attempts during scanner freshness probes. |
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

## Market data freshness and symbol routing

StockHelper deliberately mixes data sources so scans use the freshest daily candles without replacing reliable historical bases unnecessarily.

### Source rules

- **Forex and global index-like instruments** (`US500`, `US100`, `DE40`, `FRA40`, `JP225`, etc.) use Yahoo Finance as the primary source.
- **Canonical metals** now use Stooq web/table symbols like other literal commodities:
  - `GOLD` -> Stooq `xauusd` -> `data/csv/commodities/XAUUSD.csv`
  - `SILVER` -> Stooq `xagusd` -> `data/csv/commodities/XAGUSD.csv`
  - `PLATINUM` -> Stooq `pl.f` -> `data/csv/commodities/PL_F.csv`
  - `PALLADIUM` -> Stooq `pa.f` -> `data/csv/commodities/PA_F.csv`
- **Search groups still use canonical display names** (`GOLD`, `SILVER`, `PLATINUM`, `PALLADIUM`), but fetch/cache paths are based on the mapped Stooq symbols above.
- **Warsaw stocks/WIG** use Stooq bulk (`d_pl_txt` / `wse stocks`) as the historical base. After Warsaw close, Yahoo is probed to append fresh `.WA` candles when only the newest session is missing. The first WIG/index scanner freshness check after 03:00 Warsaw time downloads Stooq bulk once per Warsaw date so the local WIG base is refreshed before Yahoo fresh-candle merges.
- **WIG20** uses Stooq as the base (`wse indices/wig20.txt` imported to `data/csv/commodities/WIG20.csv`) and Yahoo only for a newer `WIG20.WA` candle. If WIG20 appears to be missing more than one session, StockHelper triggers Stooq bulk first.
- **Literal commodities** such as cocoa/coffee/oil keep Stooq web/table as the base when needed, with optional Yahoo fresh-candle merges.

### Useful freshness commands

```bash
# Refresh Warsaw stocks and WIG20 from Stooq bulk.
# Imports all WSE stocks into data/csv/stocks/*_WA.csv, trims stock CSVs to two years,
# and imports only wse indices/wig20.txt into data/csv/commodities/WIG20.csv.
stock --download-wig-bulk

# Trim existing Warsaw stock CSVs to two years without downloading anything.
stock --trim-wig-csvs

# Keep a different number of years if needed.
stock --trim-wig-csvs --wig-trim-years 3

# Inspect the Stooq bulk CAPTCHA/download flow interactively.
stock --download-wig-bulk --inspector

# Run indexes sequentially (useful for VPN/rate-limit safety).
stock -allsearch indexes --scan-workers 1

# Run commodity allsearch with canonical metal names (GOLD, SILVER, PLATINUM, PALLADIUM).
stock -allsearch commodities --scan-workers 1
```

### Expected cache filenames

```text
data/csv/commodities/XAUUSD.csv     # Stooq xauusd (GOLD)
data/csv/commodities/XAGUSD.csv     # Stooq xagusd (SILVER)
data/csv/commodities/PL_F.csv       # Stooq pl.f (PLATINUM)
data/csv/commodities/PA_F.csv       # Stooq pa.f (PALLADIUM)
data/csv/commodities/WIG20.csv      # Stooq bulk wse indices/wig20.txt + optional Yahoo WIG20.WA fresh candle
data/csv/stocks/*_WA.csv               # Stooq bulk wse stocks, automatically trimmed to two years
```

## Most useful commands

Run the examples from the repository root.

### 1. Run analysis for an existing stock config

```shell
stock ena
```

**Description:**

- Finds a matching file in `configs/stocks/` using case-insensitive/normalized matching.
- Calls `main_stock.py` automatically.
- Calculates shares, engaged capital, potential loss, loss %, optional take-profit/risk-reward, stock liquidity metrics, and warnings.
- Uses Stooq-backed local data where possible and updates cache under `data/csv/stocks/`.

**When to use it:**

- You already have a stock config and want a quick position-size/risk check.

**Output to expect:**

- A terminal table with risk levels and position sizes.
- Warnings if liquidity/risk-reward checks fail.
- Updated cached data in `data/csv/stocks/` when data is refreshed.

**Common variants:**

```bash
stock xtb
stock configs/stocks/ena.py
python main_stock.py --config configs/stocks/ena.py
```

### 2. Run analysis for a forex or commodity config

```bash
stock eurpln_long
stock cocoa_short
```

**Description:**

- Finds a matching file in `configs/forex/` or `configs/commodities/`.
- Calls `main.py` automatically.
- Calculates lots, engaged capital, potential loss with spread, loss %, and risk/reward checks.

**When to use it:**

- You want to validate an existing forex/commodity/CFD setup.

**Output to expect:**

- A terminal risk table and position analysis.
- Updated cached data in `data/csv/forex/` or `data/csv/commodities/` when data is refreshed by the workflow.

**Common variants:**

```bash
stock usd_pln_short
stock gold_short
python main.py --config configs/commodities/Cocoa_short.py
```

### 3. Open the interactive chart/config tool

```shell
stock -c ena
```

**Description:**

- Opens the TradingView Lightweight Charts UI in your browser.
- Loads cached data first, with data provider fallback support.
- Lets you click/select levels such as high, low, entry, stop loss, optional check/risk-reward levels, and drawn objects; the active level can be cleared from the sidebar.
- Includes a **Transaction journal** button for saving the current setup, selected technique/reason, transaction amount/currency, notes, calculated context, and chart screenshot.
- When launched from the journal for closing a trade, the chart opens in a focused close-adjust mode where only ENTRY, SOLD, and SL lines are edited before saving the closing screenshot back into the journal.
- Stock charts include a CFD mode toggle; `stock -c AAPL.US cfd` opens the same symbol directly with CFD sizing inputs enabled. Stock CFDs use lot/deposit cost plus spread entered as price units with pips shown as `spread / 0.01`, so no separate pip-value field is required.
- Saves a config and chart snapshot when you click **Finish**.

**When to use it:**

- You want to create or update a `TradingConfig` from chart levels instead of editing Python files manually.

**Output files created/updated:**

- Config: `configs/stocks/<slug>.py`, `configs/forex/<slug>_<long|short>.py`, or `configs/commodities/<slug>_<long|short>.py`.
- Chart snapshot: `charts/<config>_levels.png`.
- Session state: `data/state/sessions/<config>.json`.
- Cached market data: `data/<group>/<symbol>.csv`.

### 3a. Use the transaction journal

```bash
stock --journal-html
stock --journal-pdf
```

**Description:**

- `stock --journal-html` writes `data/journal/transactions.html` and opens it through the local report server when possible. Use this served URL for update/delete/close buttons; opening the file directly is read-only for browser security.
- Journal entries are created from the chart sidebar with **Add journal entry** and stored in `data/journal/transactions.json`. Screenshots are stored in `data/journal/screenshots/`.
- The journal supports editable Trade Summary fields, manual notes, compressed mode, year filtering, bulk delete, and closing entries with profit/loss estimation from entry, sold price, and long/short direction.
- To capture a closing screenshot, open the close-adjust chart from a journal entry, adjust ENTRY/SOLD/SL lines, and accept the screenshot. This special chart mode is only for journal closing; normal `stock -c <symbol>` chart sessions keep all normal chart features.
- `stock --journal-pdf` opens the same journal view and reminds you to use the PDF/download/print flow.

**Output files created/updated:**

- Journal JSON: `data/journal/transactions.json`.
- Journal HTML: `data/journal/transactions.html`.
- Journal screenshots: `data/journal/screenshots/*.png`.

**Common variants:**

```bash
stock -c AAPL.US
stock -c AAPL.US cfd
stock -c EUR/USD --ichimoku-mode on
stock -c TRN --fibo-lines 5 --fibo-anchor-start 2026-01-30 --fibo-anchor-end 2026-05-21 --fibo-right
python -m chart_program jsw --instrument stock --data-source stooq --no-run-after-save
```

### 4. Run an Ichimoku scanner

```shell
stock -ichimoku_search wig
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
stock -ichimoku_search all
stock -ichimoku_search commodities
stock -ichimoku_search forex
STOCKHELPER_DEBUG_SYMBOL=XTB.WA stock -ichimoku_search wig
```

### 5. Run a Fibonacci scanner

```shell
stock -fibo_search wig
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
stock -fibo_search all
stock -fibo_search dax
stock -fibo_search us100
stock -fibo_search commodities
```

### 6. Explain one Fibonacci scanner result

```bash
stock -fibo_search single -explain MPWR.US
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
stock -fibo_search wig -explain XTB.WA
stock -fibo_search commodities -explain GOLD
```

### 7. Run combined Ichimoku + Fibonacci reports

```shell
stock -allsearch all
```

**Description:**

- Runs Ichimoku and Fibonacci scanning and combines the outputs.
- Regenerates compact Trójpolówki Markdown watchlists from the same allsearch run (no second instrument scan).
- Builds a browser-friendly HTML report and a Markdown report.
- Embeds four HTML tabs: `ALLSEARCH REPORT`, `3P FIBO`, `3P ICHIMOKU`, and `🔻 Kliny`.
- Adds top-choice sections, sortable/filterable tables, a search toolbar with market buttons and Allsearch-only scanner buttons, group Stooq-open buttons, StockHelper chart-open buttons, and a PDF export button that works from every tab.
- Opens/serves the HTML report via the local report server when possible.
- Includes an **Open journal** button that runs `stock --journal-html` in a separate served window; the journal is separate from scanner result generation and does not remove instruments from the scanner report.

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
- The HTML report renders both 3P files as tabs, not as separate links; every 3P cell carries market/scanner metadata so the toolbar can filter instruments in-place without collapsing columns. Every 3P column and top-choice block has a `📊` StockHelper chart-open control, plus compact Stooq and Google-Sheets copy icons next to instruments. Grouped `📊` controls open one chart first and then show the rest of that button's instruments in the chart sidebar as quick buttons grouped by the originating section/source.
- Top choices are intentionally selective: recent breakouts/patterns, returned-to-cloud/deep-cloud retest candidates, deeper Fibo pullbacks, and the strongest falling-wedge setups are prioritized.
- The `🔻 Kliny` tab groups falling wedges by market, keeps Stooq/StockHelper/Google-Sheets-copy controls next to each table, hides empty market groups while filtering, marks statuses as `⏳ unbroken` or `🚀 breakout`, and shows `Breakout date` plus `Breakout direction` (`long` for upper-line breakout, `short` for lower-line breakdown).
- Falling-wedge scanner rows are written at the end of Fibo markdown under `WYNIKI KLINY OPADAJĄCE`; wedges must pass the same Avg10d liquidity threshold used by Fibonacci formations, and the wedge tables include `Avg10d PLN`. A wedge remains valid only while no candle closes outside its boundaries, except for an accepted breakout/breakdown on the latest candle or within the last 5 candles, which becomes the absolute top-choice wedge case. Touch counts are based on anchor candles plus separate local-extreme wick contacts on the wedge boundary, matching the chart markers: larger anchor dots and smaller colored touch dots. In 5.0, wedge scoring favors longer structures with stronger boundary touches, active anchors, and exact wick-contact debug markers; report chart links can also expose alternate wedge candidates in the chart UI. The report keeps wedge table columns compact (months, touches, slope, breakout, size, score) and does not show fit/proximity/compression columns.
- WYNIKI 2 Ichimoku includes `Mies. respektu przed wybiciem`, showing how long the prior cloud side was respected before the breakout.
- Freshness probing samples up to five random instruments per run (instead of always the first five) so an interrupted refresh does not keep checking the same already-updated symbols on the next run.


**Common variants:**

```bash
stock -allsearch wig
stock -allsearch dax
stock -allsearch commodities
stock -allsearch indexes --scan-workers 1
STOCKHELPER_COMMODITIES_WORKERS=3 stock -allsearch commodities
STOCKHELPER_COMMODITIES_SEQUENTIAL=1 stock -allsearch commodities
stock --open-allsearch-report all
```

### 8. Check average liquidity for one instrument

```bash
stock -checkavg XTB.WA
```

**Description:**

- Prints recent average turnover/liquidity metrics for a single instrument.

**When to use it:**

- You want to debug why a stock scanner result passed or failed liquidity filters.

**Output to expect:**

- Terminal liquidity metric output.

### 9. Debug Stooq web/table access

```bash
stock --debug-stooq CB.F
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
stock --debug-stooq COFFEE
stock --debug-stooq CB.F --debug-stooq-fetch
stock --debug-stooq CB.F --inspector
STOCKHELPER_STOOQ_CAPTCHA_DEBUG=1 stock --debug-stooq CB.F
```

### 10. Fetch older cached history

```bash
stock --fetch-older-data --fetch-older-data-scope stocks --fetch-workers 4
```

**Description:**

- Extends local stock/forex CSV history by requesting older windows before the current oldest cached date.
- Commodities are intentionally excluded by the current implementation.
- Supports simple local parallelism and xdist-style sharding.

**When to use it:**

- Scanners need more history than currently cached. Broad scans do **not** perform older-history backfills automatically; this command is the explicit backfill path.
- You want a longer local history before running broad scans.

**Output files updated:**

- `data/csv/stocks/*.csv`
- `data/csv/forex/*.csv`

**Common variants:**

```bash
stock --fetch-older-data --fetch-older-data-scope forex
stock --fetch-older-data --xdist-worker-index 0 --xdist-worker-count 4
STOCKHELPER_FETCH_RETRY_ON_ZERO_BACKFILL=0 stock --fetch-older-data
```

## Debug commands

### Show CLI help

```bash
stock --help
python main.py --help
python main_stock.py --help
python -m chart_program --help
```

If these fail with `ModuleNotFoundError`, install dependencies first.

### Force cache-only mode

```bash
stock -onlycache -ichimoku_search wig
stock -onlycache -fibo_search commodities
stock -onlycache -allsearch all
```

Use this when remote data providers are slow, rate-limited, or unavailable and you trust local CSV files. `-onlycache` sets both `STOCKHELPER_CACHE_ONLY=1` and the internal `STOCKHELPER_USER_ONLYCACHE=1` marker, skips normal freshness probes, and prevents the scanner from merging fresh Yahoo candles for that run. Without explicit `-onlycache`, automatic cache gating may still be temporarily relaxed per symbol so calculations can use the newest available candle.

### Force verbose Stooq logs

```bash
STOCKHELPER_STOOQ_DEBUG=1 stock -fibo_search commodities
```

Use this to see Stooq scraper progress and fallback decisions, including blank-page refreshes, VPN prompts, CAPTCHA attempts, and table extraction progress.

### Debug one scanner symbol

```bash
STOCKHELPER_DEBUG_SYMBOL=XTB.WA stock -ichimoku_search wig
```

Use this when a specific ticker is missing or has unexpected scanner status.

### Run a Stooq CAPTCHA/debug capture

```bash
STOCKHELPER_STOOQ_CAPTCHA_DEBUG=1 stock --debug-stooq CB.F --inspector
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
  - stocks: `data/csv/stocks/<SYMBOL>.csv`
  - forex: `data/csv/forex/<PAIR>.csv`
  - commodities: `data/csv/commodities/<SYMBOL>.csv`
  - indices/memberships: `data/state/indices/`
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

```shell
stock -c ena
```

### `Instrument config not found`

`stock <target>` only runs analysis for an existing config. Check the config folders:

```bash
find configs -maxdepth 2 -type f | sort
```

Create/update a config from chart mode:

```bash
stock -c <symbol-or-slug>
```

### Config name is ambiguous

The launcher accepts prefix/normalized matches. If a short slug matches multiple files, pass the full path:

```bash
stock configs/stocks/ena.py
```

### Scanner results look stale

Force a remote refresh:

```bash
STOCKHELPER_FORCE_REMOTE_REFRESH=1 stock -ichimoku_search wig
```

Or force cache-only if remote data is unreliable:

```bash
STOCKHELPER_CACHE_ONLY=1 stock -fibo_search wig
```

### Stooq returns blank pages, CAPTCHA, or rate-limit pages

Run debug capture:

```bash
STOCKHELPER_STOOQ_DEBUG=1 STOCKHELPER_STOOQ_CAPTCHA_DEBUG=1 stock --debug-stooq CB.F --inspector
```

Check `debug/stooq/` for JSON, HTML, and screenshots. If visible rows are correct and you want to merge them into commodity CSV cache, add `--debug-stooq-fetch`.

For `stock -allsearch commodities`, commodity Stooq web fetches run in bounded parallel mode by default (`STOCKHELPER_COMMODITIES_WORKERS=6`). If VPN/CAPTCHA handling becomes confusing, retry with `STOCKHELPER_COMMODITIES_SEQUENTIAL=1` or lower the worker count. Blank/no-table pages and CAPTCHA/limit states just before Playwright inspector are refreshed automatically (`STOCKHELPER_STOOQ_BLANK_AUTO_RETRIES=3`), then a Firefox Playwright fallback can be tried for blank Chromium pages before the headed inspector. Set `STOCKHELPER_STOOQ_BLANK_PROMPT=1` only when you explicitly want the old pause-before-retry behavior. After commodities scans, StockHelper prints a `[commodity-check]` CSV row-count summary using `STOCKHELPER_COMMODITIES_MIN_ROWS` (default `250`).

#### Stooq Playwright proxies

Proxy support is optional and is applied only to Playwright browser launches used for Stooq web/debug scraping. It does not change Yahoo requests or non-Playwright downloads. Priority is:

1. symbol-specific proxy, e.g. `STOCKHELPER_STOOQ_PROXY_XAUUSD`;
2. metals-wide proxy, `STOCKHELPER_STOOQ_PROXY_METALS`, for `xauusd`, `xagusd`, `pl.f`, `pa.f`;
3. global Stooq proxy, `STOCKHELPER_STOOQ_PROXY`.

Examples:

```bash
# One proxy for all Stooq Playwright traffic.
export STOCKHELPER_STOOQ_PROXY='http://user:pass@host:port'

# One proxy for metals only.
export STOCKHELPER_STOOQ_PROXY_METALS='http://user:pass@host:port'

# Per-metal proxy.
export STOCKHELPER_STOOQ_PROXY_XAUUSD='http://gold-user:gold-pass@host:port'
export STOCKHELPER_STOOQ_PROXY_XAGUSD='http://silver-user:silver-pass@host:port'

# Provider-specific country targeting using a placeholder.
export STOCKHELPER_STOOQ_PROXY_METALS='http://customer-{country}:pass@host:port'
export STOCKHELPER_STOOQ_PROXY_COUNTRY_METALS='PL'
stock -allsearch commodities
```

Country targeting is proxy-provider-specific: StockHelper only substitutes `{country}` in the proxy string and passes the resulting proxy settings to Playwright. Put country information where your provider expects it, usually in the username, host, or port.

#### Tor circuit isolation pool

For concurrent Stooq UI sessions, edit `/etc/tor/torrc` on Ubuntu (the path can
differ on other systems) and configure the Tor SOCKS listener:

```text
SocksPort 9050 IsolateSOCKSAuth
```

Restart Tor after changing `torrc` (`sudo systemctl restart tor`). StockHelper
assigns a different SOCKS username/password slot to successive browser sessions,
so Tor places those streams on isolated circuits. Because Chromium does not
support SOCKS5 authentication itself, StockHelper automatically creates one
local HTTP CONNECT bridge per slot and applies the SOCKS credentials between
that bridge and Tor. The first slot is randomized and subsequent sessions rotate
through the pool. The default pool has 16 slots:

```bash
STOCKHELPER_STOOQ_TOR=1 \
STOCKHELPER_STOOQ_TOR_AUTH_POOL_SIZE=16 \
./stock -search forex
```

Set `STOCKHELPER_STOOQ_TOR_ISOLATE_SOCKS_AUTH=0` to disable credentials for a
Tor installation that does not use `IsolateSOCKSAuth`. Circuit isolation does
not guarantee that every circuit has a different exit relay; Tor makes the
final path selection.

After the forex coverage summary, warned CSVs are retried for up to four Tor
circuit rounds by default. Only files that remain incomplete enter the next
round. Tune the behavior when needed:

```bash
export STOCKHELPER_FOREX_HEALTH_RETRY_ROUNDS=4
export STOCKHELPER_FOREX_HEALTH_RETRY_DELAY=3
export STOCKHELPER_FOREX_HEALTH_WORKERS=4
```

The delay is multiplied by the completed round (3s, 6s, 9s by default), giving
Tor and Stooq time between denial or timeout responses.

### No scanner Markdown is created

Check that dependencies are installed and that the scanner scope is valid:

```bash
stock -ichimoku_search wig
stock -fibo_search wig
```

Expected report folders:

```text
chart_program/data/search/ichimoku/
chart_program/data/search/fibo/
Trojpolowki/
```

### Combined report does not open

Open the latest existing report manually:

```shell
stock --open-allsearch-report all
```

Or open the HTML file directly from:

```text
chart_program/data/all_insturments_search/allsearch/
```

The combined HTML includes tabs for the allsearch report, 3P Fibo, 3P Ichimoku, and `🔻 Kliny`. Use the search box and market buttons across tabs; the Ichimoku/Fibo scanner buttons are shown only on the Allsearch tab and can be clicked again to clear the scanner filter. Use the `📄 Download PDF` button in the tab header to export the currently visible report view.

### Data history is too short

Extend stock/forex CSVs:

```bash
stock --fetch-older-data --fetch-older-data-scope stocks --fetch-workers 4
stock --fetch-older-data --fetch-older-data-scope forex --fetch-workers 4
```

Commodities are excluded from `--fetch-older-data` by the current implementation.

## Development notes

- Automated tests live under `tests/`; run `pytest -q` for the suite or targeted files such as `pytest -q tests/test_trojpolowki.py tests/test_stock_cfd_config.py`.
- Use `python -m py_compile ...` as a lightweight syntax check before/alongside tests.
- Avoid editing generated cache/report files unless the task specifically requires it.
- The Docker helper is named `stock` and is intended to be called as `stock ...`; local development can still call `python run ...` inside a prepared Python/Poetry environment.
