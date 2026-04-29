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
        source_provider: str | None = None,
    ):
        self.symbol = symbol
        self.df = dataframe.dropna(subset=["Open", "High", "Low", "Close"]).sort_values("Date").reset_index(drop=True)
        self.instrument_type = instrument_type
        self.values = preset_values or {}
        self._finished = False
        self.source_ticker = source_ticker
        self.source_name = source_name
        self.source_provider = (source_provider or "unknown").upper()
        self.price_precision = 3 if instrument_type == "forex" else 2

    def _precision_for_price(self, value: float | None = None) -> int:
        if value is None:
            if not self.df.empty:
                value = pd.to_numeric(pd.Series([self.df["Close"].iloc[-1]]), errors="coerce").iloc[0]
            else:
                value = 0
        try:
            abs_value = abs(float(value))
        except (TypeError, ValueError):
            return self.price_precision
        if abs_value < 1:
            return 4
        return self.price_precision

    def _round_price(self, value: float) -> float:
        precision = self._precision_for_price(value)
        return round(float(value), precision)

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

    def _has_weekend_data(self) -> bool:
        dates = pd.to_datetime(self.df["Date"], errors="coerce")
        if dates.empty:
            return False
        return bool((dates.dt.weekday >= 5).any())

    def _date_window(self, date_value, size: int = 5):
        dates = list(self.df["Date"])
        idx = self._resolve_candle_index(date_value)
        if idx is None:
            return None, None
        left = max(0, idx - size)
        right = min(len(dates) - 1, idx + size)
        return dates[left], dates[right]

    def _build_figure(self, current_values: dict, level_points: dict, objects: list[dict] | None = None, active_tool: str = "level"):
        display_precision = self._precision_for_price()
        show_ichimoku = bool((current_values or {}).get("__show_ichimoku__", False))
        has_weekend_data = self._has_weekend_data()
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

        if show_ichimoku and len(self.df) >= 52:
            dates = pd.to_datetime(self.df["Date"], errors="coerce")
            highs = pd.to_numeric(self.df["High"], errors="coerce")
            lows = pd.to_numeric(self.df["Low"], errors="coerce")
            closes = pd.to_numeric(self.df["Close"], errors="coerce")

            tenkan = (highs.rolling(9).max() + lows.rolling(9).min()) / 2
            kijun = (highs.rolling(26).max() + lows.rolling(26).min()) / 2
            span_a_base = (tenkan + kijun) / 2
            span_b_base = (highs.rolling(52).max() + lows.rolling(52).min()) / 2

            last_date = dates.iloc[-1]
            if not pd.isna(last_date):
                date_builder = pd.date_range if has_weekend_data else pd.bdate_range
                future_dates = list(date_builder(last_date + pd.Timedelta(days=1), periods=26))
            else:
                future_dates = []
            x_all = list(dates) + future_dates

            span_a = [np.nan] * len(x_all)
            span_b = [np.nan] * len(x_all)
            for i, val in enumerate(span_a_base):
                j = i + 26
                if j < len(x_all) and pd.notna(val):
                    span_a[j] = float(val)
            for i, val in enumerate(span_b_base):
                j = i + 26
                if j < len(x_all) and pd.notna(val):
                    span_b[j] = float(val)

            fig.add_trace(go.Scatter(x=dates, y=tenkan, mode="lines", name="Tenkan-sen", line={"color": "#ef4444", "width": 1.0}))
            fig.add_trace(go.Scatter(x=dates, y=kijun, mode="lines", name="Kijun-sen", line={"color": "#3b82f6", "width": 1.7}))
            fig.add_trace(go.Scatter(x=x_all, y=span_a, mode="lines", name="Senkou Span A", line={"color": "#22c55e", "width": 1.2}))
            fig.add_trace(go.Scatter(x=x_all, y=span_b, mode="lines", name="Senkou Span B", line={"color": "#ef4444", "width": 1.2}))

            valid_idx = [i for i, (a, b) in enumerate(zip(span_a, span_b)) if not np.isnan(a) and not np.isnan(b)]
            cloud_segments = []
            if valid_idx:
                seg_start = valid_idx[0]
                prev_i = valid_idx[0]
                prev_sign = 1 if span_a[prev_i] >= span_b[prev_i] else -1
                for i in valid_idx[1:]:
                    sign = 1 if span_a[i] >= span_b[i] else -1
                    if i != prev_i + 1 or sign != prev_sign:
                        cloud_segments.append((seg_start, prev_i, prev_sign))
                        seg_start = i
                    prev_i = i
                    prev_sign = sign
                cloud_segments.append((seg_start, prev_i, prev_sign))

            bull_added = False
            bear_added = False
            for start_i, end_i, sign in cloud_segments:
                x_seg = x_all[start_i : end_i + 1]
                a_seg = span_a[start_i : end_i + 1]
                b_seg = span_b[start_i : end_i + 1]
                if len(x_seg) < 2:
                    continue
                fill_color = "rgba(34,197,94,0.22)" if sign > 0 else "rgba(239,68,68,0.22)"
                show_name = "Ichimoku Bull Cloud" if sign > 0 else "Ichimoku Bear Cloud"
                show_legend = (sign > 0 and not bull_added) or (sign < 0 and not bear_added)
                fig.add_trace(go.Scatter(x=x_seg, y=a_seg, mode="lines", line={"width": 0}, showlegend=False, hoverinfo="skip"))
                fig.add_trace(
                    go.Scatter(
                        x=x_seg,
                        y=b_seg,
                        mode="lines",
                        fill="tonexty",
                        fillcolor=fill_color,
                        line={"width": 0},
                        name=show_name,
                        showlegend=show_legend,
                        hoverinfo="skip",
                    )
                )
                bull_added = bull_added or (sign > 0)
                bear_added = bear_added or (sign < 0)

            chikou = closes.shift(-26)
            fig.add_trace(go.Scatter(x=dates, y=chikou, mode="lines", name="Chikou Span", line={"color": "rgba(250, 204, 21, 0.58)", "width": 1.1, "dash": "dot"}))

        # Transparent heatmap overlay for precise XY cursor price picking.
        y_min = float(self.df["Low"].min())
        y_max = float(self.df["High"].max())
        y_pad = (y_max - y_min) * 0.05 if y_max > y_min else 1.0
        y_low = y_min - y_pad
        y_high = y_max + y_pad
        precision_tick = 10 ** (-self._precision_for_price((y_min + y_max) / 2.0))
        target_steps = int((y_high - y_low) / precision_tick) if precision_tick > 0 else 0
        grid_points = max(400, min(2200, target_steps))
        y_grid = np.linspace(y_low, y_high, grid_points)
        x_min_data = pd.to_datetime(self.df["Date"].min(), errors="coerce")
        x_max_data = pd.to_datetime(self.df["Date"].max(), errors="coerce")
        pad_days = 10
        x_grid = list(self.df["Date"])
        if not pd.isna(x_min_data) and not pd.isna(x_max_data):
            if has_weekend_data:
                x_grid = list(pd.date_range(x_min_data - pd.Timedelta(days=pad_days), x_max_data + pd.Timedelta(days=pad_days)))
            else:
                x_grid = list(pd.bdate_range(x_min_data - pd.tseries.offsets.BDay(pad_days), x_max_data + pd.tseries.offsets.BDay(pad_days)))
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
            price = point.get("price", point.get("plot_price"))
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
                    name=f"{LABELS[field]}: {price:.{display_precision}f}",
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
                        hovertemplate=f"ENTRY click: %{{y:.{display_precision}f}}<extra></extra>",
                        showlegend=True,
                    )
                )

        for obj in (objects or []):
            obj_type = obj.get("type")
            is_preview_line = obj_type == "preview_line"
            is_fib_618 = obj_type == "fib" and "61.8%" in str(obj.get("label", ""))
            line_width = 2.0 if is_fib_618 else (1.6 if obj_type == "fib" else 1.2)
            line_color = "#94a3b8" if is_preview_line else ("#ffffff" if is_fib_618 else obj.get("color", LINE_COLORS["gold"]))
            mode = "lines" if is_preview_line else ("lines+text+markers" if is_fib_618 else "lines+text")
            fig.add_trace(
                go.Scatter(
                    x=[obj.get("x0"), obj.get("x1")],
                    y=[obj.get("y0"), obj.get("y1")],
                    mode=mode,
                    line={"color": line_color, "width": line_width, "dash": "dot" if is_preview_line else "solid"},
                    marker={"size": 5, "color": line_color} if is_fib_618 else None,
                    text=[] if is_preview_line else ["", obj.get("label", "OBJECT")],
                    textposition="top center",
                    name="Line preview" if is_preview_line else obj.get("label", "OBJECT"),
                    customdata=None if is_preview_line else None,
                    hovertemplate=None,
                    hoverinfo="skip",
                    showlegend=not is_preview_line,
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
            rangebreaks=[] if has_weekend_data else [dict(bounds=["sat", "mon"])],
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
        ichimoku_on = bool((self.values or {}).get("__show_ichimoku__", False))
        currency_fee_on = bool((self.values or {}).get("apply_currency_conversion_fee", False))
        currency_fee_eligible = bool((self.values or {}).get("__currency_fee_eligible__", False))

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
                                html.Button(
                                    f"Ichimoku: {'ON' if ichimoku_on else 'OFF'}",
                                    id="ichimoku-toggle-btn",
                                    n_clicks=0,
                                    style={"fontWeight": "700"},
                                ),
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
                            figure=self._build_figure(self.values, initial_level_points, initial_objects, active_tool="level"),
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
                        html.Div(
                            f"Name/Ticker: {self.source_name or self.symbol}"
                            + (f" ({self.source_ticker})" if self.source_ticker else ""),
                            style={"marginBottom": "8px", "fontWeight": "800", "fontSize": "20px", "color": "#f8fafc"},
                        ),
                        html.H4(f"Instrument: {self.instrument_type.upper()}", style={"marginTop": "0", "marginBottom": "6px", "color": "#cbd5e1"}),
                        html.Div(f"SOURCE: {self.source_provider}", style={"marginBottom": "12px", "fontWeight": "700", "color": "#93c5fd", "fontSize": "16px"}),
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
                        html.Button(
                            f"FX conversion fee 1%: {'ON' if currency_fee_on else 'OFF'}",
                            id="currency-fee-toggle",
                            n_clicks=0,
                            style={
                                "marginTop": "8px",
                                "width": "100%",
                                "padding": "8px",
                                "display": "block" if currency_fee_eligible else "none",
                                "background": "#2563eb" if currency_fee_on else "#1f2937",
                                "color": "white" if currency_fee_on else "#e5e7eb",
                                "border": "1px solid #334155",
                            },
                        ),
                        html.Label("Lot cost", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="lot-cost", type="number", value=self.values.get("lot_cost") if self.values.get("lot_cost") not in (0, None) else None, style=self._input_style(), disabled=is_stock),
                        html.Label("Pip value", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="pip-value", type="number", value=self.values.get("pip_value") if self.values.get("pip_value") not in (0, None) else None, style=self._input_style(), disabled=is_stock),
                        html.Label("Spread multiplier (spread = Multiplier * pip_value)", style={"marginTop": "8px", "display": "block", "opacity": 0.5 if is_stock else 1}),
                        dcc.Input(id="spread-mult", type="number", value=self.values.get("spread_multiplier") if self.values.get("spread_multiplier") not in (0, None) else None, placeholder="e.g. 9", style=self._input_style(), disabled=is_stock),
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
                dcc.Store(id="viewport-store", data=None),
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
            if clicked_object_id and active_tool == "level":
                return levels_store, level_points, objects_store, line_anchor, fib_anchor, half_anchor, clicked_object_id

            price = self._extract_price(point)
            date = point.get("x")
            if price is None:
                return levels_store, level_points, objects_store, line_anchor, fib_anchor, half_anchor, None

            if active_tool == "line":
                if line_anchor is None:
                    return levels_store, level_points, objects_store, {"x": date, "y": self._round_price(price)}, fib_anchor, half_anchor, None
                objects_store.append(
                    {
                        "id": str(uuid4()),
                        "type": "line",
                        "label": "LINE",
                        "x0": line_anchor["x"],
                        "y0": line_anchor["y"],
                        "x1": date,
                        "y1": self._round_price(price),
                        "color": color or LINE_COLORS["gold"],
                    }
                )
                return levels_store, level_points, objects_store, None, fib_anchor, half_anchor, None

            if active_tool == "fib":
                if fib_anchor is None:
                    return levels_store, level_points, objects_store, line_anchor, {"x": date, "y": self._round_price(price)}, half_anchor, None

                y_start = self._round_price(fib_anchor["y"])
                y_end = self._round_price(price)
                x_start = pd.to_datetime(fib_anchor["x"], errors="coerce")
                x_end = pd.to_datetime(date, errors="coerce")
                x_right = pd.to_datetime(self.df.iloc[-1]["Date"], errors="coerce")
                if pd.isna(x_start) or pd.isna(x_end) or x_start == x_end:
                    x_start = pd.to_datetime(self.df.iloc[0]["Date"], errors="coerce")
                    x_end = pd.to_datetime(self.df.iloc[-1]["Date"], errors="coerce")

                delta = y_end - y_start
                retrace_levels = [0.0, 0.618, 1.0]
                fib_group_id = str(uuid4())
                last_date = pd.to_datetime(self.df.iloc[-1]["Date"], errors="coerce")
                x_right = last_date if not pd.isna(last_date) else x_end
                x_common_end = x_right + abs(x_end - x_start) * 3

                for r in retrace_levels:
                    pct = f"{r * 100:.1f}%".replace(".0%", "%")
                    y_val = self._round_price(y_end - delta * r)
                    base_label = f"FIB {pct}"
                    label = f"{base_label} ({y_val:.{self.price_precision}f})"
                    x_level_start = x_start + (x_end - x_start) * (1 - r)
                    if abs(r - 0.618) < 1e-9:
                        x_level_start = x_end
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
                            "group_id": fib_group_id,
                        }
                    )
                return levels_store, level_points, objects_store, line_anchor, None, half_anchor, None

            if active_tool == "half":
                current_price = self._round_price(price)
                if half_anchor is None:
                    return levels_store, level_points, objects_store, line_anchor, fib_anchor, {"x": date, "y": current_price}, None
                midpoint = self._round_price((half_anchor["y"] + current_price) / 2.0)
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
                    selected = self._round_price(float(row["High"])) if active_field == "high" else self._round_price(float(row["Low"]))
                    resolved_date = self.df.iloc[idx]["Date"]
                    tick = 10 ** (-self._precision_for_price(selected))
                    candle_span = abs(float(row["High"]) - float(row["Low"]))
                    offset = max(candle_span * 0.12, tick * 8, abs(selected) * 0.002)
                    plot_price = selected + offset if active_field == "high" else selected - offset
                else:
                    selected = None
                    resolved_date = date
                    plot_price = None
            else:
                selected = self._round_price(price)
                idx = self._resolve_candle_index(date)
                resolved_date = self.df.iloc[idx]["Date"] if idx is not None else date
                plot_price = selected

            if selected is not None:
                levels_store[active_field] = selected
                level_points[active_field] = {"price": selected, "plot_price": self._round_price(plot_price), "date": resolved_date}

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
            if str(selected_id).startswith("fib-group:"):
                fib_group_id = str(selected_id).split(":", 1)[1]
                return [obj for obj in objects_store if obj.get("group_id") != fib_group_id]
            return [obj for obj in objects_store if obj.get("id") != selected_id]

        @app.callback(
            Output("ichimoku-toggle-btn", "children"),
            Output("levels-store", "data", allow_duplicate=True),
            Input("ichimoku-toggle-btn", "n_clicks"),
            State("levels-store", "data"),
            prevent_initial_call=True,
        )
        def toggle_ichimoku(_, levels_store):
            levels_store = levels_store or {}
            current = bool(levels_store.get("__show_ichimoku__", False))
            new_value = not current
            levels_store["__show_ichimoku__"] = new_value
            return f"Ichimoku: {'ON' if new_value else 'OFF'}", levels_store

        @app.callback(
            Output("currency-fee-toggle", "children"),
            Output("currency-fee-toggle", "style"),
            Output("levels-store", "data", allow_duplicate=True),
            Input("currency-fee-toggle", "n_clicks"),
            State("currency-fee-toggle", "style"),
            State("levels-store", "data"),
            prevent_initial_call=True,
        )
        def toggle_currency_fee(_, current_style, levels_store):
            levels_store = levels_store or {}
            current = bool(levels_store.get("apply_currency_conversion_fee", False))
            new_value = not current
            levels_store["apply_currency_conversion_fee"] = new_value
            style = dict(current_style or {})
            style["background"] = "#2563eb" if new_value else "#1f2937"
            style["color"] = "white" if new_value else "#e5e7eb"
            return f"FX conversion fee 1%: {'ON' if new_value else 'OFF'}", style, levels_store

        @app.callback(
            Output("viewport-store", "data"),
            Input("candle-chart", "relayoutData"),
            State("viewport-store", "data"),
            prevent_initial_call=True,
        )
        def keep_viewport(relayout_data, current_view):
            if not isinstance(relayout_data, dict):
                return current_view
            updated = dict(current_view or {})
            x0 = relayout_data.get("xaxis.range[0]")
            x1 = relayout_data.get("xaxis.range[1]")
            y0 = relayout_data.get("yaxis.range[0]")
            y1 = relayout_data.get("yaxis.range[1]")
            if x0 is not None and x1 is not None:
                updated["x_range"] = [x0, x1]
            if y0 is not None and y1 is not None:
                updated["y_range"] = [y0, y1]
            return updated

        @app.callback(
            Output("candle-chart", "figure"),
            Output("values-panel", "children"),
            Output("object-picker", "options"),
            [Output(f"btn-{field}", "style") for field in SELECTION_SEQUENCE],
            Output("tool-line", "style"),
            Output("tool-fib", "style"),
            Output("tool-half", "style"),
            Output("ichimoku-toggle-btn", "style"),
            Input("levels-store", "data"),
            Input("level-points-store", "data"),
            Input("objects-store", "data"),
            Input("active-field", "data"),
            Input("active-tool", "data"),
            Input("line-anchor", "data"),
            Input("fib-anchor", "data"),
            State("viewport-store", "data"),
        )
        def redraw(levels_store, level_points, objects_store, active_field, active_tool, line_anchor, fib_anchor, viewport):
            levels_store = levels_store or {}
            level_points = level_points or {}
            objects_store = objects_store or []
            draw_objects = list(objects_store)

            fig = self._build_figure(levels_store, level_points, draw_objects, active_tool=active_tool)

            if isinstance(viewport, dict):
                if viewport.get("x_range"):
                    fig.update_xaxes(range=viewport["x_range"])
                if viewport.get("y_range"):
                    fig.update_yaxes(range=viewport["y_range"])

            lines = [html.Div(f"Mode: {active_tool.upper()}")]
            if active_tool == "level":
                lines.append(html.Div(f"Active button: {LABELS.get(active_field, active_field)}"))
            for field in SELECTION_SEQUENCE:
                value = levels_store.get(field)
                lines.append(html.Div(f"{LABELS[field]}: {'-' if value is None else f'{value:.{self._precision_for_price(value)}f}'}"))

            obj_options = []
            seen_fib_groups = set()
            for obj in objects_store:
                if obj.get("type") == "fib" and obj.get("group_id"):
                    group_id = obj.get("group_id")
                    if group_id in seen_fib_groups:
                        continue
                    seen_fib_groups.add(group_id)
                    obj_options.append({"label": f"FIB ({group_id[:8]})", "value": f"fib-group:{group_id}"})
                    continue
                obj_options.append({"label": f"{obj.get('label', 'OBJ')} ({obj.get('id')[:8]})", "value": obj.get("id")})

            btn_styles = []
            for field in SELECTION_SEQUENCE:
                if active_tool == "level" and field == active_field:
                    btn_styles.append({"background": "#2563eb", "color": "white", "border": "1px solid #2563eb", "padding": "8px"})
                else:
                    btn_styles.append({"background": "#1f2937", "color": "#e5e7eb", "border": "1px solid #334155", "padding": "8px"})

            tool_active_style = {"background": "#2563eb", "color": "white", "border": "1px solid #2563eb"}
            tool_idle_style = {"background": "#1f2937", "color": "#e5e7eb", "border": "1px solid #334155"}
            line_style = tool_active_style if active_tool == "line" else tool_idle_style
            fib_style = tool_active_style if active_tool == "fib" else tool_idle_style
            half_style = tool_active_style if active_tool == "half" else tool_idle_style
            ichimoku_style = tool_active_style if levels_store.get("__show_ichimoku__", False) else tool_idle_style

            return fig, lines, obj_options, *btn_styles, line_style, fib_style, half_style, ichimoku_style


        app.clientside_callback(
            """
            function(hoverData, figure, activeTool, lineAnchor) {
                if (!figure) {
                    return window.dash_clientside.no_update;
                }
                const baseData = (figure.data || []).filter((trace) => trace.name !== 'Line preview');
                if (activeTool !== 'line' || !lineAnchor) {
                    if (baseData.length === (figure.data || []).length) {
                        return window.dash_clientside.no_update;
                    }
                    return {...figure, data: baseData};
                }

                let hoverPoint = null;
                if (hoverData && hoverData.points && hoverData.points.length > 0) {
                    const first = hoverData.points[0];
                    const rawY = first.y ?? first.close ?? first.high ?? first.low ?? first.open;
                    if (rawY !== null && rawY !== undefined && first.x !== null && first.x !== undefined) {
                        hoverPoint = {x: first.x, y: Number(rawY)};
                    }
                }

                if (!hoverPoint) {
                    return {...figure, data: baseData};
                }

                const preview = {
                    type: 'scatter',
                    x: [lineAnchor.x, hoverPoint.x],
                    y: [lineAnchor.y, hoverPoint.y],
                    mode: 'lines',
                    line: {color: '#94a3b8', width: 1.2, dash: 'dot'},
                    name: 'Line preview',
                    hoverinfo: 'skip',
                    showlegend: false,
                };
                return {...figure, data: [...baseData, preview]};
            }
            """,
            Output("candle-chart", "figure", allow_duplicate=True),
            Input("candle-chart", "hoverData"),
            State("candle-chart", "figure"),
            State("active-tool", "data"),
            State("line-anchor", "data"),
            prevent_initial_call=True,
        )

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
                        curr_txt = f"  CURSOR:{cursor_price:.{self._precision_for_price(cursor_price)}f}" if cursor_price is not None else "  CURSOR:--"
                        return (
                            f"D:{d_txt}"
                            f"  O:{row['Open']:.{self._precision_for_price(row['Open'])}f}"
                            f"  H:{row['High']:.{self._precision_for_price(row['High'])}f}"
                            f"  L:{row['Low']:.{self._precision_for_price(row['Low'])}f}"
                            f"  C:{row['Close']:.{self._precision_for_price(row['Close'])}f}"
                            f"{curr_txt}"
                        )
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
            State("objects-store", "data"),
            State("level-points-store", "data"),
            prevent_initial_call=True,
        )
        def finalize(n_clicks, levels_store, position_type, capital, lot_cost, pip_value, spread_mult, objects_store, level_points):
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
