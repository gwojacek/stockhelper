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
```

The quoted `"algt.us cfd"` form is supported and forces **commodity** behavior for that symbol.

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
- Adding `cfd` suffix (e.g. `"algt.us cfd"`) forces instrument type to commodity.

---

## 4) UI guide

- Left panel:
  - candlestick chart
  - level selection buttons: `HIGH`, `LOW`, `ENTRY`, `STOP LOSS`, `CHECK_ZR`, `LINE_CROSS`
  - drawing tools: `Line`, `Fib 61.8`, `Half→SL`
  - Ichimoku cloud toggle
- Right panel:
  - instrument type
  - `Name/Ticker` display
  - selected values
  - manual fields (`capital`, `lot_cost`, `pip_value`, `spread`)
  - drawn object management

### Drawing behavior

- You can pan/zoom with mouse and wheel.
- Line/Fib points are selected via chart clicks.
- Line and Fib tools now show a live preview after first anchor and before second click.
- The chart x-range is padded before/after available candles so lines can be drawn beyond the raw candle window.

---

## 5) Data source options

- `--data-source auto` (default)
  - stock/forex: Yahoo then Stooq fallback
  - commodity: Stooq then Yahoo fallback
- `--data-source yahoo`
- `--data-source stooq`

Optional:

- `--api-key <key>` for Stooq variants (`apikey`, `api_key` on `stooq.pl` and `stooq.com`).

---

## 6) Reliability / rollback

If final save fails at any stage (config update, chart snapshot write, data persistence), the workflow restores previous file snapshots to avoid partial writes.

---

## 7) Helpful examples

```bash
# Polish stock
python -m chart_program mbr

# Foreign stock
python -m chart_program algt.us

# Forex pair
python -m chart_program usdpln

# Force commodity mode by adding CFD suffix
python -m chart_program "algt.us cfd"

# Explicit instrument override
python -m chart_program algt.us --instrument stock
python -m chart_program "algt.us cfd" --instrument commodity
```
