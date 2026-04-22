# Chart Program (Standalone)

This is a separate, standalone tool for interactive level selection.

## Run

```bash
python -m chart_program.main jsw --data-source yahoo
```

## UI highlights

- Modern dark layout with chart area + right sidebar.
- Level buttons: `HIGH`, `LOW`, `ENTRY`, `STOP LOSS`, `CHECK_ZR`, `LINE_CROSS`.
- Active selected level button is highlighted in blue.
- Click a level button, then click chart to set/update that value.
- For clicked levels, the chart shows **short local segments** (not full-width lines).
- Right sidebar shows selected values and labeled manual inputs.
- Inputs not used by the detected instrument are disabled/greyed-out.
- Instrument type and symbol/name are displayed in sidebar.
- Capital defaults to `255000`.

## Navigation and zoom

- Drag on chart to pan (grab/move behavior).
- Mouse wheel zoom enabled.
- Mode bar removes autoscale, pan, lasso, and extra zoom/reset buttons.

## Drawing tools

- **Line tool**: click first point, then second point to create a segment line object.
- **Fib 61.8 tool**: click first anchor, then second anchor to place 3 fib objects: `100%`, `61.8%`, `0%`.
- Color options: Golden yellow (default), Blue, Red.
- Click a drawn object on chart to select it, then delete via sidebar.
- `Reset all` clears all selected levels and drawn objects.

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
