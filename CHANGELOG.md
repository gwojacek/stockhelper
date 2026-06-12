# Changelog

All notable release changes for StockHelper are documented here.

The project currently has four release tags: `1.0`, `2.0`, `3.0`, and `4.0`. Each section summarizes the important feature work delivered up to that tag, with later sections describing what changed since the previous tag.

## [4.0] - 2026-06-12

Tag: `4.0` (`966bc4c`)  
Compare: [`3.0...4.0`](https://github.com/gwojacek/stockhelper/compare/3.0...4.0)

### Added

- Added bullish-engulfing Ichimoku retest detection so scanner reports can identify a bullish engulfing candle followed by a retest of the Ichimoku context.
- Allowed engulfing retests that occur inside the Ichimoku cloud, avoiding missed setups when the retest candle is still within cloud boundaries.
- Documented the split data layout with placeholder files so CSV market data and runtime state/cache files have clearly separated homes.

### Changed

- Refined Fibonacci 61.8% pattern windows to better match the intended validation range for Fibo setups.
- Cleaned up downloaded market data handling after Fibo scans and data refreshes.
- Moved generated data into dedicated subfolders for clearer separation between instrument CSVs, search output, and cache/state artifacts.

### Fixed

- Fixed Fibonacci invalidation handling so invalidated patterns stop participating in later signal decisions.
- Fixed directional 23.6% to 61.8% progress checks in Fibo calculations.
- Stored index data under index-specific paths instead of mixing index caches with stock or commodity data.

## [3.0] - 2026-06-12

Tag: `3.0` (`a66a101`)  
Compare: [`2.0...3.0`](https://github.com/gwojacek/stockhelper/compare/2.0...3.0)

### Added

- Implemented a broader market-data retrieval pipeline for stocks, commodities, forex pairs, and indexes.
- Added Playwright-powered Stooq bulk download automation for WIG data, including consent/captcha handling and diagnostics.
- Added WIG20 bulk refresh support that refreshes missing or stale local CSVs before scans need them.
- Added Yahoo freshness merging so cached history can be extended with newer candles without replacing the full Stooq history.
- Added scanner worker override support to tune all-search scan concurrency.
- Documented data freshness behavior and symbol-routing decisions for the mixed Stooq/Yahoo data sources.

### Changed

- Refreshed Warsaw stock data with Yahoo latest candles while preserving Stooq historical data as the primary local cache.
- Routed forex and index scans through Yahoo-compatible symbols where applicable.
- Loaded WIG20 data from Stooq bulk files while using Yahoo for fresh latest candles.
- Used canonical commodity symbols and Yahoo primary feeds for API-backed metal commodities.
- Imported only WIG20 constituents from WSE index bulk data to avoid unnecessary local data churn.
- Used a KGH reference file to detect stale WIG20 index cache state more reliably.
- Trimmed WIG stock CSVs after bulk import to keep local data smaller.

### Fixed

- Avoided slow per-symbol Stooq API refreshes for Warsaw stock refreshes.
- Appended only newer Yahoo candles to cached market data, preventing duplicate historical rows.
- Added fallback to Yahoo when Warsaw Stooq lookup fails.
- Improved Stooq bulk download handling for duplicate downloads, invalid non-zip files, ad overlay interference, recurring consent prompts, captcha approval, and blank/error pages.
- Fixed CHN index Yahoo mapping and kept all-search scans running after lookup errors.
- Corrected Yahoo ticker mappings for indexes.

## [2.0] - 2026-06-08

Tag: `2.0` (`f592a43`)  
Compare: [`1.0...2.0`](https://github.com/gwojacek/stockhelper/compare/1.0...2.0)

### Added

- Added the major chart-rendering upgrade to TradingView Lightweight Charts for the interactive/report chart UI, replacing the older chart rendering path with a faster browser-native candlestick experience.
- Added an in-chart position calculation panel for report charts.
- Added calculation drawer controls, including vertical chart panning while calculations are open.
- Added display of FX conversion fee state in the compact chart calculation UI.
- Added terminal streaming for report chart output via the report console sink.

### Changed

- Opened report charts without an extra fetch round trip and waited for the chart server before redirecting from reports.
- Opened all-search reports without blocking the terminal.
- Detached report viewer/server processes where needed, then refined the flow to keep report server output attached to the console for easier debugging.
- Kept report chart calculations in the console flow rather than hiding failures in detached processes.
- Reworked the calculation panel layout: larger initial drawer height, compact tables, centered content, aligned headers, repositioned panel header, and larger table text.
- Improved report chart launch plumbing around the Lightweight Charts server flow, including redirect timing, process handling, and console visibility.

### Fixed

- Fixed report chart opening failures caused by stale console/report-server state.
- Made the report chart launcher resilient to stale browser/server processes and `ERR_EMPTY_RESPONSE` style failures.

## [1.0] - 2026-06-03

Tag: `1.0` (`9d25779`)

### Added

- Established the core StockHelper toolkit for checking trade ideas and scanning markets from reusable Python config files.
- Added position and risk analysis for stocks, forex pairs, commodities, and CFD/index-like instruments, including position size, capital used, potential loss, and risk/reward output.
- Added the short `python run <slug>` launcher that auto-detects stock, forex, or commodity configs and routes to the correct analysis workflow.
- Added config-first instrument definitions under `configs/stocks/`, `configs/forex/`, and `configs/commodities/` so setups can be reused and updated from chart workflows.
- Added market-data download and local CSV caching for stocks, forex, and commodities using Stooq, Yahoo Finance, and Stooq web/table fallback paths.
- Added scanner workflows for Ichimoku cloud setups, Fibonacci formations, all-search combined reports, single-symbol Fibo explanations, and average-liquidity checks.
- Added Markdown/HTML report generation, terminal output, cached CSV artifacts, debug JSON/HTML/screenshots, and chart image exports.
- Added the interactive browser chart editor for selecting price levels, saving/updating config files, toggling Ichimoku chart mode, and exporting chart snapshots.
- Included Trójpołówki (3P) watchlists by the `1.0` tag, generated from all-search output with compact Fibonacci and Ichimoku continuation/watchlist sections.
- Added falling-wedge detection and reporting for StockHelper.
- Integrated wedge detection into the Trójpołówki workflow.
- Added chart drawing support for wedge trendlines, breakout/retest context, and wedge report visualization.
- Added falling-wedge scanner report sections and controls, including recent breakout prioritization and active wedge selection.
- Added liquidity filtering for wedge results to reduce low-quality scanner matches.
- Added cache-only CLI support and logic to keep recent wedge breakouts available without forcing older-history backfills.
- Added stock CFD chart mode controls and 3P-column StockHelper chart buttons.
- Added report UI improvements such as icon-only action buttons and centered latest-data status icons.
- Added documentation for report/chart UX, Fibo behavior, and Stooq scan controls.

### Changed

- Refined Fibonacci 3P scan behavior across steep pullbacks, pullback-zone routing, stale-start resets, valid base selection, same-bottom deduplication, same-scale duplicate filtering, and close-bottom formation preference.
- Routed steep Fibo pullbacks into a dedicated 3P warning column and restricted the first 3P Fibo column to steep candidates.
- Reset after large completed Fibo cycles and rejected broad candidates after large 61.8% cycles.
- Improved falling-wedge anchors, chart traces, chart zoom stability, report ordering, report controls, and anchor validation.
- Prioritized fresh wedge breakouts and rejected stale breakout candidates in reports.
- Improved Ichimoku parallel scan progress reporting.
- Tuned Stooq/commodity scanning with bounded parallel scans, sequential commodity defaults, blank-page retries, and VPN/rate-limit pause handling.
- Refined stock CFD spread handling and disabled implicit older-history scan backfill.

### Fixed

- Fixed wedge anchor semantics so charted wedge lines are based on the intended session points.
- Fixed report button JavaScript newline handling.
- Aligned Fibo 3P and all-search Fibo rows.
- Excluded unsuccessful breakouts from top scanner choices.
