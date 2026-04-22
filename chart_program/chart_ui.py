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
        self.df = dataframe.reset_index(drop=True)
        self.instrument_type = instrument_type
        self.values = preset_values or {}

    def _date_window(self, date_value, size: int = 5):
        dates = list(self.df["Date"])
        if not dates:
            return None, None
        if date_value in dates:
            idx = dates.index(date_value)
        else:
            idx = len(dates) - 1

        left = max(0, idx - size)
        right = min(len(dates) - 1, idx + size)
        return dates[left], dates[right]

    def _build_figure(self, current_values: dict, level_points: dict, objects: list[dict] | None = None):
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

        # Transparent wick-capture overlay for precise Y hover/click on candle shadows.
        overlay_x = []
        overlay_y = []
        for _, row in self.df.iterrows():
            overlay_x.extend([row["Date"], row["Date"], None])
            overlay_y.extend([row["Low"], row["High"], None])
        fig.add_trace(
            go.Scatter(
                x=overlay_x,
                y=overlay_y,
                mode="lines",
                line={"width": 14, "color": "rgba(255,255,255,0.01)"},
                name="cursor_capture",
                showlegend=False,
                hovertemplate="Price: %{y:.5f}<extra></extra>",
            )
        )

        level_colors = {
            "high": "#d946ef",
            "low": "#14b8a6",
            "entry": "#22c55e",
            "stop_loss": "#ef4444",
            "check_zr_value_fibo_or_elevation": "#f59e0b",
            "line_cross_value": "#3b82f6",
        }

        for field in SELECTION_SEQUENCE:
            point = (level_points or {}).get(field)
            if not point:
                continue
            price = point.get("price")
            date = point.get("date")
            x0, x1 = self._date_window(date)
            if x0 is None:
                continue
            fig.add_trace(
                go.Scatter(
                    x=[x0, x1],
                    y=[price, price],
                    mode="lines",
                    line={"color": level_colors.get(field, "gray"), "width": 3},
                    name=f"{LABELS[field]}: {price:.5f}",
                    hoverinfo="name",
                    showlegend=True,
                )
            )

        for obj in (objects or []):
            fig.add_trace(
                go.Scatter(
                    x=[obj.get("x0"), obj.get("x1")],
                    y=[obj.get("y0"), obj.get("y1")],
                    mode="lines+text",
                    line={"color": obj.get("color", LINE_COLORS["gold"]), "width": 2},
                    text=["", obj.get("label", "OBJECT")],
                    textposition="top center",
                    name=obj.get("label", "OBJECT"),
                    customdata=[obj.get("id"), obj.get("id")],
                    hovertemplate=f"{obj.get('label', 'OBJECT')}: %{{y:.5f}}<extra></extra>",
                    showlegend=True,
                )
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
            legend={"orientation": "h", "y": 1.02, "x": 0},
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

    @staticmethod
    def _input_style():
        return {"width": "100%", "color": "black", "background": "white"}

    def run(self):
        app = Dash(__name__)

        is_stock = self.instrument_type == "stock"
        is_commodity = self.instrument_type == "commodity"

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
                                html.Button("Reset all", id="reset-all", n_clicks=0),
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
                            figure=self._build_figure(self.values, {}, []),
                            style={"height": "82vh"},
                            config={
                                "scrollZoom": True,
                                "displaylogo": False,
                                "modeBarButtonsToRemove": ["autoScale2d", "pan2d", "lasso2d", "select2d", "zoom2d", "zoomIn2d", "zoomOut2d", "resetScale2d"],
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
                        dcc.Dropdown(id="position-type", options=[{"label": "LONG", "value": "long"}, {"label": "SHORT", "value": "short"}], value=self.values.get("position_type", "long"), disabled=is_stock),
                        html.Label("Capital", style={"marginTop": "8px", "display": "block"}),
                        dcc.Input(id="capital", type="number", value=self.values.get("capital", 255000), style=self._input_style()),
                        html.Label("Lot cost", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="lot-cost", type="number", value=self.values.get("lot_cost", 0), style=self._input_style(), disabled=is_stock),
                        html.Label("Pip value", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="pip-value", type="number", value=self.values.get("pip_value", 0), style=self._input_style(), disabled=is_stock),
                        html.Label("Spread", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="spread", type="number", value=self.values.get("spread", 0), style=self._input_style(), disabled=is_stock),
                        html.Label("Pip size", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if (is_stock or is_commodity) else 1}),
                        dcc.Input(id="pip-size", type="number", value=self.values.get("pip_size", 0.0001), style=self._input_style(), disabled=(is_stock or is_commodity)),
                        html.H4("Drawn objects", style={"marginTop": "14px"}),
                        dcc.Dropdown(id="object-picker", options=[], value=None, clearable=True),
                        html.Button("Delete selected object", id="delete-object", n_clicks=0, style={"marginTop": "8px", "width": "100%"}),
                        html.Button("Finish", id="finish-btn", n_clicks=0, style={"marginTop": "16px", "width": "100%", "padding": "10px", "background": "#2563eb", "color": "white", "border": "none", "borderRadius": "8px"}),
                        html.Div(id="result-box", style={"marginTop": "10px"}),
                    ],
                ),
                dcc.Store(id="levels-store", data=self.values),
                dcc.Store(id="level-points-store", data={}),
                dcc.Store(id="objects-store", data=[]),
                dcc.Store(id="active-field", data="entry"),
                dcc.Store(id="active-tool", data="level"),
                dcc.Store(id="line-anchor", data=None),
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
            Output("level-points-store", "data"),
            Output("objects-store", "data"),
            Output("line-anchor", "data"),
            Output("fib-anchor", "data"),
            Output("object-picker", "value"),
            Input("candle-chart", "clickData"),
            Input("reset-all", "n_clicks"),
            State("levels-store", "data"),
            State("level-points-store", "data"),
            State("objects-store", "data"),
            State("active-field", "data"),
            State("active-tool", "data"),
            State("line-color", "value"),
            State("line-anchor", "data"),
            State("fib-anchor", "data"),
            prevent_initial_call=True,
        )
        def apply_click(click_data, reset_clicks, levels_store, level_points, objects_store, active_field, active_tool, color, line_anchor, fib_anchor):
            levels_store = levels_store or {}
            level_points = level_points or {}
            objects_store = objects_store or []

            if ctx.triggered_id == "reset-all":
                self.values = {}
                return {}, {}, [], None, None, None

            point = (click_data or {}).get("points", [{}])[0]
            clicked_object_id = point.get("customdata")
            if clicked_object_id:
                return levels_store, level_points, objects_store, line_anchor, fib_anchor, clicked_object_id

            price = self._extract_price(point)
            date = point.get("x")
            if price is None:
                return levels_store, level_points, objects_store, line_anchor, fib_anchor, None

            if active_tool == "line":
                if line_anchor is None:
                    return levels_store, level_points, objects_store, {"x": date, "y": price}, fib_anchor, None
                objects_store.append(
                    {
                        "id": str(uuid4()),
                        "type": "line",
                        "label": "LINE",
                        "x0": line_anchor["x"],
                        "y0": line_anchor["y"],
                        "x1": date,
                        "y1": price,
                        "color": color or LINE_COLORS["gold"],
                    }
                )
                return levels_store, level_points, objects_store, None, fib_anchor, None

            if active_tool == "fib":
                if fib_anchor is None:
                    return levels_store, level_points, objects_store, line_anchor, {"x": date, "y": price}, None

                y_start = fib_anchor["y"]
                y_end = price
                x0 = fib_anchor["x"]
                x1 = date
                y_618 = y_start + (y_end - y_start) * 0.618

                fib_lines = [
                    ("FIB 100%", y_start),
                    ("FIB 61.8%", y_618),
                    ("FIB 0%", y_end),
                ]
                for label, y_val in fib_lines:
                    objects_store.append(
                        {
                            "id": str(uuid4()),
                            "type": "fib",
                            "label": label,
                            "x0": x0,
                            "x1": x1,
                            "y0": y_val,
                            "y1": y_val,
                            "price": y_val,
                            "color": color or LINE_COLORS["gold"],
                        }
                    )
                return levels_store, level_points, objects_store, line_anchor, None, None

            if active_field == "high":
                selected = self._extract_price({"high": point.get("high")})
            elif active_field == "low":
                selected = self._extract_price({"low": point.get("low")})
            else:
                selected = price

            if selected is not None:
                levels_store[active_field] = selected
                level_points[active_field] = {"price": selected, "date": date}

            self.values = levels_store
            return levels_store, level_points, objects_store, line_anchor, fib_anchor, None

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
            Input("level-points-store", "data"),
            Input("objects-store", "data"),
            Input("active-field", "data"),
            Input("active-tool", "data"),
        )
        def redraw(levels_store, level_points, objects_store, active_field, active_tool):
            levels_store = levels_store or {}
            level_points = level_points or {}
            objects_store = objects_store or []
            fig = self._build_figure(levels_store, level_points, objects_store)

            lines = [html.Div(f"Mode: {active_tool.upper()}")]
            if active_tool == "level":
                lines.append(html.Div(f"Active button: {LABELS.get(active_field, active_field)}"))
            for field in SELECTION_SEQUENCE:
                value = levels_store.get(field)
                lines.append(html.Div(f"{LABELS[field]}: {'-' if value is None else f'{value:.5f}'}"))

            obj_options = [{"label": f"{obj.get('label', 'OBJ')} ({obj.get('id')[:8]})", "value": obj.get("id")} for obj in objects_store]

            btn_styles = []
            for field in SELECTION_SEQUENCE:
                if active_tool == "level" and field == active_field:
                    btn_styles.append({"background": "#2563eb", "color": "white", "border": "1px solid #2563eb", "padding": "8px"})
                else:
                    btn_styles.append({"background": "#1f2937", "color": "#e5e7eb", "border": "1px solid #334155", "padding": "8px"})

            return fig, lines, obj_options, *btn_styles

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
                        "capital": capital or 255000,
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
        level_points = {}
        for field in SELECTION_SEQUENCE:
            value = levels.get(field) if isinstance(levels, dict) else None
            if isinstance(value, (int, float)):
                level_points[field] = {"price": value, "date": self.df["Date"].iloc[-1]}
        fig = self._build_figure(levels if isinstance(levels, dict) else {}, level_points, objects)
        fig.write_image(str(file_path), width=1800, height=1000)
