from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html

SELECTION_SEQUENCE = [
    "high",
    "low",
    "entry",
    "stop_loss",
    "check_zr_value_fibo_or_elevation",
    "line_cross_value",
]

LABELS = {
    "high": "HIGH",
    "low": "LOW",
    "entry": "ENTRY",
    "stop_loss": "STOP LOSS",
    "check_zr_value_fibo_or_elevation": "CHECK_ZR",
    "line_cross_value": "LINE_CROSS",
}


class ChartLevelSelectorUI:
    def __init__(self, symbol: str, dataframe, instrument_type: str, preset_values: dict | None = None):
        self.symbol = symbol
        self.df = dataframe
        self.instrument_type = instrument_type
        self.values = preset_values or {}

    def _build_figure(self, current_values: dict):
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
            "high": "#d946ef",
            "low": "#14b8a6",
            "entry": "#22c55e",
            "stop_loss": "#ef4444",
            "check_zr_value_fibo_or_elevation": "#f59e0b",
            "line_cross_value": "#3b82f6",
        }

        for key, value in current_values.items():
            if isinstance(value, (int, float)):
                fig.add_hline(
                    y=value,
                    line_width=2,
                    line_color=color_map.get(key, "gray"),
                    annotation_text=f"{LABELS.get(key, key)}: {value:.5f}",
                    annotation_position="right",
                )

        fig.update_layout(
            title=f"{self.symbol} ({self.instrument_type}) - Daily (1Y)",
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
            dragmode="pan",
            template="plotly_dark",
            uirevision="keep_zoom",
            margin={"l": 24, "r": 24, "t": 45, "b": 20},
            paper_bgcolor="#0b1220",
            plot_bgcolor="#111827",
        )
        fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", showline=True)
        fig.update_yaxes(showspikes=True, spikemode="across", spikesnap="cursor", showline=True)
        return fig

    @staticmethod
    def _extract_float(click_data: dict, key: str, fallback=None):
        try:
            return float(click_data["points"][0][key])
        except (KeyError, TypeError, ValueError, IndexError):
            return fallback

    def run(self):
        app = Dash(__name__)

        button_row = html.Div(
            [
                html.Button(LABELS[field], id=f"btn-{field}", n_clicks=0, className="level-btn")
                for field in SELECTION_SEQUENCE
            ],
            style={"display": "grid", "gridTemplateColumns": "repeat(3, minmax(0, 1fr))", "gap": "8px", "marginBottom": "12px"},
        )

        app.layout = html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 360px", "height": "100vh", "background": "#020617", "color": "#e5e7eb"},
            children=[
                html.Div(
                    style={"padding": "14px"},
                    children=[
                        html.H3(f"Interactive Level Selector: {self.symbol}", style={"margin": "0 0 12px 0"}),
                        button_row,
                        dcc.Graph(id="candle-chart", figure=self._build_figure(self.values), style={"height": "85vh"}),
                        html.Div(id="cursor-box", style={"marginTop": "8px", "fontFamily": "monospace"}),
                    ],
                ),
                html.Div(
                    style={"borderLeft": "1px solid #1f2937", "padding": "16px", "background": "#0b1220", "overflowY": "auto"},
                    children=[
                        html.H4("Selected values", style={"marginTop": 0}),
                        html.Div(id="values-panel", style={"fontFamily": "monospace", "marginBottom": "14px"}),
                        html.H4("Manual inputs"),
                        dcc.Dropdown(id="position-type", options=[{"label": "LONG", "value": "long"}, {"label": "SHORT", "value": "short"}], value=self.values.get("position_type", "long")),
                        dcc.Input(id="capital", type="number", placeholder="Capital", value=self.values.get("capital", 0), style={"width": "100%", "marginTop": "8px"}),
                        dcc.Input(id="lot-cost", type="number", placeholder="Lot cost", value=self.values.get("lot_cost", 0), style={"width": "100%", "marginTop": "8px"}),
                        dcc.Input(id="pip-value", type="number", placeholder="Pip value", value=self.values.get("pip_value", 0), style={"width": "100%", "marginTop": "8px"}),
                        dcc.Input(id="spread", type="number", placeholder="Spread", value=self.values.get("spread", 0), style={"width": "100%", "marginTop": "8px"}),
                        dcc.Input(id="pip-size", type="number", placeholder="Pip size", value=self.values.get("pip_size", 0.0001), style={"width": "100%", "marginTop": "8px"}),
                        html.Button("Finish", id="finish-btn", n_clicks=0, style={"marginTop": "16px", "width": "100%", "padding": "10px", "background": "#2563eb", "color": "white", "border": "none", "borderRadius": "8px"}),
                        html.Div(id="result-box", style={"marginTop": "10px"}),
                    ],
                ),
                dcc.Store(id="levels-store", data=self.values),
                dcc.Store(id="active-field", data="entry"),
            ],
        )

        @app.callback(
            Output("active-field", "data"),
            [Input(f"btn-{field}", "n_clicks") for field in SELECTION_SEQUENCE],
            State("active-field", "data"),
            prevent_initial_call=True,
        )
        def choose_active(*args):
            trigger = ctx.triggered_id
            if not trigger:
                return args[-1]
            return trigger.replace("btn-", "")

        @app.callback(
            Output("levels-store", "data"),
            Input("candle-chart", "clickData"),
            State("levels-store", "data"),
            State("active-field", "data"),
            prevent_initial_call=True,
        )
        def apply_click(click_data, levels_store, active_field):
            levels_store = levels_store or {}
            if not click_data or not active_field:
                return levels_store

            if active_field == "high":
                selected = self._extract_float(click_data, "high")
            elif active_field == "low":
                selected = self._extract_float(click_data, "low")
            else:
                selected = self._extract_float(click_data, "y")

            if selected is not None:
                levels_store[active_field] = selected
            self.values = levels_store
            return levels_store

        @app.callback(
            Output("candle-chart", "figure"),
            Output("values-panel", "children"),
            Input("levels-store", "data"),
            State("active-field", "data"),
        )
        def redraw(levels_store, active_field):
            levels_store = levels_store or {}
            fig = self._build_figure(levels_store)
            lines = [html.Div(f"Active: {LABELS.get(active_field, active_field)}")]
            for field in SELECTION_SEQUENCE:
                value = levels_store.get(field)
                text = "-" if value is None else f"{value:.5f}"
                lines.append(html.Div(f"{LABELS[field]}: {text}"))
            return fig, lines

        @app.callback(
            Output("cursor-box", "children"),
            Input("candle-chart", "hoverData"),
        )
        def hover_info(hover_data):
            if hover_data and hover_data.get("points"):
                point = hover_data["points"][0]
                y = point.get("y")
                x = point.get("x")
                return f"Cursor Price: {y} | Date: {x}"
            return "Cursor Price: n/a"

        @app.callback(
            Output("result-box", "children"),
            Input("finish-btn", "n_clicks"),
            State("levels-store", "data"),
            State("position-type", "value"),
            State("capital", "value"),
            State("lot-cost", "value"),
            State("pip-value", "value"),
            State("spread", "value"),
            State("pip-size", "value"),
            prevent_initial_call=True,
        )
        def finalize(n_clicks, levels_store, position_type, capital, lot_cost, pip_value, spread, pip_size):
            if n_clicks > 0:
                levels_store = levels_store or {}
                levels_store.update(
                    {
                        "position_type": position_type,
                        "capital": capital or 0,
                        "lot_cost": lot_cost or 0,
                        "pip_value": pip_value or 0,
                        "spread": spread or 0,
                        "pip_size": pip_size or 0.0001,
                    }
                )
                self.values = levels_store
                return "Values captured. Close window to continue saving."
            return ""

        app.run(debug=False)
        return self.values

    def save_chart_snapshot(self, levels: dict, file_path: Path):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        fig = self._build_figure(levels)
        fig.write_image(str(file_path), width=1800, height=1000)
