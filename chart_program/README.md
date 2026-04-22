# Chart Program (Standalone)

This is a separate, standalone tool for interactive level selection.

## Run

```bash
python -m chart_program.main jsw --data-source yahoo
```

## UI highlights

- Modern dark layout with chart area + right sidebar.
- Level buttons: `HIGH`, `LOW`, `ENTRY`, `STOP LOSS`, `CHECK_ZR`, `LINE_CROSS`.
- Click a button, then click chart to set/update that value (reselection supported).
- Right sidebar shows selected values and manual-edit inputs (`position_type`, `capital`, `lot_cost`, `pip_value`, `spread`, `pip_size`).
- Cursor box shows current hover price/date.
- Mouse wheel zoom is enabled and zoom state is preserved (no auto reset).
- Mode bar removes autoscale, pan, and lasso tools.

## Data window

Only the latest ~1 year of daily candles is used and saved.

## Data source options

- `--data-source auto` (default): try Yahoo Finance first, then Stooq.
- `--data-source yahoo`: use only Yahoo Finance.
- `--data-source stooq`: use only Stooq.

## Failure behavior

If any error happens after chart selection starts (config write, chart export, or data save), the tool rolls back file changes and leaves existing files untouched (all-or-nothing writes).

## API key note

Stooq CSV endpoint typically works without an API key. If your environment/provider requires one, pass it with `--api-key` and the tool will try both `apikey` and `api_key` query variants on `stooq.pl` and `stooq.com`.


## Drawing tools

- **Line tool**: click `Line tool`, click chart to create a colored horizontal line object.
- **Fib 61.8 tool**: click `Fib 61.8`, click first anchor, then second anchor; tool creates `FIB 61.8` object.
- All drawn objects can be removed from sidebar (`Delete selected object`).
