from __future__ import annotations

from pathlib import Path
import base64
import json
import socket
import threading
import time
import webbrowser
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request
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


class LightweightChartLevelSelectorUI:
    """TradingView Lightweight Charts based level selector.

    The public contract intentionally mirrors ``ChartLevelSelectorUI`` so the
    level-selector workflow can keep using the same selected-values/session
    payloads while replacing Plotly as the interactive charting engine.
    """

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
        self._snapshot_data_url: str | None = None
        self.source_ticker = source_ticker
        self.source_name = source_name
        self.source_provider = (source_provider or "unknown").upper()
        self.price_precision = 3 if instrument_type == "forex" else 2
        self.server_port = self._pick_free_port()

    @staticmethod
    def _pick_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return int(s.getsockname()[1])

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
        return round(float(value), self._precision_for_price(value))

    def _resolve_candle_index(self, date_value):
        if self.df.empty:
            return None
        target = pd.to_datetime(date_value, errors="coerce")
        if pd.isna(target):
            return len(self.df) - 1
        all_dates = pd.to_datetime(self.df["Date"], errors="coerce")
        deltas = (all_dates - target).abs()
        return int(deltas.idxmin())

    def _date_window(self, date_value, size: int = 5):
        dates = list(self.df["Date"])
        idx = self._resolve_candle_index(date_value)
        if idx is None:
            return None, None
        left = max(0, idx - size)
        right = min(len(dates) - 1, idx + size)
        return dates[left], dates[right]

    def _has_weekend_data(self) -> bool:
        dates = pd.to_datetime(self.df["Date"], errors="coerce")
        if dates.empty:
            return False
        return bool((dates.dt.weekday >= 5).any())

    def _json_safe(self, value):
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._json_safe(v) for v in value]
        if isinstance(value, tuple):
            return [self._json_safe(v) for v in value]
        if isinstance(value, (pd.Timestamp, np.datetime64)):
            ts = pd.to_datetime(value, errors="coerce")
            return None if pd.isna(ts) else ts.strftime("%Y-%m-%d")
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if pd.isna(value) if not isinstance(value, (str, bytes, bool, type(None))) else False:
            return None
        return value

    def _ohlc_payload(self) -> list[dict]:
        rows = []
        for _, row in self.df.iterrows():
            ts = pd.to_datetime(row["Date"], errors="coerce")
            if pd.isna(ts):
                continue
            rows.append(
                {
                    "time": ts.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                }
            )
        return rows

    def _ichimoku_payload(self) -> dict[str, list[dict]]:
        empty = {"tenkan": [], "kijun": [], "spanA": [], "spanB": [], "chikou": []}
        if len(self.df) < 52:
            return empty
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
            builder = pd.date_range if self._has_weekend_data() else pd.bdate_range
            future_dates = list(builder(last_date + pd.Timedelta(days=1), periods=26))
        else:
            future_dates = []
        x_all = list(dates) + future_dates

        def line_payload(xs, ys):
            out = []
            for x, y in zip(xs, ys):
                if pd.isna(x) or pd.isna(y):
                    continue
                out.append({"time": pd.to_datetime(x).strftime("%Y-%m-%d"), "value": float(y)})
            return out

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
        return {
            "tenkan": line_payload(dates, tenkan),
            "kijun": line_payload(dates, kijun),
            "spanA": line_payload(x_all, span_a),
            "spanB": line_payload(x_all, span_b),
            "chikou": line_payload(dates, closes.shift(-26)),
        }

    def _payload(self) -> dict:
        return {
            "symbol": self.symbol,
            "instrumentType": self.instrument_type,
            "sourceTicker": self.source_ticker,
            "sourceName": self.source_name,
            "sourceProvider": self.source_provider,
            "pricePrecision": self._precision_for_price(),
            "basePrecision": self.price_precision,
            "selectionSequence": SELECTION_SEQUENCE,
            "labels": LABELS,
            "lineColors": LINE_COLORS,
            "values": self._json_safe(self.values),
            "ohlc": self._ohlc_payload(),
            "ichimoku": self._ichimoku_payload(),
        }


    def _fallback_lightweight_charts_script(self) -> str:
        return r"""
  <script>
  if (!window.LightweightCharts) {
    window.LightweightCharts = (() => {
      const LineStyle = {Solid: 0, Dotted: 1, Dashed: 2};
      const CrosshairMode = {Normal: 0};
      const CandlestickSeries = 'CandlestickSeries';
      const LineSeries = 'LineSeries';
      function createChart(container, options) {
        const canvas = document.createElement('canvas');
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.display = 'block';
        container.innerHTML = '';
        container.appendChild(canvas);
        const ctx = canvas.getContext('2d');
        const state = {series: [], candleSeries: null, clickHandlers: [], moveHandlers: [], yMin: 0, yMax: 1, width: 1, height: 1, dpr: 1};
        const colors = {
          bg: options?.layout?.background?.color || '#111827',
          text: options?.layout?.textColor || '#e5e7eb',
          grid: options?.grid?.vertLines?.color || '#1f2937',
        };
        function resize() {
          const rect = container.getBoundingClientRect();
          state.dpr = window.devicePixelRatio || 1;
          state.width = Math.max(1, Math.floor(rect.width));
          state.height = Math.max(1, Math.floor(rect.height));
          canvas.width = Math.floor(state.width * state.dpr);
          canvas.height = Math.floor(state.height * state.dpr);
          ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
          draw();
        }
        function allPrices() {
          const out = [];
          state.series.forEach(s => (s.data || []).forEach(p => {
            if (s.kind === 'candlestick') out.push(p.open, p.high, p.low, p.close);
            else out.push(p.value);
          }));
          return out.filter(Number.isFinite);
        }
        function candleData() { return state.candleSeries?.data || []; }
        function xForIndex(idx) {
          const data = candleData();
          const left = 54, right = 70;
          const plotW = Math.max(1, state.width - left - right);
          if (data.length <= 1) return left + plotW / 2;
          return left + (idx / (data.length - 1)) * plotW;
        }
        function indexForTime(time) {
          const data = candleData();
          const key = typeof time === 'string' ? time : String(time || '').slice(0, 10);
          const found = data.findIndex(p => p.time === key);
          return found >= 0 ? found : 0;
        }
        function priceToY(price) {
          const top = 18, bottom = 28;
          const plotH = Math.max(1, state.height - top - bottom);
          const span = state.yMax - state.yMin || 1;
          return top + ((state.yMax - price) / span) * plotH;
        }
        function yToPrice(y) {
          const top = 18, bottom = 28;
          const plotH = Math.max(1, state.height - top - bottom);
          const ratio = Math.max(0, Math.min(1, (y - top) / plotH));
          return state.yMax - ratio * (state.yMax - state.yMin || 1);
        }
        function lineDash(style) {
          if (style === LineStyle.Dotted) return [2, 4];
          if (style === LineStyle.Dashed) return [6, 4];
          return [];
        }
        function drawAxes() {
          ctx.strokeStyle = colors.grid;
          ctx.lineWidth = 1;
          ctx.font = '11px ui-monospace, monospace';
          ctx.fillStyle = colors.text;
          for (let i = 0; i <= 4; i++) {
            const y = 18 + i * (Math.max(1, state.height - 46) / 4);
            ctx.beginPath(); ctx.moveTo(54, y); ctx.lineTo(state.width - 62, y); ctx.stroke();
            const price = state.yMax - i * ((state.yMax - state.yMin) / 4);
            ctx.fillText(price.toFixed(Math.abs(price) < 1 ? 4 : 2), state.width - 58, y + 4);
          }
        }
        function draw() {
          if (!ctx) return;
          const prices = allPrices();
          const min = prices.length ? Math.min(...prices) : 0;
          const max = prices.length ? Math.max(...prices) : 1;
          const pad = Math.max((max - min) * 0.08, Math.abs(max || 1) * 0.01, 0.01);
          state.yMin = min - pad;
          state.yMax = max + pad;
          ctx.clearRect(0, 0, state.width, state.height);
          ctx.fillStyle = colors.bg;
          ctx.fillRect(0, 0, state.width, state.height);
          drawAxes();
          const candles = candleData();
          const candleW = Math.max(2, Math.min(11, (state.width - 124) / Math.max(1, candles.length) * 0.65));
          candles.forEach((p, idx) => {
            const x = xForIndex(idx), yO = priceToY(p.open), yH = priceToY(p.high), yL = priceToY(p.low), yC = priceToY(p.close);
            const up = p.close >= p.open;
            ctx.strokeStyle = up ? '#22c55e' : '#ef4444';
            ctx.fillStyle = up ? '#22c55e' : '#ef4444';
            ctx.beginPath(); ctx.moveTo(x, yH); ctx.lineTo(x, yL); ctx.stroke();
            const top = Math.min(yO, yC), h = Math.max(1, Math.abs(yC - yO));
            ctx.fillRect(x - candleW / 2, top, candleW, h);
          });
          state.series.filter(s => s.kind === 'line').forEach(s => {
            const pts = (s.data || []).filter(p => Number.isFinite(Number(p.value)));
            if (!pts.length) return;
            ctx.save();
            ctx.strokeStyle = s.options?.color || '#facc15';
            ctx.lineWidth = s.options?.lineWidth || 1.4;
            ctx.setLineDash(lineDash(s.options?.lineStyle));
            ctx.beginPath();
            pts.forEach((p, i) => {
              const x = xForIndex(indexForTime(p.time));
              const y = priceToY(Number(p.value));
              if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();
            ctx.restore();
          });
        }
        function makeSeries(kind, options) {
          const s = {
            kind, options: options || {}, data: [],
            setData(data) { this.data = Array.isArray(data) ? data : []; if (kind === 'candlestick') state.candleSeries = this; draw(); },
            coordinateToPrice(y) { return yToPrice(y); },
            priceToCoordinate(price) { return priceToY(price); },
          };
          state.series.push(s);
          return s;
        }
        function mousePayload(ev) {
          const rect = canvas.getBoundingClientRect();
          const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
          const data = candleData();
          const left = 54, plotW = Math.max(1, state.width - 124);
          const idx = Math.max(0, Math.min(data.length - 1, Math.round(((x - left) / plotW) * Math.max(0, data.length - 1))));
          return {point: {x, y}, time: data[idx]?.time};
        }
        canvas.addEventListener('click', ev => state.clickHandlers.forEach(h => h(mousePayload(ev))));
        canvas.addEventListener('mousemove', ev => state.moveHandlers.forEach(h => h(mousePayload(ev))));
        window.addEventListener('resize', resize);
        setTimeout(resize, 0);
        return {
          addSeries(type, opts) { return makeSeries(type === CandlestickSeries ? 'candlestick' : 'line', opts); },
          addCandlestickSeries(opts) { return makeSeries('candlestick', opts); },
          addLineSeries(opts) { return makeSeries('line', opts); },
          removeSeries(series) { state.series = state.series.filter(s => s !== series); if (state.candleSeries === series) state.candleSeries = null; draw(); },
          timeScale() { return {fitContent(){ draw(); }, setVisibleLogicalRange(){}, getVisibleLogicalRange(){ return null; }, timeToCoordinate(time){ return xForIndex(indexForTime(typeof time === 'string' ? time : String(time || '').slice(0, 10))); }, subscribeVisibleLogicalRangeChange(){}}; },
          subscribeClick(handler) { state.clickHandlers.push(handler); },
          subscribeCrosshairMove(handler) { state.moveHandlers.push(handler); },
          takeScreenshot() { draw(); return canvas; },
        };
      }
      return {createChart, CandlestickSeries, LineSeries, CrosshairMode, LineStyle, __stockhelperFallback: true};
    })();
  }
  </script>
"""

    def _html(self) -> str:
        payload = json.dumps(self._payload(), ensure_ascii=False)
        fallback_script = self._fallback_lightweight_charts_script()
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>StockHelper Lightweight Chart - {self.symbol}</title>
  <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
  {fallback_script}
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #020617; color: #e5e7eb; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .layout {{ display: grid; grid-template-columns: 1fr 380px; height: 100vh; }}
    .main {{ padding: 14px; min-width: 0; }}
    h3 {{ margin: 0 0 10px 0; }}
    button {{ background: #1f2937; color: #e5e7eb; border: 1px solid #334155; border-radius: 6px; padding: 8px; cursor: pointer; font-weight: 700; }}
    button.active {{ background: #2563eb; border-color: #2563eb; color: white; }}
    .level-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }}
    .toolbar {{ display: flex; gap: 8px; margin-bottom: 10px; align-items: center; }}
    #chart-wrap {{ position: relative; height: calc(100vh - 132px); min-height: 480px; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden; }}
    #chart {{ width: 100%; height: 100%; }}
    #cloud-overlay {{ position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 2; }}
    #cursor-box {{ margin-bottom: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 16px; font-weight: 700; text-align: center; }}
    .side {{ border-left: 1px solid #1f2937; padding: 16px; background: #0b1220; overflow-y: auto; }}
    label {{ display: block; margin-top: 8px; }}
    input, select {{ width: 100%; color: black; background: white; font-size: 16px; padding: 6px 8px; border-radius: 4px; border: 1px solid #cbd5e1; }}
    input:disabled, select:disabled {{ opacity: 0.38; background: #475569; color: #cbd5e1; border-color: #334155; cursor: not-allowed; }}
    .muted {{ opacity: .5; }}
    .source {{ margin-bottom: 12px; font-weight: 700; color: #93c5fd; font-size: 16px; }}
    .values {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin-bottom: 8px; white-space: pre-wrap; }}
    .color-dot {{ width: 22px; height: 22px; padding: 0; border: 1px solid white; }}
    #chart-legend {{ display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; min-height: 20px; margin: 0 0 7px 0; font-size: 12px; font-weight: 700; }}
    #chart-legend span {{ display: inline-flex; align-items: center; gap: 5px; cursor: pointer; user-select: none; }}
    #chart-legend span.hidden {{ opacity: 0.38; text-decoration: line-through; }}
    #chart-legend button {{ padding: 0 5px; line-height: 16px; font-size: 11px; border-radius: 4px; background: #334155; color: #e5e7eb; }}
    .fib-label-contrast {{ color: #f8fafc; text-shadow: 0 1px 2px rgba(0,0,0,.65); }}
    #chart-legend i {{ width: 18px; height: 3px; display: inline-block; border-radius: 2px; }}
  </style>
</head>
<body>
  <div class="layout">
    <main class="main">
      <h3>Interactive Level Selector: {self.symbol}</h3>
      <div class="level-grid" id="level-buttons"></div>
      <div class="toolbar">
        <button id="tool-line">Line tool</button>
        <button id="tool-fib">Fib 61.8</button>
        <button id="tool-half">Half→SL</button>
        <button id="ichimoku-toggle">Ichimoku</button>
        <button id="reset-all" style="margin-left:auto">Reset all</button>
        <span>Line color:</span>
        <button class="color-dot" data-color="#facc15" style="background:#facc15"></button>
        <button class="color-dot" data-color="#a855f7" style="background:#a855f7"></button>
        <button class="color-dot" data-color="#22c55e" style="background:#22c55e"></button>
      </div>
      <div id="cursor-box">D:---- -- -- O:-- H:-- L:-- C:-- DAY:-- CURSOR:--</div>
      <div id="chart-legend"></div>
      <div id="chart-wrap"><div id="chart"></div><canvas id="cloud-overlay"></canvas></div>
    </main>
    <aside class="side">
      <div style="margin-bottom:8px;font-weight:800;font-size:20px;color:#f8fafc" id="identity"></div>
      <h4 id="instrument-title" style="margin-top:0;margin-bottom:6px;color:#cbd5e1"></h4>
      <button id="stock-cfd-toggle" style="width:100%;margin-bottom:8px;display:none"></button>
      <div class="source" id="source"></div>
      <h4>Selected values</h4>
      <div id="values-panel" class="values"></div>
      <h4>Manual inputs</h4>
      <label id="position-type-label">Position type</label>
      <select id="position-type"><option value="long">LONG</option><option value="short">SHORT</option></select>
      <label>Capital</label><input id="capital" type="number" />
      <button id="currency-fee-toggle" style="margin-top:8px;width:100%;display:none"></button>
      <label id="lot-cost-label">Lot cost</label><input id="lot-cost" type="number" />
      <label id="pip-value-label">Pip value</label><input id="pip-value" type="number" />
      <label id="spread-mult-label">Spread multiplier (spread = Multiplier * pip_value)</label><input id="spread-mult" type="number" />
      <select id="object-picker" style="display:none"><option value="">-- select --</option></select>
      <button id="delete-object" style="display:none">Delete selected object</button>
      <button id="finish-btn" style="margin-top:16px;width:100%;padding:10px;background:#2563eb;color:white;border:none;border-radius:8px">Finish</button>
      <div id="result-box" style="margin-top:10px"></div>
    </aside>
  </div>
  <script>window.STOCKHELPER_PAYLOAD = {payload};</script>
  <script>
(() => {{
  const P = window.STOCKHELPER_PAYLOAD;
  const seq = P.selectionSequence;
  const labels = P.labels;
  let levels = {{...(P.values || {{}})}};
  let levelPoints = {{...(levels.level_points || {{}})}};
  let drawnObjects = Array.isArray(levels.drawn_objects) ? [...levels.drawn_objects] : [];
  let activeField = seq.some(k => levels[k] != null) ? null : 'high';
  let activeTool = 'level';
  let lineAnchor = null;
  let fibAnchor = null;
  let halfAnchor = null;
  let lineColor = P.lineColors.gold;
  const precision = P.pricePrecision || 2;
  const ohlcByTime = new Map(P.ohlc.map((r, idx) => [r.time, {{...r, idx}}]));

  const $ = id => document.getElementById(id);
  const fmt = (v) => Number(v).toFixed(Math.abs(Number(v)) < 1 ? 4 : precision);
  const roundPrice = (v) => Number(Number(v).toFixed(Math.abs(Number(v)) < 1 ? 4 : precision));
  const dateAtIndex = (idx) => P.ohlc[Math.max(0, Math.min(P.ohlc.length - 1, idx))]?.time || P.ohlc[P.ohlc.length - 1]?.time;
  const nearest = (time) => {{
    if (!time) return P.ohlc[P.ohlc.length - 1];
    if (ohlcByTime.has(time)) return ohlcByTime.get(time);
    const target = new Date(time).getTime();
    let best = P.ohlc[0], dist = Infinity;
    P.ohlc.forEach((r, idx) => {{ const d = Math.abs(new Date(r.time).getTime() - target); if (d < dist) {{ best = {{...r, idx}}; dist = d; }} }});
    return best;
  }};
  const addDays = (date, days) => {{ const d = new Date(date + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + days); return d.toISOString().slice(0, 10); }};
  const compareTime = (a, b) => new Date(String(a).slice(0, 10) + 'T00:00:00Z') - new Date(String(b).slice(0, 10) + 'T00:00:00Z');
  const extendFuture = (time, minDays = 180) => addDays(P.ohlc[P.ohlc.length - 1]?.time || time, minDays);
  const fibColor = (ratio) => ({{1:'#1d4ed8', 0:'#7c3aed', 0.236:'#0f766e', 0.382:'#be123c', 0.618:'#15803d'}})[ratio] || '#2563eb';
  const normalizeLineData = (data) => {{
    const seen = new Set();
    return data
      .filter(p => p && p.time && Number.isFinite(Number(p.value)))
      .map(p => ({{time:String(p.time).slice(0, 10), value:Number(p.value)}}))
      .sort((a, b) => compareTime(a.time, b.time))
      .map(p => {{
        let time = p.time;
        while (seen.has(time)) time = addDays(time, 1);
        seen.add(time);
        return {{...p, time}};
      }});
  }};
  const addLegend = (label, color, key=null, onDelete=null) => {{
    if (!label) return;
    const legend = $('chart-legend');
    const legendKey = key || `${{label}}|${{color}}`;
    if ([...legend.children].some(el => el.dataset.key === legendKey)) return;
    const item = document.createElement('span');
    item.dataset.key = legendKey;
    item.classList.toggle('hidden', hiddenLegendKeys.has(legendKey));
    item.innerHTML = `<i style="background:${{color}}"></i><b>${{label}}</b>`;
    item.onclick = (ev) => {{
      if (ev.target && ev.target.dataset && ev.target.dataset.delete === '1') return;
      hiddenLegendKeys.has(legendKey) ? hiddenLegendKeys.delete(legendKey) : hiddenLegendKeys.add(legendKey);
      render();
    }};
    if (onDelete) {{
      const del = document.createElement('button');
      del.type = 'button';
      del.dataset.delete = '1';
      del.textContent = '×';
      del.title = 'Delete this drawing';
      del.onclick = (ev) => {{ ev.stopPropagation(); onDelete(); render(); }};
      item.appendChild(del);
    }}
    legend.appendChild(item);
  }};
  const resetLegend = () => {{ $('chart-legend').innerHTML = ''; }};

  const chart = LightweightCharts.createChart($('chart'), {{
    layout: {{ background: {{ type: 'solid', color: '#111827' }}, textColor: '#e5e7eb' }},
    grid: {{ vertLines: {{ color: '#1f2937' }}, horzLines: {{ color: '#1f2937' }} }},
    rightPriceScale: {{ borderColor: '#334155' }},
    timeScale: {{ borderColor: '#334155', rightOffset: 18, tickMarkFormatter: (time) => {{
      const d = typeof time === 'string' ? new Date(time + 'T00:00:00Z') : new Date(Date.UTC(time.year, time.month - 1, time.day));
      return d.getUTCMonth() === 0 ? String(d.getUTCFullYear()) : d.toLocaleString('en-US', {{month:'short', timeZone:'UTC'}});
    }} }},
    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
    localization: {{ priceFormatter: p => fmt(p) }},
  }});
  const addLineSeries = (opts) => chart.addSeries ? chart.addSeries(LightweightCharts.LineSeries, opts) : chart.addLineSeries(opts);
  const addCandles = (opts) => chart.addSeries ? chart.addSeries(LightweightCharts.CandlestickSeries, opts) : chart.addCandlestickSeries(opts);
  const candleSeries = addCandles({{ upColor:'#f8fafc', downColor:'#22d3ee', borderUpColor:'#22d3ee', borderDownColor:'#0891b2', wickUpColor:'#22d3ee', wickDownColor:'#0891b2' }});
  candleSeries.setData(P.ohlc);
  if (typeof candleSeries.applyOptions === 'function') candleSeries.applyOptions({{priceLineColor:'#f8fafc', priceLineWidth:1, priceLineStyle:LightweightCharts.LineStyle.Dotted}});
  chart.timeScale().fitContent();
  if (chart.timeScale().subscribeVisibleLogicalRangeChange) chart.timeScale().subscribeVisibleLogicalRangeChange(() => requestAnimationFrame(drawCloud));
  window.addEventListener('resize', () => requestAnimationFrame(drawCloud));
  const dynamicSeries = [];
  let previewSeries = null;
  let previewFrame = null;
  let pendingPreview = null;
  const hiddenLegendKeys = new Set();
  let suppressViewportCapture = false;
  const safeRemoveSeries = (series) => {{ try {{ if (series) chart.removeSeries(series); }} catch(e) {{ console.warn('removeSeries failed', e); }} }};
  const removeDynamic = () => {{ while(dynamicSeries.length) safeRemoveSeries(dynamicSeries.pop()); safeRemoveSeries(previewSeries); previewSeries = null; if (previewFrame) cancelAnimationFrame(previewFrame); previewFrame = null; pendingPreview = null; }};
  const addLine = (data, color, width=1.4, style=LightweightCharts.LineStyle.Solid, title='', legend=true, pointMarkers=false, rightLabel=false, legendKey=null, onDelete=null) => {{
    if (legend && title) addLegend(title, color, legendKey, onDelete);
    if (legendKey && hiddenLegendKeys.has(legendKey)) return null;
    const normalized = normalizeLineData(data || []);
    if (normalized.length === 0) return null;
    const options = {{
      color,
      lineWidth: width,
      lineStyle: style,
      priceLineVisible: false,
      lastValueVisible: !!rightLabel,
      title: rightLabel ? title : '',
      pointMarkersVisible: pointMarkers,
      crosshairMarkerVisible: pointMarkers,
    }};
    const s = addLineSeries(options);
    try {{
      s.setData(normalized);
      if (typeof s.applyOptions === 'function') s.applyOptions(options);
    }} catch(e) {{
      console.warn('Skipping invalid line data', title, e);
      safeRemoveSeries(s);
      return null;
    }}
    dynamicSeries.push(s);
    return s;
  }};


  function updateLinePreview(time, value) {{
    if (!lineAnchor || !Number.isFinite(value)) return;
    pendingPreview = {{time, value}};
    if (previewFrame) return;
    previewFrame = requestAnimationFrame(() => {{
      previewFrame = null;
      const pt = pendingPreview;
      pendingPreview = null;
      if (!pt || !lineAnchor) return;
      if (!previewSeries) previewSeries = addLineSeries({{color:'#94a3b8', lineWidth:1.2, lineStyle:LightweightCharts.LineStyle.Dotted, priceLineVisible:false, lastValueVisible:false, title:''}});
      try {{
        previewSeries.setData(normalizeLineData([{{time:lineAnchor.x, value:lineAnchor.y}}, {{time:pt.time, value:pt.value}}]));
        if (typeof previewSeries.applyOptions === 'function') previewSeries.applyOptions({{priceLineVisible:false,lastValueVisible:false,title:''}});
      }} catch(e) {{ console.warn('line preview failed', e); }}
    }});
  }}

  function cloudPairs() {{
    const map = new Map();
    (P.ichimoku.spanA || []).forEach(p => map.set(p.time, {{time:p.time, a:Number(p.value)}}));
    (P.ichimoku.spanB || []).forEach(p => {{ const row = map.get(p.time) || {{time:p.time}}; row.b = Number(p.value); map.set(p.time, row); }});
    return [...map.values()].filter(p => p.time && Number.isFinite(p.a) && Number.isFinite(p.b)).sort((x, y) => compareTime(x.time, y.time));
  }}

  function wedgeTouchPoints(obj) {{
    const xs = Array.isArray(obj.x) ? obj.x.map(x => String(x).slice(0, 10)) : [];
    const ys = Array.isArray(obj.y) ? obj.y.map(Number) : [];
    const byTime = new Map(xs.map((x, i) => [x, ys[i]]));
    const isUpper = String(obj.label || '').toLowerCase().includes('upper');
    const isLower = String(obj.label || '').toLowerCase().includes('lower');
    const out = [];
    let lastTouchIdx = -999;
    P.ohlc.forEach((row, idx) => {{
      if (!byTime.has(row.time)) return;
      const y = byTime.get(row.time);
      const touchPrice = isUpper ? row.high : (isLower ? row.low : row.close);
      const tolerance = Math.max(Math.abs(row.high - row.low) * 0.28, Math.abs(y || 1) * 0.004);
      if (Math.abs(touchPrice - y) <= tolerance) {{
        if (idx > lastTouchIdx + 1) out.push({{time: row.time, value: y, upper: isUpper, lower:isLower}});
        lastTouchIdx = idx;
      }}
    }});
    (obj.anchor_x || []).forEach((x, i) => out.push({{time:String(x).slice(0, 10), value:Number((obj.anchor_y || [])[i]), anchor:true, upper:isUpper, lower:isLower}}));
    return out.filter(p => p.time && Number.isFinite(p.value));
  }}

  function drawWedgeTouchPoints(ctx) {{
    drawnObjects.filter(obj => obj.type === 'wedge' || obj.group_id === 'auto-wedge').forEach(obj => {{
      const points = wedgeTouchPoints(obj);
      const fill = String(obj.label || '').toLowerCase().includes('upper') ? '#fbbf24' : '#e879f9';
      points.forEach(pt => {{
        const x = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(pt.time) : null;
        const y = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(pt.value) : null;
        if (x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) return;
        ctx.beginPath();
        ctx.arc(x, y, pt.anchor ? 5.2 : 4.4, 0, Math.PI * 2);
        ctx.fillStyle = fill;
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 1.2;
        ctx.fill();
        ctx.stroke();
      }});
    }});
  }}

  function drawValuePointers(ctx) {{
    const pointerFields = ['line_cross_value'];
    pointerFields.forEach(field => {{
      const pt = levelPoints[field];
      if (!pt || hiddenLegendKeys.has(`level:${{field}}`)) return;
      const x = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(pt.date) : null;
      const y = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(pt.price ?? pt.plot_price) : null;
      if (x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) return;
      ctx.save();
      ctx.fillStyle = '#3b82f6';
      ctx.strokeStyle = '#f8fafc';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x, y - 15);
      ctx.lineTo(x - 5, y - 6);
      ctx.lineTo(x + 5, y - 6);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }});
  }}

  function lineValueForDate(obj, time) {{
    if (!obj) return null;
    if (Array.isArray(obj.x) && Array.isArray(obj.y)) {{
      const idx = obj.x.map(x => String(x).slice(0, 10)).indexOf(String(time).slice(0, 10));
      if (idx >= 0) return Number(obj.y[idx]);
    }}
    const x0 = String(obj.x0 || '').slice(0, 10), x1 = String(obj.x1 || '').slice(0, 10);
    const y0 = Number(obj.y0), y1 = Number(obj.y1);
    if (!x0 || !x1 || !Number.isFinite(y0) || !Number.isFinite(y1)) return null;
    const t0 = new Date(x0 + 'T00:00:00Z').getTime();
    const t1 = new Date(x1 + 'T00:00:00Z').getTime();
    const t = new Date(String(time).slice(0, 10) + 'T00:00:00Z').getTime();
    const span = t1 - t0;
    if (!Number.isFinite(t) || span === 0) return y0;
    return y0 + (y1 - y0) * ((t - t0) / span);
  }}

  function firstAnchorPoint(obj) {{
    const ax = Array.isArray(obj.anchor_x) && obj.anchor_x.length ? obj.anchor_x[0] : (Array.isArray(obj.x) && obj.x.length ? obj.x[0] : obj.x0);
    const ay = Array.isArray(obj.anchor_y) && obj.anchor_y.length ? obj.anchor_y[0] : (Array.isArray(obj.y) && obj.y.length ? obj.y[0] : obj.y0);
    if (!ax || !Number.isFinite(Number(ay))) return null;
    return {{date:String(ax).slice(0, 10), price:roundPrice(Number(ay))}};
  }}

  function applyWedgeDerivedLevels() {{
    const wedges = drawnObjects.filter(obj => obj.type === 'wedge' || obj.group_id === 'auto-wedge');
    if (!wedges.length) return;
    const upper = wedges.find(obj => String(obj.label || '').toLowerCase().includes('upper'));
    const lower = wedges.find(obj => String(obj.label || '').toLowerCase().includes('lower'));
    const upperAnchor = firstAnchorPoint(upper || wedges[0]);
    const lowerAnchor = firstAnchorPoint(lower || wedges[1]);
    if (upperAnchor && levels.high == null) {{
      levels.high = upperAnchor.price;
      levelPoints.high = {{price:upperAnchor.price, plot_price:upperAnchor.price, date:upperAnchor.date}};
    }}
    if (lowerAnchor && levels.low == null) {{
      levels.low = lowerAnchor.price;
      levelPoints.low = {{price:lowerAnchor.price, plot_price:lowerAnchor.price, date:lowerAnchor.date}};
    }}
    const candidates = [];
    wedges.forEach(obj => {{
      const label = String(obj.label || '').toLowerCase();
      const isUpper = label.includes('upper');
      const isLower = label.includes('lower');
      let seenInside = false;
      P.ohlc.forEach(row => {{
        const line = lineValueForDate(obj, row.time);
        if (!Number.isFinite(line)) return;
        const inside = isUpper ? row.close <= line : (isLower ? row.close >= line : true);
        if (inside) {{ seenInside = true; return; }}
        if (!seenInside) return;
        if ((isUpper && row.close > line) || (isLower && row.close < line)) candidates.push({{time:row.time, value:roundPrice(line), source:obj, isUpper, isLower}});
      }});
    }});
    candidates.sort((a, b) => compareTime(a.time, b.time));
    if (candidates.length) {{
      const cross = candidates[0];
      const lineCrossIsAuto = levels.line_cross_value == null || levels.__wedge_auto_line_cross__ || levelPoints.line_cross_value?.auto_wedge;
      if (lineCrossIsAuto) {{
        levels.line_cross_value = cross.value;
        levels.__wedge_auto_line_cross__ = true;
        levelPoints.line_cross_value = {{price:cross.value, plot_price:cross.value, date:cross.time, auto_wedge:true}};
      }}
      const counterpart = cross.isUpper ? lower : (cross.isLower ? upper : null);
      const otherLine = lineValueForDate(counterpart, cross.time);
      const stopLossIsAuto = levels.stop_loss == null || levels.__wedge_auto_stop_loss__ || levelPoints.stop_loss?.auto_wedge;
      if (Number.isFinite(otherLine) && stopLossIsAuto) {{
        const stop = roundPrice((cross.value + otherLine) / 2.0);
        levels.stop_loss = stop;
        levels.__wedge_auto_stop_loss__ = true;
        levelPoints.stop_loss = {{price:stop, plot_price:stop, date:cross.time, auto_wedge:true}};
        levels.__half_points__ = [];
      }}
    }}
  }}

  function drawCloud() {{
    const canvas = $('cloud-overlay');
    const wrap = $('chart-wrap');
    if (!canvas || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    canvas.style.width = `${{rect.width}}px`;
    canvas.style.height = `${{rect.height}}px`;
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);
    if (!levels.__show_ichimoku__) {{ drawWedgeTouchPoints(ctx); drawValuePointers(ctx); return; }}
    const pairs = cloudPairs().map(p => ({{
      x: chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(p.time) : null,
      yA: candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(p.a) : null,
      yB: candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(p.b) : null,
      bull: p.a >= p.b,
    }})).filter(p => p.x !== null && p.yA !== null && p.yB !== null && Number.isFinite(p.x) && Number.isFinite(p.yA) && Number.isFinite(p.yB));
    for (let i = 1; i < pairs.length; i++) {{
      const p0 = pairs[i - 1], p1 = pairs[i];
      if (p0.bull !== p1.bull || Math.abs(p1.x - p0.x) > 80) continue;
      ctx.beginPath();
      ctx.moveTo(p0.x, p0.yA); ctx.lineTo(p1.x, p1.yA); ctx.lineTo(p1.x, p1.yB); ctx.lineTo(p0.x, p0.yB); ctx.closePath();
      ctx.fillStyle = p1.bull ? 'rgba(34,197,94,0.18)' : 'rgba(239,68,68,0.18)';
      ctx.fill();
    }}
    drawWedgeTouchPoints(ctx);
    drawValuePointers(ctx);
  }}

  function captureViewport() {{
    if (suppressViewportCapture) return null;
    try {{ return chart.timeScale().getVisibleLogicalRange ? chart.timeScale().getVisibleLogicalRange() : null; }} catch(e) {{ return null; }}
  }}

  function restoreViewport(viewport) {{
    if (!viewport || !chart.timeScale().setVisibleLogicalRange) return;
    requestAnimationFrame(() => {{ try {{ chart.timeScale().setVisibleLogicalRange(viewport); }} catch(e) {{ console.warn('restore viewport failed', e); }} requestAnimationFrame(drawCloud); }});
  }}

  function deleteSelectedLevel(field) {{
    return () => {{
      delete levels[field];
      delete levelPoints[field];
      hiddenLegendKeys.delete(`level:${{field}}`);
      if (field === 'entry') hiddenLegendKeys.delete('level:entry-point');
      if (field === 'stop_loss') levels.__half_points__ = [];
    }};
  }}

  function fibPercentLabel(obj) {{
    const match = String(obj.label || '').match(/([0-9]+(?:\\.[0-9]+)?%)/);
    return match ? match[1] : '';
  }}

  function render() {{
    const viewport = captureViewport();
    removeDynamic();
    resetLegend();
    if (levels.__show_ichimoku__) {{
      addLine(P.ichimoku.tenkan, '#ef4444', 1, LightweightCharts.LineStyle.Solid, 'Tenkan-sen', true, false, false, 'ichi:tenkan');
      addLine(P.ichimoku.kijun, '#3b82f6', 2, LightweightCharts.LineStyle.Solid, 'Kijun-sen', true, false, false, 'ichi:kijun');
      addLine(P.ichimoku.spanA, '#22c55e', 1, LightweightCharts.LineStyle.Solid, 'Senkou Span A', true, false, false, 'ichi:spanA');
      addLine(P.ichimoku.spanB, '#ef4444', 1, LightweightCharts.LineStyle.Solid, 'Senkou Span B', true, false, false, 'ichi:spanB');
      addLine(P.ichimoku.chikou, 'rgba(250,204,21,.8)', 1, LightweightCharts.LineStyle.Dotted, 'Chikou Span', true, false, false, 'ichi:chikou');
    }}
    const levelColors = {{high:'#d946ef', low:'#14b8a6', entry:'#22c55e', stop_loss:'#ef4444', check_zr_value_fibo_or_elevation:'#f59e0b', line_cross_value:'#3b82f6'}};
    seq.forEach(field => {{
      const pt = levelPoints[field]; if (!pt) return;
      const deleteFn = deleteSelectedLevel(field);
      if (field === 'line_cross_value') {{ addLegend(`${{labels[field]}}: ${{fmt(pt.price)}}`, levelColors[field] || '#3b82f6', `level:${{field}}`, deleteFn); return; }}
      const base = nearest(pt.date); const x0 = dateAtIndex(base.idx - 5); const x1 = dateAtIndex(base.idx + 5);
      addLine([{{time:x0, value:pt.plot_price ?? pt.price}}, {{time:x1, value:pt.plot_price ?? pt.price}}], levelColors[field] || '#94a3b8', 2, LightweightCharts.LineStyle.Solid, `${{labels[field]}}: ${{fmt(pt.price)}}`, true, false, false, `level:${{field}}`, deleteFn);
      if (field === 'entry') addLine([{{time:pt.date, value:pt.price}}], levelColors[field], 2.2, LightweightCharts.LineStyle.Solid, '', false, false, false, 'level:entry-point');
    }});
    (levels.__half_points__ || []).forEach((pt, i) => addLine([{{time:pt.date, value:pt.price}}], '#a855f7', 2, LightweightCharts.LineStyle.Solid, 'Half point', true, false, false, `half:${{i}}`));
    const seenFibLegend = new Set();
    let wedgeLegendAdded = false;
    drawnObjects.forEach(obj => {{
      const color = obj.color || P.lineColors.gold;
      const isFib = obj.type === 'fib';
      const isWedge = obj.type === 'wedge' || obj.group_id === 'auto-wedge';
      const fibKey = isFib ? `fib-group:${{obj.group_id || obj.id}}` : null;
      const objKey = isWedge ? `wedge:${{obj.id || obj.label || Math.random()}}` : (isFib ? fibKey : `obj:${{obj.id || obj.label || Math.random()}}`);
      const deleteFn = isFib ? (() => {{ drawnObjects = drawnObjects.filter(o => o.group_id !== obj.group_id); hiddenLegendKeys.delete(fibKey); }}) : (isWedge ? (() => {{ drawnObjects = drawnObjects.filter(o => o !== obj); hiddenLegendKeys.delete(objKey); }}) : (() => {{ drawnObjects = drawnObjects.filter(o => o.id !== obj.id); hiddenLegendKeys.delete(objKey); }}));
      let objectLegend = '';
      let showLegend = false;
      if (isFib) {{
        objectLegend = 'Fibonacci';
        showLegend = !seenFibLegend.has(fibKey);
        seenFibLegend.add(fibKey);
        if (showLegend) addLegend(objectLegend, color, fibKey, deleteFn);
      }} else if (isWedge) {{
        objectLegend = obj.label || 'Falling wedge';
        showLegend = true;
      }} else {{
        objectLegend = obj.label || 'LINE';
        showLegend = true;
      }}
      const seriesTitle = isFib ? (fibPercentLabel(obj) || objectLegend) : objectLegend;
      if (Array.isArray(obj.x) && Array.isArray(obj.y)) {{
        addLine(obj.x.map((x, i) => ({{time:String(x).slice(0,10), value:Number(obj.y[i])}})), color, isWedge ? 3 : (isFib ? 1.2 : 2), LightweightCharts.LineStyle.Solid, seriesTitle, showLegend && !isFib, false, isFib, objKey, deleteFn);
      }} else {{
        const x1 = isFib ? extendFuture(obj.x1, 720) : String(obj.x1).slice(0,10);
        addLine([{{time:String(obj.x0).slice(0,10), value:Number(obj.y0)}}, {{time:x1, value:Number(obj.y1)}}], color, isFib && String(obj.label || '').includes('61.8%') ? 1.4 : (isFib ? 1.0 : 2), LightweightCharts.LineStyle.Solid, seriesTitle, showLegend && !isFib, false, isFib, objKey, deleteFn);
      }}
    }});
    updatePanel();
    requestAnimationFrame(drawCloud);
    restoreViewport(viewport);
  }}

  function updatePanel() {{
    seq.forEach(field => $(field + '-btn')?.classList.toggle('active', activeTool === 'level' && activeField === field));
    $('tool-line').classList.toggle('active', activeTool === 'line');
    $('tool-fib').classList.toggle('active', activeTool === 'fib');
    $('tool-half').classList.toggle('active', activeTool === 'half');
    $('ichimoku-toggle').classList.toggle('active', !!levels.__show_ichimoku__);
    $('ichimoku-toggle').textContent = `Ichimoku: ${{levels.__show_ichimoku__ ? 'ON' : 'OFF'}}`;
    $('values-panel').textContent = seq.map(k => `${{labels[k]}}: ${{levels[k] == null ? '--' : fmt(levels[k])}}`).join('\\n');
    const picker = $('object-picker'); picker.innerHTML = '<option value="">-- select --</option>';
    const seenFib = new Set();
    drawnObjects.forEach((obj, idx) => {{
      if (obj.type === 'fib' && obj.group_id) {{ if (seenFib.has(obj.group_id)) return; seenFib.add(obj.group_id); picker.add(new Option(`FIB group (${{String(obj.group_id).slice(0,8)}})`, `fib-group:${{obj.group_id}}`)); return; }}
      picker.add(new Option(`${{obj.label || 'OBJ'}} (${{String(obj.id || idx).slice(0,8)}})`, obj.id || `obj-index:${{idx}}`));
    }});
  }}

  function applyInstrumentControls() {{
    const stockCfdOn = !!levels.__stock_cfd_mode__;
    const originalIsStock = P.instrumentType === 'stock' || stockCfdOn;
    const disabled = originalIsStock && !stockCfdOn;
    const sourceUpper = String(P.sourceTicker || '').toUpperCase();
    const symbolUpper = String(P.symbol || '').toUpperCase();
    const indexLike = P.instrumentType === 'commodity' && ['^','DE40','US500','US100','US30','JP225','WIG20','UK100','EU50','DAX','CAC','AEX','SMI','IBEX'].some(t => sourceUpper.includes(t) || symbolUpper.includes(t));
    $('identity').textContent = `Name/Ticker: ${{P.sourceName || P.symbol}}${{P.sourceTicker ? ` (${{P.sourceTicker}})` : ''}}`;
    $('instrument-title').textContent = `Instrument: ${{originalIsStock && stockCfdOn ? 'STOCK CFD' : (indexLike ? 'COMMODITY/INDEX' : P.instrumentType.toUpperCase())}}`;
    $('source').textContent = `SOURCE: ${{P.sourceProvider}}`;
    $('stock-cfd-toggle').style.display = originalIsStock ? 'block' : 'none';
    $('stock-cfd-toggle').textContent = `CFD mode: ${{stockCfdOn ? 'ON' : 'OFF'}}`;
    $('stock-cfd-toggle').classList.toggle('active', stockCfdOn);
    const setFieldState = (id, isDisabled, visible=true) => {{
      const el = $(id), label = $(`${{id}}-label`);
      if (!el) return;
      el.disabled = !!isDisabled;
      el.style.display = visible ? 'block' : 'none';
      if (label) {{ label.style.display = visible ? 'block' : 'none'; label.style.opacity = isDisabled ? 0.55 : 1; }}
    }};
    // Three explicit sidebar states:
    // 1) plain stock: sizing inputs disabled;
    // 2) commodity/forex/index: all sizing inputs enabled;
    // 3) stock CFD-as-commodity: commodity inputs enabled, pip value fixed/hidden.
    setFieldState('position-type', disabled, !disabled);
    setFieldState('lot-cost', disabled, !disabled);
    setFieldState('spread-mult', disabled, !disabled);
    setFieldState('pip-value', disabled || stockCfdOn, !disabled && !stockCfdOn);
    $('spread-mult-label').textContent = stockCfdOn ? 'Spread (price units; pips = spread / 0.01)' : 'Spread multiplier (spread = Multiplier * pip_value)';
    $('currency-fee-toggle').style.display = levels.__currency_fee_eligible__ ? 'block' : 'none';
    $('currency-fee-toggle').textContent = `FX conversion fee 1%: ${{levels.apply_currency_conversion_fee ? 'ON' : 'OFF'}}`;
    $('currency-fee-toggle').classList.toggle('active', !!levels.apply_currency_conversion_fee);
  }}

  seq.forEach(field => {{ const b = document.createElement('button'); b.id = field + '-btn'; b.textContent = labels[field]; b.onclick = () => {{ safeRemoveSeries(previewSeries); previewSeries=null; activeTool='level'; activeField=field; lineAnchor=fibAnchor=halfAnchor=null; updatePanel(); }}; $('level-buttons').appendChild(b); }});
  $('position-type').value = levels.position_type || 'long'; $('capital').value = levels.capital || 255000;
  $('lot-cost').value = levels.lot_cost && levels.lot_cost !== 0 ? levels.lot_cost : ''; $('pip-value').value = levels.__stock_cfd_mode__ ? 1 : ((levels.pip_value && levels.pip_value !== 0) ? levels.pip_value : '');
  $('spread-mult').value = levels.spread_multiplier && levels.spread_multiplier !== 0 ? levels.spread_multiplier : '';
  $('tool-line').onclick = () => {{ safeRemoveSeries(previewSeries); previewSeries=null; activeTool='line'; activeField=null; fibAnchor=halfAnchor=null; updatePanel(); }};
  $('tool-fib').onclick = () => {{ safeRemoveSeries(previewSeries); previewSeries=null; activeTool='fib'; activeField=null; lineAnchor=halfAnchor=null; updatePanel(); }};
  $('tool-half').onclick = () => {{ safeRemoveSeries(previewSeries); previewSeries=null; activeTool='half'; activeField=null; lineAnchor=fibAnchor=null; updatePanel(); }};
  document.querySelectorAll('.color-dot').forEach(b => b.onclick = () => lineColor = b.dataset.color);
  $('ichimoku-toggle').onclick = () => {{ levels.__show_ichimoku__ = !levels.__show_ichimoku__; render(); }};
  $('reset-all').onclick = () => {{ levels = {{}}; levelPoints = {{}}; drawnObjects = []; lineAnchor=fibAnchor=halfAnchor=null; activeTool='level'; activeField='high'; render(); applyInstrumentControls(); }};
  $('stock-cfd-toggle').onclick = () => {{ levels.__stock_cfd_mode__ = !levels.__stock_cfd_mode__; if (levels.__stock_cfd_mode__) $('pip-value').value = 1; applyInstrumentControls(); }};
  $('currency-fee-toggle').onclick = () => {{ levels.apply_currency_conversion_fee = !levels.apply_currency_conversion_fee; applyInstrumentControls(); }};
  $('delete-object').onclick = () => {{ const id = $('object-picker').value; if (!id) return; if (id.startsWith('fib-group:')) {{ const gid = id.split(':')[1]; drawnObjects = drawnObjects.filter(o => o.group_id !== gid); }} else if (id.startsWith('obj-index:')) {{ const idx = Number(id.split(':')[1]); drawnObjects = drawnObjects.filter((_, i) => i !== idx); }} else drawnObjects = drawnObjects.filter(o => o.id !== id); render(); }};

  chart.subscribeClick(param => {{
    if (!param || !param.point) return;
    const price = roundPrice(candleSeries.coordinateToPrice(param.point.y));
    const time = typeof param.time === 'string' ? param.time : (param.time ? `${{param.time.year}}-${{String(param.time.month).padStart(2,'0')}}-${{String(param.time.day).padStart(2,'0')}}` : nearest(null).time);
    if (!Number.isFinite(price)) return;
    if (activeTool === 'line') {{ if (!lineAnchor) {{ lineAnchor = {{x:time, y:price}}; updateLinePreview(addDays(time, 1), price); }} else {{ drawnObjects.push({{id:crypto.randomUUID(), type:'line', label:'LINE', x0:lineAnchor.x, y0:lineAnchor.y, x1:time, y1:price, color:lineColor}}); lineAnchor=null; safeRemoveSeries(previewSeries); previewSeries=null; render(); }} updatePanel(); return; }}
    if (activeTool === 'fib') {{
      const row = nearest(time); const mid = (row.low + row.high) / 2;
      if (!fibAnchor) {{ fibAnchor = {{x:row.time, mid}}; updatePanel(); return; }}
      const row1 = nearest(fibAnchor.x), row2 = nearest(time); const firstMid = fibAnchor.mid, secondMid = (row2.low + row2.high)/2; const isShort = secondMid < firstMid;
      const low = isShort ? row2.low : row1.low, high = isShort ? row1.high : row2.high; const delta = high - low; const gid = crypto.randomUUID();
      const xStart = row1.time, xSecond = row2.time; const xEnd = addDays(P.ohlc[P.ohlc.length-1].time, Math.max(720, Math.abs(row2.idx-row1.idx)*14));
      [1,0,.236,.382,.618].forEach((r, idx) => {{ const y = roundPrice(isShort ? low + delta*r : high - delta*r); const pct = `${{(r*100).toFixed(1)}}%`.replace('.0%','%'); drawnObjects.push({{id:crypto.randomUUID(), type:'fib', label:`FIB ${{pct}} (${{fmt(y)}})`, x0:idx===0?xStart:xSecond, x1:xEnd, y0:y, y1:y, price:y, color:fibColor(r), group_id:gid, direction:isShort?'short':'long'}}); }});
      fibAnchor=null; render(); return;
    }}
    if (activeTool === 'half') {{ if (!halfAnchor) {{ levels.__half_points__ = [{{date:time, price}}]; halfAnchor = {{x:time, y:price}}; render(); return; }} const midpoint = roundPrice((halfAnchor.y + price)/2); levels.stop_loss = midpoint; levelPoints.stop_loss = {{price:midpoint, plot_price:midpoint, date:time}}; levels.__half_points__ = [{{date:halfAnchor.x, price:halfAnchor.y}}, {{date:time, price}}]; halfAnchor=null; render(); return; }}
    if (activeTool === 'level' && activeField) {{ const row = nearest(time); let selected = price, plot = price; if (activeField === 'high' || activeField === 'low') {{ selected = roundPrice(activeField === 'high' ? row.high : row.low); plot = selected; }} levels[activeField] = selected; levelPoints[activeField] = {{price:selected, plot_price:plot, date:row.time}}; if (activeField === 'stop_loss') levels.__half_points__ = []; render(); }}
  }});

  chart.subscribeCrosshairMove(param => {{
    if (!param || !param.point) return;
    const cursor = candleSeries.coordinateToPrice(param.point.y);
    const time = typeof param.time === 'string' ? param.time : (param.time ? `${{param.time.year}}-${{String(param.time.month).padStart(2,'0')}}-${{String(param.time.day).padStart(2,'0')}}` : null);
    const row = nearest(time); let day = null; if (row.idx > 0) {{ const prev = P.ohlc[row.idx-1].close; if (prev) day = ((row.close-prev)/prev)*100; }}
    const dayText = day == null ? '--' : (day>=0?'+':'') + day.toFixed(2)+'%';
    const dayColor = day == null ? '#e5e7eb' : (day >= 0 ? '#22c55e' : '#ef4444');
    $('cursor-box').innerHTML = `D:${{row.time}}  O:${{fmt(row.open)}}  H:${{fmt(row.high)}}  L:${{fmt(row.low)}}  C:${{fmt(row.close)}}  <span style="color:${{dayColor}};font-weight:900">DAY:${{dayText}}</span>  CURSOR:${{Number.isFinite(cursor) ? fmt(cursor) : '--'}}`;
    if (activeTool === 'line' && lineAnchor && Number.isFinite(cursor)) updateLinePreview(time, cursor);
  }});

  $('finish-btn').onclick = async () => {{
    const stockCfdMode = !!levels.__stock_cfd_mode__;
    const pipValue = stockCfdMode ? 1 : Number($('pip-value').value || 0);
    const spreadMult = Number($('spread-mult').value || 0);
    levels = {{...levels, position_type:$('position-type').value, capital:roundPrice(Number($('capital').value || 255000)), lot_cost:roundPrice(Number($('lot-cost').value || 0)), pip_value:Number(pipValue.toFixed(4)), spread_multiplier:Number(spreadMult.toFixed(4)), spread:Number((stockCfdMode ? spreadMult : spreadMult*pipValue).toFixed(4)), spread_pips: stockCfdMode ? Number((spreadMult/0.01).toFixed(2)) : null, drawn_objects:drawnObjects, level_points:levelPoints, __finished__:true}};
    let screenshot = null; try {{ screenshot = chart.takeScreenshot(true, false).toDataURL('image/png'); }} catch(e) {{}}
    const resp = await fetch('/finish', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{levels, screenshot}})}});
    if (resp.ok) {{ $('result-box').textContent = 'Saved. Closing app...'; setTimeout(() => {{ fetch('/shutdown', {{method:'POST', keepalive:true}}); try {{ window.close(); }} catch(e) {{}} }}, 250); }}
  }};

  setInterval(() => fetch('/heartbeat', {{method:'POST', keepalive:true}}).catch(()=>{{}}), 1000);
  window.addEventListener('beforeunload', () => navigator.sendBeacon('/shutdown'));
  applyWedgeDerivedLevels(); applyInstrumentControls(); render();
}})();
  </script>
</body>
</html>"""

    def run(self):
        app = Flask(__name__)
        server_holder: dict[str, object] = {}
        heartbeat = {"ts": time.time()}

        class QuietRequestHandler(WSGIRequestHandler):
            def log(self, type, message, *args):  # noqa: A003
                return

        @app.route("/")
        def _index():
            return self._html()

        @app.route("/finish", methods=["POST"])
        def _finish():
            payload = request.get_json(silent=True) or {}
            levels = payload.get("levels") or {}
            self._snapshot_data_url = payload.get("screenshot")
            self.values = levels
            self._finished = bool(levels.get("__finished__"))
            return jsonify({"ok": True})

        @app.route("/shutdown", methods=["GET", "POST"])
        def _shutdown_app():
            shutdown = request.environ.get("werkzeug.server.shutdown")
            if shutdown:
                shutdown()
            elif server_holder.get("server") is not None:
                threading.Timer(0.1, lambda: server_holder["server"].shutdown()).start()
            return "ok"

        @app.route("/heartbeat", methods=["POST"])
        def _heartbeat():
            heartbeat["ts"] = time.time()
            return "ok"

        threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{self.server_port}/")).start()
        server = make_server("127.0.0.1", self.server_port, app, threaded=True, request_handler=QuietRequestHandler)
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
        if self._snapshot_data_url and self._snapshot_data_url.startswith("data:image/png;base64,"):
            encoded = self._snapshot_data_url.split(",", 1)[1]
            file_path.write_bytes(base64.b64decode(encoded))
            return
        # Fallback: write a tiny valid PNG so the save pipeline remains atomic
        # even if a browser blocks canvas capture.
        file_path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
            )
        )
