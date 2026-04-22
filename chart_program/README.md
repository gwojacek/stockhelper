# Chart Program (Standalone)

This is a separate, standalone tool for interactive level selection.

## Run

```bash
python -m chart_program.main jsw
```

or:

```bash
python chart_program/main.py coffee_long --instrument commodity --position-type long --api-key YOUR_KEY
```

It will:
1. Detect instrument type (or use `--instrument`).
2. Load/update daily candles from Stooq.
3. Open the interactive chart for level selection.
4. Save/update config in `configs/stocks|commodities|forex`.
5. Save chart image in `charts/<config_name>_levels.png`.


## Failure behavior

If any error happens after chart selection starts (config write, chart export, or data save), the tool rolls back file changes and leaves existing files untouched (all-or-nothing writes).


## API key note

Stooq CSV endpoint typically works without an API key. If your environment/provider requires one, pass it with `--api-key` and the tool will try both `apikey` and `api_key` query variants on `stooq.pl` and `stooq.com`.
