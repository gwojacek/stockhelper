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

    def _html(self) -> str:
        payload = json.dumps(self._payload(), ensure_ascii=False)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>StockHelper Lightweight Chart - {self.symbol}</title>
  <script src="https://unpkg.com/lightweight-charts@5.0.8/dist/lightweight-charts.standalone.production.js"></script>
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
    #chart {{ height: calc(100vh - 132px); min-height: 480px; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden; }}
    #cursor-box {{ margin-bottom: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 16px; font-weight: 700; text-align: center; }}
    .side {{ border-left: 1px solid #1f2937; padding: 16px; background: #0b1220; overflow-y: auto; }}
    label {{ display: block; margin-top: 8px; }}
    input, select {{ width: 100%; color: black; background: white; font-size: 16px; padding: 6px 8px; border-radius: 4px; border: 1px solid #cbd5e1; }}
    .muted {{ opacity: .5; }}
    .source {{ margin-bottom: 12px; font-weight: 700; color: #93c5fd; font-size: 16px; }}
    .values {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin-bottom: 8px; white-space: pre-wrap; }}
    .color-dot {{ width: 22px; height: 22px; padding: 0; border: 1px solid white; }}
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
      <div id="chart"></div>
    </main>
    <aside class="side">
      <div style="margin-bottom:8px;font-weight:800;font-size:20px;color:#f8fafc" id="identity"></div>
      <h4 id="instrument-title" style="margin-top:0;margin-bottom:6px;color:#cbd5e1"></h4>
      <button id="stock-cfd-toggle" style="width:100%;margin-bottom:8px;display:none"></button>
      <div class="source" id="source"></div>
      <h4>Selected values</h4>
      <div id="values-panel" class="values"></div>
      <button id="clear-active-level" style="width:100%;margin-bottom:14px">Clear active value</button>
      <h4>Manual inputs</h4>
      <label id="position-type-label">Position type</label>
      <select id="position-type"><option value="long">LONG</option><option value="short">SHORT</option></select>
      <label>Capital</label><input id="capital" type="number" />
      <button id="currency-fee-toggle" style="margin-top:8px;width:100%;display:none"></button>
      <label id="lot-cost-label">Lot cost</label><input id="lot-cost" type="number" />
      <label id="pip-value-label">Pip value</label><input id="pip-value" type="number" />
      <label id="spread-mult-label">Spread multiplier (spread = Multiplier * pip_value)</label><input id="spread-mult" type="number" />
      <h4 style="margin-top:14px">Drawn objects</h4>
      <select id="object-picker"><option value="">-- select --</option></select>
      <button id="delete-object" style="margin-top:8px;width:100%">Delete selected object</button>
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
  const candleSeries = addCandles({{ upColor:'#22c55e', downColor:'#ef4444', borderUpColor:'#22c55e', borderDownColor:'#ef4444', wickUpColor:'#22c55e', wickDownColor:'#ef4444' }});
  candleSeries.setData(P.ohlc);
  chart.timeScale().fitContent();
  const dynamicSeries = [];
  const removeDynamic = () => {{ while(dynamicSeries.length) chart.removeSeries(dynamicSeries.pop()); }};
  const addLine = (data, color, width=1.4, style=LightweightCharts.LineStyle.Solid, title='') => {{
    if (!data || data.length === 0) return null;
    const s = addLineSeries({{ color, lineWidth: width, lineStyle: style, priceLineVisible: false, lastValueVisible: false, title }});
    s.setData(data.filter(p => p && p.time && Number.isFinite(Number(p.value))).map(p => ({{time:p.time, value:Number(p.value)}})));
    dynamicSeries.push(s);
    return s;
  }};

  function render() {{
    removeDynamic();
    if (levels.__show_ichimoku__) {{
      addLine(P.ichimoku.tenkan, '#ef4444', 1, LightweightCharts.LineStyle.Solid, 'Tenkan-sen');
      addLine(P.ichimoku.kijun, '#3b82f6', 2, LightweightCharts.LineStyle.Solid, 'Kijun-sen');
      addLine(P.ichimoku.spanA, '#22c55e', 1, LightweightCharts.LineStyle.Solid, 'Senkou Span A');
      addLine(P.ichimoku.spanB, '#ef4444', 1, LightweightCharts.LineStyle.Solid, 'Senkou Span B');
      addLine(P.ichimoku.chikou, 'rgba(250,204,21,.8)', 1, LightweightCharts.LineStyle.Dotted, 'Chikou Span');
    }}
    const levelColors = {{high:'#d946ef', low:'#14b8a6', entry:'#22c55e', stop_loss:'#ef4444', check_zr_value_fibo_or_elevation:'#f59e0b', line_cross_value:'#3b82f6'}};
    seq.forEach(field => {{
      const pt = levelPoints[field]; if (!pt) return;
      const base = nearest(pt.date); const x0 = dateAtIndex(base.idx - 5); const x1 = dateAtIndex(base.idx + 5);
      addLine([{{time:x0, value:pt.plot_price ?? pt.price}}, {{time:x1, value:pt.plot_price ?? pt.price}}], levelColors[field] || '#94a3b8', 3, LightweightCharts.LineStyle.Solid, `${{labels[field]}}: ${{fmt(pt.price)}}`);
      if (field === 'entry') addLine([{{time:pt.date, value:pt.price}}], levelColors[field], 3, LightweightCharts.LineStyle.Solid, 'ENTRY point');
    }});
    (levels.__half_points__ || []).forEach(pt => addLine([{{time:pt.date, value:pt.price}}], '#a855f7', 2, LightweightCharts.LineStyle.Solid, 'Half point'));
    drawnObjects.forEach(obj => {{
      const color = obj.color || P.lineColors.gold;
      if (Array.isArray(obj.x) && Array.isArray(obj.y)) {{
        addLine(obj.x.map((x, i) => ({{time:String(x).slice(0,10), value:Number(obj.y[i])}})), color, obj.type === 'wedge' ? 3 : 2, LightweightCharts.LineStyle.Solid, obj.label || 'OBJECT');
        if (Array.isArray(obj.anchor_x) && Array.isArray(obj.anchor_y)) obj.anchor_x.forEach((x, i) => addLine([{{time:String(x).slice(0,10), value:Number(obj.anchor_y[i])}}], color, 3, LightweightCharts.LineStyle.Solid, `${{obj.label || 'OBJECT'}} anchor`));
      }} else {{
        addLine([{{time:String(obj.x0).slice(0,10), value:Number(obj.y0)}}, {{time:String(obj.x1).slice(0,10), value:Number(obj.y1)}}], color, obj.type === 'fib' && String(obj.label || '').includes('61.8%') ? 3 : 2, LightweightCharts.LineStyle.Solid, obj.label || 'OBJECT');
      }}
    }});
    updatePanel();
  }}

  function updatePanel() {{
    seq.forEach(field => $(field + '-btn')?.classList.toggle('active', activeTool === 'level' && activeField === field));
    $('tool-line').classList.toggle('active', activeTool === 'line');
    $('tool-fib').classList.toggle('active', activeTool === 'fib');
    $('tool-half').classList.toggle('active', activeTool === 'half');
    $('ichimoku-toggle').classList.toggle('active', !!levels.__show_ichimoku__);
    $('ichimoku-toggle').textContent = `Ichimoku: ${{levels.__show_ichimoku__ ? 'ON' : 'OFF'}}`;
    $('values-panel').textContent = seq.map(k => `${{labels[k]}}: ${{levels[k] == null ? '--' : fmt(levels[k])}}`).join('\n');
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
    ['position-type','lot-cost','spread-mult'].forEach(id => $(id).disabled = disabled);
    $('pip-value').disabled = disabled || stockCfdOn;
    $('pip-value').style.display = stockCfdOn ? 'none' : 'block';
    $('pip-value-label').style.display = stockCfdOn ? 'none' : 'block';
    $('spread-mult-label').textContent = stockCfdOn ? 'Spread (price units; pips = spread / 0.01)' : 'Spread multiplier (spread = Multiplier * pip_value)';
    $('currency-fee-toggle').style.display = levels.__currency_fee_eligible__ ? 'block' : 'none';
    $('currency-fee-toggle').textContent = `FX conversion fee 1%: ${{levels.apply_currency_conversion_fee ? 'ON' : 'OFF'}}`;
    $('currency-fee-toggle').classList.toggle('active', !!levels.apply_currency_conversion_fee);
  }}

  seq.forEach(field => {{ const b = document.createElement('button'); b.id = field + '-btn'; b.textContent = labels[field]; b.onclick = () => {{ activeTool='level'; activeField=field; lineAnchor=fibAnchor=halfAnchor=null; updatePanel(); }}; $('level-buttons').appendChild(b); }});
  $('position-type').value = levels.position_type || 'long'; $('capital').value = levels.capital || 255000;
  $('lot-cost').value = levels.lot_cost && levels.lot_cost !== 0 ? levels.lot_cost : ''; $('pip-value').value = levels.__stock_cfd_mode__ ? 1 : ((levels.pip_value && levels.pip_value !== 0) ? levels.pip_value : '');
  $('spread-mult').value = levels.spread_multiplier && levels.spread_multiplier !== 0 ? levels.spread_multiplier : '';
  $('tool-line').onclick = () => {{ activeTool='line'; activeField=null; fibAnchor=halfAnchor=null; updatePanel(); }};
  $('tool-fib').onclick = () => {{ activeTool='fib'; activeField=null; lineAnchor=halfAnchor=null; updatePanel(); }};
  $('tool-half').onclick = () => {{ activeTool='half'; activeField=null; lineAnchor=fibAnchor=null; updatePanel(); }};
  document.querySelectorAll('.color-dot').forEach(b => b.onclick = () => lineColor = b.dataset.color);
  $('ichimoku-toggle').onclick = () => {{ levels.__show_ichimoku__ = !levels.__show_ichimoku__; render(); }};
  $('reset-all').onclick = () => {{ levels = {{}}; levelPoints = {{}}; drawnObjects = []; lineAnchor=fibAnchor=halfAnchor=null; activeTool='level'; activeField='high'; render(); applyInstrumentControls(); }};
  $('clear-active-level').onclick = () => {{ if (activeTool === 'level' && activeField) {{ delete levels[activeField]; delete levelPoints[activeField]; if (activeField === 'stop_loss') levels.__half_points__ = []; render(); }} }};
  $('stock-cfd-toggle').onclick = () => {{ levels.__stock_cfd_mode__ = !levels.__stock_cfd_mode__; if (levels.__stock_cfd_mode__) $('pip-value').value = 1; applyInstrumentControls(); }};
  $('currency-fee-toggle').onclick = () => {{ levels.apply_currency_conversion_fee = !levels.apply_currency_conversion_fee; applyInstrumentControls(); }};
  $('delete-object').onclick = () => {{ const id = $('object-picker').value; if (!id) return; if (id.startsWith('fib-group:')) {{ const gid = id.split(':')[1]; drawnObjects = drawnObjects.filter(o => o.group_id !== gid); }} else if (id.startsWith('obj-index:')) {{ const idx = Number(id.split(':')[1]); drawnObjects = drawnObjects.filter((_, i) => i !== idx); }} else drawnObjects = drawnObjects.filter(o => o.id !== id); render(); }};

  chart.subscribeClick(param => {{
    if (!param || !param.point) return;
    const price = roundPrice(candleSeries.coordinateToPrice(param.point.y));
    const time = typeof param.time === 'string' ? param.time : (param.time ? `${{param.time.year}}-${{String(param.time.month).padStart(2,'0')}}-${{String(param.time.day).padStart(2,'0')}}` : nearest(null).time);
    if (!Number.isFinite(price)) return;
    if (activeTool === 'line') {{ if (!lineAnchor) {{ lineAnchor = {{x:time, y:price}}; }} else {{ drawnObjects.push({{id:crypto.randomUUID(), type:'line', label:'LINE', x0:lineAnchor.x, y0:lineAnchor.y, x1:time, y1:price, color:lineColor}}); lineAnchor=null; render(); }} updatePanel(); return; }}
    if (activeTool === 'fib') {{
      const row = nearest(time); const mid = (row.low + row.high) / 2;
      if (!fibAnchor) {{ fibAnchor = {{x:row.time, mid}}; updatePanel(); return; }}
      const row1 = nearest(fibAnchor.x), row2 = nearest(time); const firstMid = fibAnchor.mid, secondMid = (row2.low + row2.high)/2; const isShort = secondMid < firstMid;
      const low = isShort ? row2.low : row1.low, high = isShort ? row1.high : row2.high; const delta = high - low; const gid = crypto.randomUUID();
      const xStart = row1.time, xSecond = dateAtIndex(row2.idx - 2); const xEnd = addDays(P.ohlc[P.ohlc.length-1].time, Math.max(21, Math.abs(row2.idx-row1.idx)*3));
      [1,0,.236,.382,.618].forEach((r, idx) => {{ const y = roundPrice(isShort ? low + delta*r : high - delta*r); const pct = `${{(r*100).toFixed(1)}}%`.replace('.0%','%'); drawnObjects.push({{id:crypto.randomUUID(), type:'fib', label:`FIB ${{pct}} (${{fmt(y)}})`, x0:idx===0?xStart:xSecond, x1:xEnd, y0:y, y1:y, price:y, color:r===.618?'#22c55e':lineColor, group_id:gid, direction:isShort?'short':'long'}}); }});
      fibAnchor=null; render(); return;
    }}
    if (activeTool === 'half') {{ if (!halfAnchor) {{ levels.__half_points__ = [{{date:time, price}}]; halfAnchor = {{x:time, y:price}}; render(); return; }} const midpoint = roundPrice((halfAnchor.y + price)/2); levels.stop_loss = midpoint; levelPoints.stop_loss = {{price:midpoint, plot_price:midpoint, date:time}}; levels.__half_points__ = [{{date:halfAnchor.x, price:halfAnchor.y}}, {{date:time, price}}]; halfAnchor=null; render(); return; }}
    if (activeTool === 'level' && activeField) {{ const row = nearest(time); let selected = price, plot = price; if (activeField === 'high' || activeField === 'low') {{ selected = roundPrice(activeField === 'high' ? row.high : row.low); const tick = Math.pow(10, -(Math.abs(selected) < 1 ? 4 : precision)); const span = Math.abs(row.high - row.low); const offset = Math.max(span*.12, tick*8, Math.abs(selected)*.002); plot = roundPrice(activeField === 'high' ? selected + offset : selected - offset); }} levels[activeField] = selected; levelPoints[activeField] = {{price:selected, plot_price:plot, date:row.time}}; if (activeField === 'stop_loss') levels.__half_points__ = []; render(); }}
  }});

  chart.subscribeCrosshairMove(param => {{
    if (!param || !param.point) return;
    const cursor = candleSeries.coordinateToPrice(param.point.y);
    const time = typeof param.time === 'string' ? param.time : (param.time ? `${{param.time.year}}-${{String(param.time.month).padStart(2,'0')}}-${{String(param.time.day).padStart(2,'0')}}` : null);
    const row = nearest(time); let day = null; if (row.idx > 0) {{ const prev = P.ohlc[row.idx-1].close; if (prev) day = ((row.close-prev)/prev)*100; }}
    $('cursor-box').textContent = `D:${{row.time}}  O:${{fmt(row.open)}}  H:${{fmt(row.high)}}  L:${{fmt(row.low)}}  C:${{fmt(row.close)}}  DAY:${{day == null ? '--' : (day>=0?'+':'') + day.toFixed(2)+'%'}}  CURSOR:${{Number.isFinite(cursor) ? fmt(cursor) : '--'}}`;
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
  applyInstrumentControls(); render();
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
