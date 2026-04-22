from __future__ import annotations

from pathlib import Path
from uuid import uuid4

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

LINE_COLORS = {
    "gold": "#facc15",
    "blue": "#3b82f6",
    "red": "#ef4444",
}


class ChartLevelSelectorUI:
    def __init__(self, symbol: str, dataframe, instrument_type: str, preset_values: dict | None = None):
        self.symbol = symbol
        self.df = dataframe
        self.instrument_type = instrument_type
        self.values = preset_values or {}

    def _build_figure(self, current_values: dict, objects: list[dict] | None = None):
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

        level_colors = {
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
                    line_color=level_colors.get(key, "gray"),
                    annotation_text=f"{LABELS.get(key, key)}: {value:.5f}",
                    annotation_position="right",
                )

        for obj in (objects or []):
            y_val = obj.get("price")
            color = obj.get("color", LINE_COLORS["gold"])
            label = obj.get("label", "OBJ")
            fig.add_hline(y=y_val, line_width=2, line_color=color, annotation_text=f"{label}: {y_val:.5f}", annotation_position="left")

        fig.update_layout(
            title=f"{self.symbol} ({self.instrument_type}) - Daily (1Y)",
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
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
    def _extract_price(point: dict | None):
        if not point:
            return None
        for key in ("y", "close", "high", "low", "open"):
            value = point.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
        return None

    def run(self):
        app = Dash(__name__)

        button_row = html.Div(
            [html.Button(LABELS[field], id=f"btn-{field}", n_clicks=0, className="level-btn") for field in SELECTION_SEQUENCE],
            style={"display": "grid", "gridTemplateColumns": "repeat(3, minmax(0, 1fr))", "gap": "8px", "marginBottom": "10px"},
        )

        app.layout = html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 380px", "height": "100vh", "background": "#020617", "color": "#e5e7eb"},
            children=[
                html.Div(
                    style={"padding": "14px"},
                    children=[
                        html.H3(f"Interactive Level Selector: {self.symbol}", style={"margin": "0 0 10px 0"}),
                        button_row,
                        html.Div(
                            style={"display": "flex", "gap": "8px", "marginBottom": "10px"},
                            children=[
                                html.Button("Line tool", id="tool-line", n_clicks=0),
                                html.Button("Fib 61.8", id="tool-fib", n_clicks=0),
                                dcc.Dropdown(
                                    id="line-color",
                                    options=[
                                        {"label": "Golden yellow", "value": LINE_COLORS["gold"]},
                                        {"label": "Blue", "value": LINE_COLORS["blue"]},
                                        {"label": "Red", "value": LINE_COLORS["red"]},
                                    ],
                                    value=LINE_COLORS["gold"],
                                    clearable=False,
                                    style={"width": "220px", "color": "black"},
                                ),
                            ],
                        ),
                        dcc.Graph(
                            id="candle-chart",
                            figure=self._build_figure(self.values, []),
                            style={"height": "82vh"},
                            config={
                                "scrollZoom": True,
                                "displaylogo": False,
                                "modeBarButtonsToRemove": [
                                    "autoScale2d",
                                    "pan2d",
                                    "lasso2d",
                                    "select2d",
                                    "zoom2d",
                                    "zoomIn2d",
                                    "zoomOut2d",
                                    "resetScale2d",
                                ],
                            },
                        ),
                        html.Div(id="cursor-box", style={"marginTop": "8px", "fontFamily": "monospace"}),
                    ],
                ),
                html.Div(
                    style={"borderLeft": "1px solid #1f2937", "padding": "16px", "background": "#0b1220", "overflowY": "auto"},
                    children=[
                        html.H4(f"Instrument: {self.instrument_type.upper()}"),
                        html.Div(f"Symbol/Name: {self.symbol}", style={"marginBottom": "12px"}),
                        html.H4("Selected values", style={"marginTop": 0}),
                        html.Div(id="values-panel", style={"fontFamily": "monospace", "marginBottom": "14px"}),
                        html.H4("Manual inputs"),
                        html.Label("Position type"),
                        dcc.Dropdown(id="position-type", options=[{"label": "LONG", "value": "long"}, {"label": "SHORT", "value": "short"}], value=self.values.get("position_type", "long")),
                        html.Label("Capital", style={"marginTop": "8px", "display": "block"}),
                        dcc.Input(id="capital", type="number", value=self.values.get("capital", 0), style={"width": "100%"}),
                        html.Label("Lot cost", style={"marginTop": "8px", "display": "block"}),
                        dcc.Input(id="lot-cost", type="number", value=self.values.get("lot_cost", 0), style={"width": "100%"}),
                        html.Label("Pip value", style={"marginTop": "8px", "display": "block"}),
                        dcc.Input(id="pip-value", type="number", value=self.values.get("pip_value", 0), style={"width": "100%"}),
                        html.Label("Spread", style={"marginTop": "8px", "display": "block"}),
                        dcc.Input(id="spread", type="number", value=self.values.get("spread", 0), style={"width": "100%"}),
                        html.Label("Pip size", style={"marginTop": "8px", "display": "block"}),
                        dcc.Input(id="pip-size", type="number", value=self.values.get("pip_size", 0.0001), style={"width": "100%"}),
                        html.H4("Drawn objects", style={"marginTop": "14px"}),
                        dcc.Dropdown(id="object-picker", options=[], value=None, clearable=True),
                        html.Button("Delete selected object", id="delete-object", n_clicks=0, style={"marginTop": "8px", "width": "100%"}),
                        html.Button("Finish", id="finish-btn", n_clicks=0, style={"marginTop": "16px", "width": "100%", "padding": "10px", "background": "#2563eb", "color": "white", "border": "none", "borderRadius": "8px"}),
                        html.Div(id="result-box", style={"marginTop": "10px"}),
                    ],
                ),
                dcc.Store(id="levels-store", data=self.values),
                dcc.Store(id="objects-store", data=[]),
                dcc.Store(id="active-field", data="entry"),
                dcc.Store(id="active-tool", data="level"),
                dcc.Store(id="fib-anchor", data=None),
            ],
        )

        @app.callback(
            Output("active-field", "data"),
            Output("active-tool", "data"),
            [Input(f"btn-{field}", "n_clicks") for field in SELECTION_SEQUENCE] + [Input("tool-line", "n_clicks"), Input("tool-fib", "n_clicks")],
            State("active-field", "data"),
            State("active-tool", "data"),
            prevent_initial_call=True,
        )
        def choose_mode(*args):
            trigger = ctx.triggered_id
            current_field = args[-2]
            current_tool = args[-1]
            if not trigger:
                return current_field, current_tool
            if str(trigger).startswith("btn-"):
                return str(trigger).replace("btn-", ""), "level"
            if trigger == "tool-line":
                return current_field, "line"
            if trigger == "tool-fib":
                return current_field, "fib"
            return current_field, current_tool

        @app.callback(
            Output("levels-store", "data"),
            Output("objects-store", "data"),
            Output("fib-anchor", "data"),
            Input("candle-chart", "clickData"),
            State("levels-store", "data"),
            State("objects-store", "data"),
            State("active-field", "data"),
            State("active-tool", "data"),
            State("line-color", "value"),
            State("fib-anchor", "data"),
            prevent_initial_call=True,
        )
        def apply_click(click_data, levels_store, objects_store, active_field, active_tool, color, fib_anchor):
            levels_store = levels_store or {}
            objects_store = objects_store or []
            point = (click_data or {}).get("points", [{}])[0]
            price = self._extract_price(point)
            if price is None:
                return levels_store, objects_store, fib_anchor

            if active_tool == "line":
                objects_store.append({"id": str(uuid4()), "type": "line", "price": price, "color": color or LINE_COLORS["gold"], "label": "LINE"})
                return levels_store, objects_store, fib_anchor

            if active_tool == "fib":
                if fib_anchor is None:
                    return levels_store, objects_store, price
                fib_value = fib_anchor + (price - fib_anchor) * 0.618
                objects_store.append({"id": str(uuid4()), "type": "fib", "price": fib_value, "color": color or LINE_COLORS["gold"], "label": "FIB 61.8"})
                return levels_store, objects_store, None

            if active_field == "high":
                selected = self._extract_price({"high": point.get("high")})
            elif active_field == "low":
                selected = self._extract_price({"low": point.get("low")})
            else:
                selected = price

            if selected is not None:
                levels_store[active_field] = selected
            self.values = levels_store
            return levels_store, objects_store, fib_anchor

        @app.callback(
            Output("objects-store", "data", allow_duplicate=True),
            Input("delete-object", "n_clicks"),
            State("objects-store", "data"),
            State("object-picker", "value"),
            prevent_initial_call=True,
        )
        def delete_object(_, objects_store, selected_id):
            objects_store = objects_store or []
            if not selected_id:
                return objects_store
            return [obj for obj in objects_store if obj.get("id") != selected_id]

        @app.callback(
            Output("candle-chart", "figure"),
            Output("values-panel", "children"),
            Output("object-picker", "options"),
            [Output(f"btn-{field}", "style") for field in SELECTION_SEQUENCE],
            Input("levels-store", "data"),
            Input("objects-store", "data"),
            Input("active-field", "data"),
            Input("active-tool", "data"),
        )
        def redraw(levels_store, objects_store, active_field, active_tool):
            levels_store = levels_store or {}
            objects_store = objects_store or []
            fig = self._build_figure(levels_store, objects_store)

            lines = [html.Div(f"Mode: {active_tool.upper()}")]
            if active_tool == "level":
                lines.append(html.Div(f"Active button: {LABELS.get(active_field, active_field)}"))
            for field in SELECTION_SEQUENCE:
                value = levels_store.get(field)
                lines.append(html.Div(f"{LABELS[field]}: {'-' if value is None else f'{value:.5f}'}"))

            obj_options = [{"label": f"{obj.get('label', 'OBJ')} @ {obj.get('price', 0):.5f}", "value": obj.get("id")} for obj in objects_store]

            btn_styles = []
            for field in SELECTION_SEQUENCE:
                if active_tool == "level" and field == active_field:
                    btn_styles.append({"background": "#2563eb", "color": "white", "border": "1px solid #2563eb", "padding": "8px"})
                else:
                    btn_styles.append({"background": "#1f2937", "color": "#e5e7eb", "border": "1px solid #334155", "padding": "8px"})

            return (fig, lines, obj_options, *btn_styles)

        @app.callback(Output("cursor-box", "children"), Input("candle-chart", "hoverData"))
        def hover_info(hover_data):
            if hover_data and hover_data.get("points"):
                point = hover_data["points"][0]
                price = self._extract_price(point)
                date = point.get("x")
                if price is not None:
                    return f"Cursor Price: {price:.5f} | Date: {date}"
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
            State("objects-store", "data"),
            prevent_initial_call=True,
        )
        def finalize(n_clicks, levels_store, position_type, capital, lot_cost, pip_value, spread, pip_size, objects_store):
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
                        "drawn_objects": objects_store or [],
                    }
                )
                self.values = levels_store
                return "Values captured. Close window to continue saving."
            return ""

        app.run(debug=False)
        return self.values

    def save_chart_snapshot(self, levels: dict, file_path: Path):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        objects = levels.get("drawn_objects", []) if isinstance(levels, dict) else []
        fig = self._build_figure(levels, objects)
        fig.write_image(str(file_path), width=1800, height=1000)
