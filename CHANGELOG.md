# Changelog

All notable release changes for StockHelper are documented here.

The project currently documents release tags `1.0` through `7.5`, plus unreleased changes currently on `HEAD`. Each section summarizes the important feature work delivered up to that tag, with later sections describing what changed since the previous tag.

## [Unreleased]

- Added a 50-instrument ETF scanner market to allsearch, preserving the supplied international Yahoo tickers, fetching directly through Yahoo Finance, and storing its candles separately under `data/csv/etfs/`.

Compare: [`7.5...HEAD`](https://github.com/gwojacek/stockhelper/compare/7.5...HEAD)

## [7.4] - 2026-08-14

Tag: `7.5`
Compare: [`7.4...7.5`](https://github.com/gwojacek/stockhelper/compare/7.4...7.5)

### Added

- Added scanner support for user-saved Fibonacci and wedge drawings from the latest provider-qualified chart session, including directional commodity aliases.
- Added persisted chart-calculated wedge breakout state and calendar-time matching for saved wedge lines.
- Added draggable saved Fibonacci anchors whose scanner results are recalculated from the edited drawing.

### Changed

- Made saved wedge anchors and their visible projected boundaries take precedence over automatic scanner fallbacks, so touch and breakout evaluation matches the structure shown in the chart.
- Reused the Ichimoku candle snapshot for the Fibonacci phase of allsearch and merged a single missing Yahoo candle before Ichimoku scans, reducing redundant downloads while keeping the active candle current.
- Changed commodity and forex `--force-refresh` into a last-20-candle audit that refreshes only missing CSVs or caches containing at least two Yahoo-precision candles.
- Rebased contaminated commodity and forex cache tails from Stooq, including long binary-float Yahoo values already stored in CSVs, while limiting Yahoo freshness data to the newest candle.
- Expanded Stooq history-table and direct-CSV download paths for forex data and added consecutive consent-dialog handling for commodity scraping.

### Fixed

- Expired invalid saved Fibonacci drawings after two weeks so obsolete manual anchors no longer suppress automatic detection indefinitely.
- Preserved valid long and short Fibonacci impulses while refreshing shared allsearch data.
- Corrected Ichimoku breakout dates, far-cloud-edge validation, maintained breakout selection, retest counts, and stale retest-pattern suppression.
- Tightened hammer, harami, piercing-line, and cloud-contact validation to reject off-center or incomplete formations while accepting contained bullish harami candles.
- Prevented the chart-loader cache merge from restoring Yahoo-only rows after an authoritative Stooq-tail rebase and removed overlapping Yahoo-only dates during forced repairs.
- Limited audited forex repairs to the affected Stooq tail and handled repeated Stooq consent dialogs during browser downloads.

### Added

- Added scanner breakout direction and Fibo pattern name/date metadata to chart CLI commands, saved chart context, generated scanner reports, and report-launched chart commands.
- Added fixed candle-index scanner highlights with a dedicated clickable legend and hover tooltip for Ichimoku breakouts, post-breakout retest patterns, and Fibo 61.8 patterns.
- Added pattern-length-aware highlight spans: one candle for single-candle formations, two for engulfing/harami/piercing-line/dark-cloud-cover patterns, and three for morning/evening star formations. Multi-candle formations use one undivided outer box.
- Added legacy commodity pattern-date recovery and chart-side Fibo 61.8 dark-cloud-cover recovery, including OIL/`CB.F` metadata, Setup information, and highlights.

### Changed

- Fibo reversal scanning now records the final confirming candle as `Pattern date`, while allowing any candle in a connected one-, two-, or three-candle formation to provide the required 61.8 touch.
- Ichimoku chart highlights now use scanner direction and resolve nearby scanner transition dates to the first actual close beyond the requested cloud boundary, counting trading candles across weekends and inside-cloud transitions.
- Scanner highlights now use solid orange for breakouts and rose for patterns, stay attached to exact candles while zooming, and expose concise legend labels with detailed hover text.

### Fixed

- Fixed duplicated scanner legend entries during chart zoom and eliminated internal borders between candles in multi-candle pattern highlights.
- Fixed scanner/report metadata being lost when reopening Fibo charts, including commodity symbol aliases such as `OIL` to `CB.F`.
- Fixed late or wrong-side Ichimoku highlights observed around BRACOMP, LIN.DE, ALE.WA, ARM.US, ASML.US, and similar scanner confirmations.
- Fixed one-candle patterns being rendered with three-candle spans and suppressed invalid retest/pattern highlights on or before the breakout candle.

## [7.3] - 2026-07-29

Tag: `7.3`
Compare: [`7.2...7.3`](https://github.com/gwojacek/stockhelper/compare/7.2...7.3)

### Added

- Added a per-instrument Fibo dropout analyzer to the combined HTML report. The analyzer opens in a sidebar, runs the scanner's cache-only explain mode through the local report server, displays the complete rejection trace, and can copy a Codex-ready diagnostic.
- Added the report-server `/fibo-dropout-analysis` endpoint and bumped the report protocol to v21.
- Added explicit Fibo lifecycle handling for formations that return across 23.6 before touching 61.8, allowing them to move back to the early column and return to the waiting column if correction resumes.
- Added extended-sideways-base and independent-recent-impulse handling for automatic Fibo anchors, including current new-high re-anchoring and direction-aware broad-short preservation.

### Changed

- Refined Fibo peak, base, stale-cycle, deduplication, and per-ticker limiting rules. Long and short candidates now have independent limits, live 3P matches are preserved, and active re-anchored/opposite-direction formations clear obsolete dropout cards.
- Refined 3P routing so pure inclines remain in column one, 23.6-zone formations remain in the waiting column, fresh 61.8 touches stay in the near-61.8 column for their complete three-candle pattern window, and recent confirmed reversals use the valid-pattern column.
- Improved mirrored-short behavior for commodities, forex, DAX40, and Nasdaq-100, including broad decline preservation while the correction remains near its active recovery extreme.
- Made liquidity/turnover gates stock-only; commodity and forex Fibo/wedge candidates no longer depend on unavailable or unreliable volume metadata.
- Updated Ichimoku retest counting so one continuous cloud visit contributes only the pattern at its best local reaction extreme. A close back on the trend side completes that cycle; a later cloud visit starts a new retest.
- Improved chart symbol handling so commodity display names resolve to canonical Stooq cache paths, including `Natural Gas -> NG_F.csv`.
- Kept the chart viewport stable when users complete a manual Fibonacci drawing.

### Fixed

- Fixed valid WHEAT, OIL, COFFEE, COCOA, MBG.DE, MTX.DE, OPL, CTAS.US, ALV.DE, QIA.DE, and related formations being lost through liquidity lookup, historical-offset deduplication, stale-sideways, dominant-peak, ratio, or anchor-reset paths.
- Fixed false dark-cloud-cover/piercing-line matches whose first candle was doji-like, while retaining the small reopen tolerance required by futures.
- Fixed old opposite-direction or old-anchor cards remaining in the ten-day dropout history when the instrument is active under a current Fibo classification.
- Fixed report-launched Natural Gas charts failing in cache-only mode because the display name was used instead of its canonical storage symbol.

## [7.2] - 2026-07-21

Tag: `7.2`
Compare: [`7.1...7.2`](https://github.com/gwojacek/stockhelper/compare/7.1...7.2)

### Added

- Added a persistent current-balance control to Allsearch reports. The saved PLN balance is shared with every chart launched from the report and changes made in a chart are saved for later charts.
- Added a searchable instrument switcher to the chart sidebar, populated from StockHelper's locally cached stock, forex, commodity, and index candle data.
- Added automatic chart navigation as soon as an exact instrument suggestion is selected, without requiring a separate Open button.

### Changed

- Updated report-launched charts to communicate with the local report server for shared user settings and instrument navigation.
- Bumped the report-server protocol to v20 for the shared-balance and chart-navigation integration.

### Fixed

- Fixed the report-launcher protocol negotiation so Allsearch reports continue opening through the local HTTP server instead of falling back to a non-functional `file:///` URL.

## [7.1] - 2026-07-15

Tag: `7.1`
Compare: [`7.0...7.1`](https://github.com/gwojacek/stockhelper/compare/7.0...7.1)

### Added

- Added unified setup-information debug snapshots across Ichimoku, Fibonacci, and wedge scanner results so report and chart views expose richer context for detected setups.
- Added scanner metadata flags to the chart UI/report pipeline for clearer setup provenance and downstream rendering.
- Added PyCharm/IDE-friendly runnable report command documentation and copy-ready stock launcher examples.

### Changed

- Improved Trójpołówki, Fibonacci, and Ichimoku report presentation with per-ticker Fibonacci limiting, richer status labels, refined retest notes, info-level controls, and cleaner hidden-link/filtered-section handling.
- Refined report UI behavior with dark-mode styling, normalized top-chart widths, removed wedge score display noise, deduplicated Fibonacci columns/results, and improved report rendering JavaScript.
- Updated report/chart command handling so Docker-backed clickable `python run` flows and the local `stock` wrapper behave more consistently from IDEs and generated reports.

### Fixed

- Fixed journal/report server connection handling so generated HTML reports and journal actions stay reachable while being viewed.
- Fixed Ichimoku breakout bucketing and improved retest handling to reduce misleading Trójpołówki report groupings.
- Fixed 3P Fibo and Ichimoku market filters so selected markets are applied per instrument card, matching entries stay at the top of each 3P column, and `stock --open-allsearch-report all` refreshes stale HTML before serving it.
- Guarded Stooq bulk refresh attempts to avoid repeated duplicate downloads during scans.
- Removed repository-tracked Docker home cache artifacts.

## [7.0] - 2026-07-11

Tag: `7.0`
Compare: [`6.0...7.0`](https://github.com/gwojacek/stockhelper/compare/6.0...7.0)

### Added

- Added a Docker-first installation workflow with a `Dockerfile`, `docker-compose.yml`, `.dockerignore`, and `scripts/install-stock-command.sh` helper so StockHelper can run without local Python/Poetry/Playwright setup.
- Added the `stock` shortcut for day-to-day Docker-backed commands, report URL auto-opening, report-container cleanup, and generated-file permission repair.
- Added Docker image support for Playwright Chromium, OpenCV/native browser libraries, CPU-only PyTorch, and EasyOCR so Stooq CAPTCHA OCR works without installing the GPU/CUDA wheel stack.
- Added report-server support for Docker foreground mode, served report URL emission, `/journal-html` handling, direct report-launched chart execution, output-tail diagnostics, and fast-cache hints for recently generated reports.
- Added chart CLI forwarding for Ichimoku and Fibonacci/report options, including `--ichimoku-mode`, `--fibo-lines`, `--fibo-anchor-start`, `--fibo-anchor-end`, and `--fibo-right`.
- Added regression coverage for Yahoo-only instruments keeping about 18 months of recent history.

### Changed

- Updated README usage to make Docker + `stock` the easiest path, including a quick command table, copy-ready `stock ...` snippets for the repo-local Docker wrapper, update workflow after `git pull`, report/browser behavior, permissions, cleanup, and plain Docker alternatives.
- Changed Yahoo-primary/Yahoo-only chart data trimming to keep about 1.5 years of recent data instead of about 1 year.
- Improved all-search report behavior so local report URLs are printed/served for the host helper and report-launched charts can open faster from fresh all-search cache.
- Changed Docker runs to use the host UID/GID and a writable project-local Docker home while keeping Playwright browsers installed at `/ms-playwright` in the image.
- Reduced Docker image size and build fragility by bypassing the Poetry lock's GPU/CUDA PyTorch dependency path and installing CPU PyTorch/EasyOCR directly.
- Improved WIG/WIG20 bulk refresh documentation and behavior expectations so WIG20/index data imported from a successful WIG bulk zip can be reused by later index scans.

### Fixed

- Fixed Docker Compose argument handling so commands like `stock -allsearch all` or `docker compose run --rm --no-deps stockhelper -allsearch all` pass arguments to the container `python3 run` entrypoint instead of treating flags as executables.
- Fixed Docker report serving so containers stay alive while local HTML reports are being viewed.
- Fixed unwanted browser redirects to Stooq diagnostic URLs by making the `stock` helper auto-open only localhost StockHelper report URLs.
- Fixed Playwright browser lookup failures after non-root Docker runs by using the image-global `/ms-playwright` browser path.
- Fixed root-owned generated files from Docker workflows by running containers as the host user and adding `stock --fix-permissions` for older files.
- Hardened Stooq CSV writes with non-empty/required-column validation, atomic temp-file replacement, and readback sanity checks to avoid corrupt or truncated CSVs.
- Improved report-server chart failure diagnostics by capturing and returning recent child-process output.

## [6.0] - 2026-07-10

Tag: `6.0`
Compare: [`5.0...6.0`](https://github.com/gwojacek/stockhelper/compare/5.0...6.0)

### Added

- Added the transaction journal workflow with served report actions, trade review/editing, completed-position summaries, close-preview handling, and chart screenshots.
- Added journal close-adjust chart mode so closing trades can be reviewed and adjusted from dedicated chart views without affecting normal chart mode.
- Added calculation-currency support and FX-fee-aware position calculations in the chart UI, including improved calculation controls and report integration.
- Added quick-chart navigation and selected-value chart affordances to make report-linked chart inspection faster.
- Added Stooq Playwright proxy support and documented proxy usage for more resilient Stooq data collection.

### Changed

- Refined transaction journal layout, compression, action buttons, slider toggles, reason labels, bulk actions, summary editing, and full-journal embedding in all-search reports.
- Improved Fibo, 3P, Ichimoku, hammer, engulfing, and candlestick detection, including steep/mid-pullback handling, forex retest behavior, OPL cloud transitions, and matching-cell search filters.
- Tuned scanner/report behavior by restoring toggleable scanner filters, scoping filters to all-search reports, hiding empty groups, preserving 3P search columns, refreshing scan candles, and improving report icons.
- Tuned wedge selection and breakout freshness, including descending wedge lows and retained OPL flips.
- Updated generated market data/report artifacts and tightened project documentation, including the Python 3.12 requirement.

### Fixed

- Fixed generated journal JavaScript escaping, journal HTML actions, journal close chart opening, journal direction sync, and close-line screenshot synchronization.
- Stabilized Lightweight Charts bootstrap and scanner-launched chart rendering.
- Fixed index CSV cache completeness checks and commodity parsing for Stooq metal rows without volume.
- Improved Stooq blank-page fallback handling with WebKit and Firefox retry paths.
- Rejected flat Fibo anchors and fixed 3P tab search/report filtering edge cases.

## [5.0] - 2026-06-22

Tag: `5.0`
Compare: [`4.0...5.0`](https://github.com/gwojacek/stockhelper/compare/4.0...5.0)

### Added

- Added a wedge debug sidebar tool in the chart UI so scanner-loaded falling-wedge candidates can be inspected against their displayed anchors and touch candles.
- Added manual falling-wedge import/preservation support so user-edited wedge lines survive chart reloads, config updates, and scanner/report launches.
- Added alternate falling-wedge search/roulette controls, including directional next/previous buttons that cycle through other valid wedge structures directly from the chart.
- Added regression coverage for DAT.WA falling-wedge anchors and related stop-touch/manual-wedge behavior.
- Added generated EAT, PXM, and PZU chart/config artifacts from the updated chart workflow.

### Changed

- Reworked falling-wedge detection, scoring, and anchor selection to prefer longer structures, stronger upper-boundary touches, active lower/upper anchors, plateau highs, and older matching upper anchors.
- Tightened wedge touch and breakout handling with exact wick-contact rules, stop-touch rejection after breakout, stricter contact logic, and debug markers that match the displayed wedge line.
- Improved chart editing for lines and wedges with DOM overlay icons, reachable endpoint handles, live straight-line wedge boundaries, freeform extension handles, and reduced autoscale/flicker during level selection.
- Preserved cached candles when saving charts and refreshed latest candles before chart cache loads, reducing stale chart data while avoiding unnecessary cache replacement.
- Increased commodity Stooq fetch concurrency and automated pre-inspector blank/no-table retry handling for more reliable commodities scans.

### Fixed

- Fixed wedge alternative button cycling so alternate wedge candidates can be selected reliably.
- Fixed chart icon rendering, drawing-tool toggles, anchor-direction preservation, wedge auto-level behavior, and drag viewport stability.
- Fixed config matching/resolution edge cases and highlighted the 0.618 Fibonacci ratio more clearly in chart overlays.
- Hardened report-server/chart startup waits to reduce failures when opening report-linked charts.


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
