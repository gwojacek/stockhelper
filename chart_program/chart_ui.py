from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html

SELECTION_SEQUENCE = [
    "high",
    "low",
    "entry",
    "stop_loss",
    "check_zr_value_fibo_or_elevation",
    "line_cross_value",
]


class ChartLevelSelectorUI:
    def __init__(self, symbol: str, dataframe, instrument_type: str, preset_values: dict | None = None):
        self.symbol = symbol
        self.df = dataframe
        self.instrument_type = instrument_type
        self.values = preset_values or {}

    def _build_figure(self, current_values: dict, cursor_price: float | None = None, cursor_date: str | None = None):
        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=self.df["Date"],
                    open=self.df["Open"],
                    high=self.df["High"],
                    low=self.df["Low"],
                    close=self.df["Close"],
                    name="Daily",
                )
            ]
        )

        color_map = {
            "high": "purple",
            "low": "teal",
            "entry": "green",
            "stop_loss": "red",
            "check_zr_value_fibo_or_elevation": "orange",
            "line_cross_value": "blue",
        }

        for key, value in current_values.items():
            fig.add_hline(y=value, line_width=1.5, line_color=color_map.get(key, "gray"), annotation_text=f"{key}: {value:.5f}")

        fig.update_layout(
            title=f"{self.symbol} ({self.instrument_type}) - Daily",
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
            dragmode="pan",
            template="plotly_dark",
        )
        fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", showline=True)
        fig.update_yaxes(showspikes=True, spikemode="across", spikesnap="cursor", showline=True)

        subtitle = ""
        if cursor_price is not None:
            subtitle = f" | Cursor Price: {cursor_price:.5f}"
        if cursor_date:
            subtitle += f" | Date: {cursor_date}"
        fig.update_layout(title=f"{self.symbol} ({self.instrument_type}) - Daily{subtitle}")

        return fig

    @staticmethod
    def _extract_float(click_data: dict, key: str, fallback=None):
        try:
            return float(click_data["points"][0][key])
        except (KeyError, TypeError, ValueError, IndexError):
            return fallback

    def run(self):
        app = Dash(__name__)
        initial_next_idx = 0
        for i, field in enumerate(SELECTION_SEQUENCE):
            if field in self.values:
                initial_next_idx = i + 1

        app.layout = html.Div(
            [
                html.H3(f"Guided level selection for {self.symbol}"),
                html.P("Click candles in order: HIGH, LOW, ENTRY, STOP LOSS, CHECK_ZR, LINE_CROSS."),
                dcc.Graph(id="candle-chart", figure=self._build_figure(self.values), style={"height": "85vh"}),
                html.Div(id="next-step", style={"marginTop": "8px"}),
                html.Div(id="cursor-box", style={"marginTop": "6px"}),
                dcc.Store(id="levels-store", data=self.values),
                dcc.Store(id="step-index", data=initial_next_idx),
                html.Button("Finish", id="finish-btn", n_clicks=0),
                html.Div(id="result-box", style={"marginTop": "10px"}),
            ]
        )

        @app.callback(
            Output("candle-chart", "figure"),
            Output("levels-store", "data"),
            Output("step-index", "data"),
            Output("next-step", "children"),
            Output("cursor-box", "children"),
            Input("candle-chart", "clickData"),
            Input("candle-chart", "hoverData"),
            State("levels-store", "data"),
            State("step-index", "data"),
            prevent_initial_call=False,
        )
        def select_level(click_data, hover_data, levels_store, step_index):
            levels_store = levels_store or {}
            step_index = step_index or 0

            cursor_price = self._extract_float(hover_data, "y")
            cursor_date = None
            if hover_data and "points" in hover_data and hover_data["points"]:
                cursor_date = hover_data["points"][0].get("x")

            if click_data and step_index < len(SELECTION_SEQUENCE):
                field = SELECTION_SEQUENCE[step_index]
                if field == "high":
                    selected = self._extract_float(click_data, "high")
                elif field == "low":
                    selected = self._extract_float(click_data, "low")
                else:
                    selected = self._extract_float(click_data, "y")

                if selected is not None:
                    levels_store[field] = selected
                    step_index += 1

            next_field = "Selection complete" if step_index >= len(SELECTION_SEQUENCE) else f"Next: {SELECTION_SEQUENCE[step_index]}"
            cursor_msg = (
                f"Cursor Price: {cursor_price:.5f} | Date: {cursor_date}"
                if cursor_price is not None
                else "Cursor Price: n/a"
            )
            self.values = levels_store
            fig = self._build_figure(levels_store, cursor_price=cursor_price, cursor_date=cursor_date)
            return fig, levels_store, step_index, next_field, cursor_msg

        @app.callback(
            Output("result-box", "children"),
            Input("finish-btn", "n_clicks"),
            State("levels-store", "data"),
            prevent_initial_call=True,
        )
        def finalize(n_clicks, levels_store):
            if n_clicks > 0:
                return f"Finalized levels: {levels_store}"
            return ""

        app.run(debug=False)
        return self.values

    def save_chart_snapshot(self, levels: dict, file_path: Path):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        fig = self._build_figure(levels)
        fig.write_image(str(file_path), width=1800, height=1000)
