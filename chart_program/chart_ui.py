from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import threading
import time
import webbrowser
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dcc, html
from flask import request
from werkzeug.serving import WSGIRequestHandler, make_server

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
    "purple": "#a855f7",
    "green": "#22c55e",
}


class ChartLevelSelectorUI:
    def __init__(
        self,
        symbol: str,
        dataframe,
        instrument_type: str,
        preset_values: dict | None = None,
        source_ticker: str | None = None,
        source_name: str | None = None,
    ):
        self.symbol = symbol
        self.df = dataframe.dropna(subset=["Open", "High", "Low", "Close"]).sort_values("Date").reset_index(drop=True)
        self.instrument_type = instrument_type
        self.values = preset_values or {}
        self._finished = False
        self.source_ticker = source_ticker
        self.source_name = source_name

    def _resolve_candle_index(self, date_value):
        if self.df.empty:
            return None
        target = pd.to_datetime(date_value, errors="coerce")
        if pd.isna(target):
            return len(self.df) - 1
        all_dates = pd.to_datetime(self.df["Date"], errors="coerce")
        deltas = (all_dates - target).abs()
        idx = int(deltas.idxmin())
        return idx

    def _monthly_ticks(self):
        dates = pd.to_datetime(self.df["Date"], errors="coerce")
        tickvals = []
        ticktext = []
        prev = None
        for i, d in enumerate(dates):
            label_key = d.strftime("%Y-%m")
            if label_key != prev:
                tickvals.append(self.df["Date"].iloc[i])
                ticktext.append(d.strftime("%Y") if d.month == 1 else d.strftime("%b"))
                prev = label_key
        return tickvals, ticktext

    def _date_window(self, date_value, size: int = 5):
        dates = list(self.df["Date"])
        idx = self._resolve_candle_index(date_value)
        if idx is None:
            return None, None
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
                    hoverinfo="skip",
                    hovertemplate=None,
                )
            ]
        )

        # Transparent heatmap overlay for precise XY cursor price picking.
        y_min = float(self.df["Low"].min())
        y_max = float(self.df["High"].max())
        y_pad = (y_max - y_min) * 0.05 if y_max > y_min else 1.0
        y_grid = np.linspace(y_min - y_pad, y_max + y_pad, 1200)
        x_grid = list(self.df["Date"])
        z = np.zeros((len(y_grid), len(x_grid)))
        fig.add_trace(
            go.Heatmap(
                x=x_grid,
                y=y_grid,
                z=z,
                showscale=False,
                opacity=0.001,
                hoverinfo="none",
                hovertemplate=None,
                name="cursor_capture",
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
            price = point.get("plot_price", point.get("price"))
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
                    name=f"{LABELS[field]}: {price:.2f}",
                    hoverinfo="name",
                    showlegend=True,
                )
            )
            if field == "entry" and date is not None:
                fig.add_trace(
                    go.Scatter(
                        x=[date],
                        y=[price],
                        mode="markers",
                        marker={
                            "size": 9,
                            "symbol": "square",
                            "color": level_colors.get(field, "#22c55e"),
                            "line": {"width": 1, "color": "#e5e7eb"},
                        },
                        name="ENTRY point",
                        hovertemplate="ENTRY click: %{y:.2f}<extra></extra>",
                        showlegend=True,
                    )
                )

        for obj in (objects or []):
            obj_type = obj.get("type")
            is_fib_618 = obj_type == "fib" and "61.8%" in str(obj.get("label", ""))
            line_width = 2.0 if is_fib_618 else (1.6 if obj_type == "fib" else 1.2)
            line_color = "#ffffff" if is_fib_618 else obj.get("color", LINE_COLORS["gold"])
            mode = "lines+text+markers" if is_fib_618 else "lines+text"
            fig.add_trace(
                go.Scatter(
                    x=[obj.get("x0"), obj.get("x1")],
                    y=[obj.get("y0"), obj.get("y1")],
                    mode=mode,
                    line={"color": line_color, "width": line_width},
                    marker={"size": 5, "color": line_color} if is_fib_618 else None,
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
            hovermode="closest",
            dragmode="pan",
            template="plotly_dark",
            uirevision="keep_zoom",
            margin={"l": 24, "r": 24, "t": 45, "b": 45},
            paper_bgcolor="#0b1220",
            plot_bgcolor="#111827",
            legend={"orientation": "h", "y": 1.02, "x": 0},
        )
        tickvals, ticktext = self._monthly_ticks()
        x_max = pd.to_datetime(self.df["Date"].max(), errors="coerce")
        for obj in (objects or []):
            x1 = pd.to_datetime(obj.get("x1"), errors="coerce")
            if not pd.isna(x1) and (pd.isna(x_max) or x1 > x_max):
                x_max = x1
        fig.update_xaxes(
            showspikes=True,
            spikemode="toaxis+across",
            spikesnap="cursor",
            spikedash="dash",
            spikethickness=1,
            showline=True,
            type="date",
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            tickangle=0,
            ticklabelposition="outside",
            range=[self.df["Date"].min(), x_max if not pd.isna(x_max) else self.df["Date"].max()],
            rangebreaks=[dict(bounds=["sat", "mon"])],
        )
        fig.update_yaxes(
            showspikes=True,
            spikemode="across+marker",
            spikesnap="cursor",
            spikedash="dash",
            spikethickness=1,
            showline=True,
            side="right",
        )
        y_min = pd.to_numeric(self.df["Low"], errors="coerce").min()
        y_max = pd.to_numeric(self.df["High"], errors="coerce").max()
        for obj in (objects or []):
            for key in ("y0", "y1"):
                y_val = pd.to_numeric(pd.Series([obj.get(key)]), errors="coerce").iloc[0]
                if not pd.isna(y_val):
                    y_min = y_val if pd.isna(y_min) else min(y_min, y_val)
                    y_max = y_val if pd.isna(y_max) else max(y_max, y_val)
        if not pd.isna(y_min) and not pd.isna(y_max):
            pad = (y_max - y_min) * 0.05 if y_max > y_min else 0.5
            fig.update_yaxes(range=[y_min - pad, y_max + pad])
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
        server_holder: dict[str, object] = {}
        heartbeat = {"ts": time.time()}
        initial_level_points = self.values.get("level_points", {}) if isinstance(self.values, dict) else {}
        initial_objects = self.values.get("drawn_objects", []) if isinstance(self.values, dict) else []

        class QuietRequestHandler(WSGIRequestHandler):
            def log(self, type, message, *args):  # noqa: A003
                return

        @app.server.route("/shutdown", methods=["GET", "POST"])
        def _shutdown_app():
            shutdown = request.environ.get("werkzeug.server.shutdown")
            if shutdown:
                shutdown()
            elif server_holder.get("server") is not None:
                threading.Timer(0.1, lambda: server_holder["server"].shutdown()).start()
            return "ok"

        @app.server.route("/heartbeat", methods=["POST"])
        def _heartbeat():
            heartbeat["ts"] = time.time()
            return "ok"

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
                                html.Button("Half→SL", id="tool-half", n_clicks=0),
                                html.Button("Reset all", id="reset-all", n_clicks=0, style={"marginLeft": "auto"}),
                                html.Div(
                                    style={"display": "flex", "gap": "6px", "alignItems": "center"},
                                    children=[
                                        html.Div("Line color:"),
                                        html.Button("", id="color-gold", n_clicks=0, style={"width": "22px", "height": "22px", "background": LINE_COLORS["gold"], "border": "1px solid white"}),
                                        html.Button("", id="color-purple", n_clicks=0, style={"width": "22px", "height": "22px", "background": LINE_COLORS["purple"], "border": "1px solid white"}),
                                        html.Button("", id="color-green", n_clicks=0, style={"width": "22px", "height": "22px", "background": LINE_COLORS["green"], "border": "1px solid white"}),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(id="cursor-box", style={"marginBottom": "8px", "fontFamily": "monospace", "fontSize": "16px", "fontWeight": "600", "textAlign": "center"}),
                        dcc.Graph(
                            id="candle-chart",
                            figure=self._build_figure(self.values, initial_level_points, initial_objects),
                            style={"height": "82vh"},
                            config={
                                "scrollZoom": True,
                                "displaylogo": False,
                                "modeBarButtonsToRemove": ["autoScale2d", "pan2d", "lasso2d", "select2d", "zoom2d", "zoomIn2d", "zoomOut2d", "resetScale2d"],
                            },
                        ),
                    ],
                ),
                html.Div(
                    style={"borderLeft": "1px solid #1f2937", "padding": "16px", "background": "#0b1220", "overflowY": "auto"},
                    children=[
                        html.H4(f"Instrument: {self.instrument_type.upper()}"),
                        html.Div(
                            f"Symbol/Name: {self.source_name or self.symbol}"
                            + (f" ({self.source_ticker})" if self.source_ticker else ""),
                            style={"marginBottom": "12px"},
                        ),
                        html.H4("Selected values", style={"marginTop": 0}),
                        html.Div(id="values-panel", style={"fontFamily": "monospace", "marginBottom": "14px"}),
                        html.H4("Manual inputs"),
                        html.Label("Position type"),
                        dcc.Dropdown(
                            id="position-type",
                            options=[{"label": "LONG", "value": "long"}, {"label": "SHORT", "value": "short"}],
                            value=self.values.get("position_type", "long"),
                            disabled=is_stock,
                            style={"color": "black", "background": "white"},
                        ),
                        html.Label("Capital", style={"marginTop": "8px", "display": "block"}),
                        dcc.Input(id="capital", type="number", value=self.values.get("capital") or 255000, style=self._input_style()),
                        html.Label("Lot cost", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="lot-cost", type="number", value=self.values.get("lot_cost") if self.values.get("lot_cost") not in (0, None) else None, style=self._input_style(), disabled=is_stock),
                        html.Label("Pip value", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="pip-value", type="number", value=self.values.get("pip_value") if self.values.get("pip_value") not in (0, None) else None, style=self._input_style(), disabled=is_stock),
                        html.Label("Spread multiplier (spread = Multiplier * pip_value)", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="spread-mult", type="number", value=self.values.get("spread_multiplier") if self.values.get("spread_multiplier") not in (0, None) else None, placeholder="e.g. 9", style=self._input_style(), disabled=is_stock),
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
                dcc.Store(id="level-points-store", data=initial_level_points),
                dcc.Store(id="objects-store", data=initial_objects),
                dcc.Store(id="active-field", data="entry"),
                dcc.Store(id="active-tool", data="level"),
                dcc.Store(id="line-anchor", data=None),
                dcc.Store(id="fib-anchor", data=None),
                dcc.Store(id="half-anchor", data=None),
                dcc.Store(id="line-color-store", data=LINE_COLORS["gold"]),
                dcc.Store(id="finished-store", data=False),
                dcc.Store(id="close-tab-signal", data=0),
                dcc.Store(id="heartbeat-store", data=0),
                dcc.Interval(id="heartbeat-interval", interval=1000, n_intervals=0),
                html.Script("window.addEventListener('beforeunload', () => {navigator.sendBeacon('/shutdown');});window.addEventListener('pagehide', () => {navigator.sendBeacon('/shutdown');});window.addEventListener('unload', () => {navigator.sendBeacon('/shutdown');});"),
            ],
        )


        @app.callback(
            Output("line-color-store", "data"),
            Input("color-gold", "n_clicks"),
            Input("color-purple", "n_clicks"),
            Input("color-green", "n_clicks"),
            State("line-color-store", "data"),
            prevent_initial_call=True,
        )
        def choose_color(_, __, ___, current):
            trig = ctx.triggered_id
            if trig == "color-gold":
                return LINE_COLORS["gold"]
            if trig == "color-purple":
                return LINE_COLORS["purple"]
            if trig == "color-green":
                return LINE_COLORS["green"]
            return current

        @app.callback(
            Output("active-field", "data"),
            Output("active-tool", "data"),
            [Input(f"btn-{field}", "n_clicks") for field in SELECTION_SEQUENCE] + [Input("tool-line", "n_clicks"), Input("tool-fib", "n_clicks"), Input("tool-half", "n_clicks")],
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
            if trigger == "tool-half":
                return "stop_loss", "half"
            return current_field, current_tool

        @app.callback(
            Output("levels-store", "data"),
            Output("level-points-store", "data"),
            Output("objects-store", "data"),
            Output("line-anchor", "data"),
            Output("fib-anchor", "data"),
            Output("half-anchor", "data"),
            Output("object-picker", "value"),
            Input("candle-chart", "clickData"),
            Input("reset-all", "n_clicks"),
            State("levels-store", "data"),
            State("level-points-store", "data"),
            State("objects-store", "data"),
            State("active-field", "data"),
            State("active-tool", "data"),
            State("line-color-store", "data"),
            State("line-anchor", "data"),
            State("fib-anchor", "data"),
            State("half-anchor", "data"),
            prevent_initial_call=True,
        )
        def apply_click(click_data, reset_clicks, levels_store, level_points, objects_store, active_field, active_tool, color, line_anchor, fib_anchor, half_anchor):
            levels_store = levels_store or {}
            level_points = level_points or {}
            objects_store = objects_store or []

            if ctx.triggered_id == "reset-all":
                self.values = {}
                return {}, {}, [], None, None, None, None

            point = (click_data or {}).get("points", [{}])[0]
            clicked_object_id = point.get("customdata")
            if clicked_object_id and active_tool != "level":
                return levels_store, level_points, objects_store, line_anchor, fib_anchor, half_anchor, clicked_object_id

            price = self._extract_price(point)
            date = point.get("x")
            if price is None:
                return levels_store, level_points, objects_store, line_anchor, fib_anchor, half_anchor, None

            if active_tool == "line":
                if line_anchor is None:
                    return levels_store, level_points, objects_store, {"x": date, "y": round(price, 2)}, fib_anchor, half_anchor, None
                objects_store.append(
                    {
                        "id": str(uuid4()),
                        "type": "line",
                        "label": "LINE",
                        "x0": line_anchor["x"],
                        "y0": line_anchor["y"],
                        "x1": date,
                        "y1": round(price, 2),
                        "color": color or LINE_COLORS["gold"],
                    }
                )
                return levels_store, level_points, objects_store, None, fib_anchor, half_anchor, None

            if active_tool == "fib":
                if fib_anchor is None:
                    return levels_store, level_points, objects_store, line_anchor, {"x": date, "y": round(price, 2)}, half_anchor, None

                y_start = round(fib_anchor["y"], 2)
                y_end = round(price, 2)
                x_start = pd.to_datetime(fib_anchor["x"], errors="coerce")
                x_end = pd.to_datetime(date, errors="coerce")
                x_right = pd.to_datetime(self.df.iloc[-1]["Date"], errors="coerce")
                if pd.isna(x_start) or pd.isna(x_end) or x_start == x_end:
                    x_start = pd.to_datetime(self.df.iloc[0]["Date"], errors="coerce")
                    x_end = pd.to_datetime(self.df.iloc[-1]["Date"], errors="coerce")

                delta = y_end - y_start
                retrace_levels = [0.0, 0.618, 1.0]
                last_date = pd.to_datetime(self.df.iloc[-1]["Date"], errors="coerce")
                x_right = last_date if not pd.isna(last_date) else x_end
                x_common_end = x_right + abs(x_end - x_start) * 3

                for r in retrace_levels:
                    pct = f"{r * 100:.1f}%".replace(".0%", "%")
                    y_val = round(y_end - delta * r, 2)
                    base_label = f"FIB {pct}"
                    label = f"{base_label} ({y_val:.2f})"
                    x_level_start = x_start + (x_end - x_start) * (1 - r)
                    objects_store.append(
                        {
                            "id": str(uuid4()),
                            "type": "fib",
                            "label": label,
                            "x0": x_level_start,
                            "x1": x_common_end,
                            "y0": y_val,
                            "y1": y_val,
                            "price": y_val,
                            "color": color or LINE_COLORS["gold"],
                        }
                    )
                return levels_store, level_points, objects_store, line_anchor, None, half_anchor, None

            if active_tool == "half":
                current_price = round(price, 2)
                if half_anchor is None:
                    return levels_store, level_points, objects_store, line_anchor, fib_anchor, {"x": date, "y": current_price}, None
                midpoint = round((half_anchor["y"] + current_price) / 2.0, 2)
                idx = self._resolve_candle_index(date)
                resolved_date = self.df.iloc[idx]["Date"] if idx is not None else date
                levels_store["stop_loss"] = midpoint
                level_points["stop_loss"] = {"price": midpoint, "plot_price": midpoint, "date": resolved_date}
                self.values = levels_store
                return levels_store, level_points, objects_store, line_anchor, fib_anchor, None, None

            if active_field in ("high", "low"):
                idx = self._resolve_candle_index(date)
                if idx is not None:
                    row = self.df.iloc[idx]
                    selected = round(float(row["High"]), 2) if active_field == "high" else round(float(row["Low"]), 2)
                    resolved_date = self.df.iloc[idx]["Date"]
                    offset = max((float(row["High"]) - float(row["Low"])) * 0.03, 0.01)
                    plot_price = selected + offset if active_field == "high" else selected - offset
                else:
                    selected = None
                    resolved_date = date
                    plot_price = None
            else:
                selected = round(price, 2)
                idx = self._resolve_candle_index(date)
                resolved_date = self.df.iloc[idx]["Date"] if idx is not None else date
                plot_price = selected

            if selected is not None:
                levels_store[active_field] = selected
                level_points[active_field] = {"price": selected, "plot_price": round(plot_price, 2), "date": resolved_date}

            self.values = dict(levels_store)
            self.values["drawn_objects"] = objects_store
            self.values["level_points"] = level_points
            return levels_store, level_points, objects_store, line_anchor, fib_anchor, half_anchor, None

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
                lines.append(html.Div(f"{LABELS[field]}: {'-' if value is None else f'{value:.2f}'}"))

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
            cursor_price = None
            if hover_data and hover_data.get("points"):
                point = hover_data["points"][0]
                price = self._extract_price(point)
                cursor_price = price
                date = point.get("x")
                idx = self._resolve_candle_index(date)
                if idx is not None:
                    row = self.df.iloc[idx]
                    d = pd.to_datetime(row["Date"], errors="coerce")
                    if price is not None:
                        d_txt = d.strftime("%Y-%m-%d") if not pd.isna(d) else str(row["Date"])
                        curr_txt = f"  CURSOR:{cursor_price:.2f}" if cursor_price is not None else "  CURSOR:--"
                        return f"D:{d_txt}  O:{row['Open']:.2f}  H:{row['High']:.2f}  L:{row['Low']:.2f}  C:{row['Close']:.2f}{curr_txt}"
            curr_txt = "  CURSOR:--"
            return f"D:---- -- --  O:--  H:--  L:--  C:--{curr_txt}"

        app.clientside_callback(
            """
            function(n) {
                try {
                    fetch('/heartbeat', {method: 'POST', keepalive: true});
                } catch (e) {}
                return n || 0;
            }
            """,
            Output("heartbeat-store", "data"),
            Input("heartbeat-interval", "n_intervals"),
            prevent_initial_call=False,
        )

        @app.callback(
            Output("result-box", "children"),
            Output("finished-store", "data"),
            Input("finish-btn", "n_clicks"),
            State("levels-store", "data"),
            State("position-type", "value"),
            State("capital", "value"),
            State("lot-cost", "value"),
            State("pip-value", "value"),
            State("spread-mult", "value"),
            State("pip-size", "value"),
            State("objects-store", "data"),
            State("level-points-store", "data"),
            prevent_initial_call=True,
        )
        def finalize(n_clicks, levels_store, position_type, capital, lot_cost, pip_value, spread_mult, pip_size, objects_store, level_points):
            if n_clicks > 0:
                levels_store = levels_store or {}
                levels_store.update(
                    {
                        "position_type": position_type,
                        "capital": round((capital or 255000), 2),
                        "lot_cost": round((lot_cost or 0), 2),
                        "pip_value": round((pip_value or 0), 2),
                        "spread_multiplier": round((spread_mult or 0), 2),
                        "spread": round((spread_mult or 0) * (pip_value or 0), 2),
                        "pip_size": pip_size or 0.0001,
                        "drawn_objects": objects_store or [],
                        "level_points": level_points or {},
                        "__finished__": True,
                    }
                )
                self.values = levels_store
                self._finished = True
                def trigger_shutdown():
                    try:
                        req = Request("http://127.0.0.1:8050/shutdown", method="POST")
                        urlopen(req, timeout=1)
                    except Exception:
                        pass
                threading.Timer(0.4, trigger_shutdown).start()
                return "Saved. Closing app...", True
            return "", False

        app.clientside_callback(
            """
            function(finished, current) {
                if (finished) {
                    try {
                        window.open('', '_self');
                        window.close();
                    } catch (e) {}
                    return (current || 0) + 1;
                }
                return current || 0;
            }
            """,
            Output("close-tab-signal", "data"),
            Input("finished-store", "data"),
            State("close-tab-signal", "data"),
            prevent_initial_call=False,
        )

        threading.Timer(0.8, lambda: webbrowser.open("http://127.0.0.1:8050/")).start()
        server = make_server("127.0.0.1", 8050, app.server, threaded=True, request_handler=QuietRequestHandler)
        server_holder["server"] = server
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            while server_thread.is_alive():
                if self._finished:
                    server.shutdown()
                    break
                if time.time() - heartbeat["ts"] > 4:
                    server.shutdown()
                    break
                server_thread.join(0.1)
        except KeyboardInterrupt:
            if self._finished:
                server.shutdown()
            else:
                raise
        server_thread.join(timeout=2)
        return self.values

    def save_chart_snapshot(self, levels: dict, file_path: Path):
        file_path.parent.mkdir(parents=True, exist_ok=True)
        objects = levels.get("drawn_objects", []) if isinstance(levels, dict) else []
        level_points = (levels.get("level_points") if isinstance(levels, dict) else None) or {}
        if not level_points:
            for field in SELECTION_SEQUENCE:
                value = levels.get(field) if isinstance(levels, dict) else None
                if isinstance(value, (int, float)):
                    level_points[field] = {"price": value, "date": self.df["Date"].iloc[-1]}
        fig = self._build_figure(levels if isinstance(levels, dict) else {}, level_points, objects)
        fig.write_image(str(file_path), width=1800, height=1000)
