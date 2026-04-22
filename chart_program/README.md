# Chart Program (Standalone)

This is a separate, standalone tool for interactive level selection.

## Run

```bash
python -m chart_program.main jsw
```

or:

```bash
python chart_program/main.py coffee_long --instrument commodity --position-type long
```

It will:
1. Detect instrument type (or use `--instrument`).
2. Load/update daily candles from Stooq.
3. Open the interactive chart for level selection.
4. Save/update config in `configs/stocks|commodities|forex`.
5. Save chart image in `charts/<config_name>_levels.png`.
