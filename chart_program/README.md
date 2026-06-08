# Chart Program (Standalone)

Interactive chart-based tool for selecting trading levels and generating/updating config files.

---

## 1) How to run

Recommended:

```bash
python -m chart_program
```

You can also pass target directly:

```bash
python -m chart_program jsw
python -m chart_program mbr
python -m chart_program algt.us
python -m chart_program usdpln
python -m chart_program "algt.us cfd"
python -m chart_program algt.us cfd
```

The `"algt.us cfd"` / `algt.us cfd` form is supported and forces **commodity/CFD** behavior for that symbol while preserving stock-style symbol lookup.

---

## 2) What gets created/updated

- Config files are always written to project root:
  - `configs/stocks/*.py`
  - `configs/commodities/*.py`
  - `configs/forex/*.py`
- Downloaded candles are cached under `data/`.
- Session state is stored under `data/sessions/`.
- Chart snapshots are saved under `charts/`.

Each generated config includes:

- top-level `filename = "<config_file_stem>"`
- `TradingConfig` dataclass with selected levels and risk fields.
- for stocks, `market_data_source` is persisted and later used in stock summary output.

---

## 3) Symbol handling

### Stocks

- Polish examples: `jsw`, `mbr`, `kghm` (defaults to `.WA` when suffix is missing).
- Foreign examples: `algt.us` (US suffix supported).

### Forex

- `usdpln`, `eurusd`, `audusd`
- `USD/PLN`, `EUR/USD`, `AUD/USD`

### Commodities

- Plain names: `gold`, `silver`, `coffee`, `wheat`, etc.
- Futures-like aliases are supported (e.g. `.f`, `=f` forms in provider mapping).
- Adding `cfd` suffix (e.g. `"algt.us cfd"` or `python run -c algt.us cfd`) forces instrument type to commodity/CFD mode. Stock CFD mode uses lot/deposit cost and spread in price units; pips are displayed from that spread, without a separate pip-value input, and generated configs keep `stock_cfd_mode` metadata.

---

## 4) UI guide

- Left panel:
  - candlestick chart
  - level selection buttons: `HIGH`, `LOW`, `ENTRY`, `STOP LOSS`, `CHECK_ZR`, `LINE_CROSS`
  - drawing tools: `Line`, `Fib 61.8`, `Half→SL`
  - scanner-preloaded Fibonacci/wedge lines when opened from reports
  - Ichimoku cloud toggle
- Right panel:
  - instrument type
  - `Name/Ticker` display
  - selected values and a clear-active-value control for removing an already-clicked level
  - CFD mode toggle for stock charts
  - manual fields (`capital`, `lot_cost`, `pip_value`, `spread`; stock CFD hides `pip_value` and uses spread as price units)
  - `FX conversion fee 1%` toggle (default ON for foreign stocks and forex pairs without PLN)
  - drawn object management

### Drawing behavior

- You can pan/zoom with mouse and wheel.
- Line/Fib points are selected via chart clicks.
- Line tool now shows a live preview after first anchor and before second click.
- The chart x-range is padded before/after available candles so lines can be drawn beyond the raw candle window.
- For responsiveness, chart renders only the latest ~**1.5 years** of candles (about 548 days) even if local CSV contains longer history.

---

## 5) Data source options

- `--data-source auto` (default)
  - stock/forex: Yahoo then Stooq fallback
  - commodity: Stooq then Yahoo fallback
- `--data-source yahoo`
- `--data-source stooq`

Optional:

- `--api-key <key>` for Stooq variants (`apikey`, `api_key` on `stooq.pl` and `stooq.com`).
- `STOCKHELPER_STOOQ_DEBUG_HTTP=1` saves direct/cloudscraper Stooq response diagnostics under `data/debug/stooq_http/` (URL with API key redacted, status, headers, anti-bot detection flag/kind, preview, and response body excerpt). The console error also preserves the debug JSON path.

---

## 6) Data normalization

- Local and remote OHLC data is sanitized (column normalization, numeric/date coercion, invalid-row drop, date de-duplication) before chart/scanner usage.

## 7) Reliability / rollback

If final save fails at any stage (config update, chart snapshot write, data persistence), the workflow restores previous file snapshots to avoid partial writes.

---

## 8) Helpful examples

```bash
# Polish stock
python -m chart_program mbr

# Foreign stock
python -m chart_program algt.us

# Forex pair
python -m chart_program usdpln

# Force commodity mode by adding CFD suffix
python -m chart_program "algt.us cfd"
python -m chart_program algt.us cfd

# Explicit instrument override
python -m chart_program algt.us --instrument stock
python -m chart_program "algt.us cfd" --instrument commodity
```

---

## 9) Effect of FX fee toggle for foreign stocks

- **ON**: position sizing includes conversion fee on buy + sell-at-stop path, and analysis output shows % reduction in position size caused by conversion fees.
- **OFF**: analysis assumes you already hold instrument currency, so stock monetary outputs are displayed in instrument currency (e.g. USD) instead of PLN.
