from __future__ import annotations

from pathlib import Path
import base64
import os
import json
import socket
import threading
import time
import webbrowser
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request

from core.calculator import calculate_position_size, calculate_stock_position
from core.risk_manager import calculate_distance_ratio, calculate_take_profit
from chart_program.config_writer import DEFAULT_RISK_LEVELS
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


    def _future_time_payload(self, periods: int = 120) -> list[str]:
        dates = pd.to_datetime(self.df["Date"], errors="coerce")
        if dates.empty or pd.isna(dates.iloc[-1]):
            return []
        builder = pd.date_range if self._has_weekend_data() else pd.bdate_range
        future_dates = builder(dates.iloc[-1] + pd.Timedelta(days=1), periods=periods)
        return [pd.to_datetime(d).strftime("%Y-%m-%d") for d in future_dates]

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

    def _chart_group_payload(self) -> dict | None:
        raw = os.environ.get("STOCKHELPER_CHART_GROUP_JSON", "")
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except Exception:
            return None
        items = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command") or "").strip()
            if not command:
                continue
            label = str(item.get("label") or command).strip()
            section = str(item.get("section") or "").strip()
            items.append({"command": command, "label": label, "section": section})
        if not items:
            return None
        return {
            "id": str(payload.get("id") or ""),
            "label": str(payload.get("label") or "Quick charts from group btn"),
            "items": items,
            "current": str(payload.get("current") or ""),
            "reportServer": str(payload.get("reportServer") or ""),
        }

    def _payload(self) -> dict:
        return {
            "symbol": self.symbol,
            "instrumentType": self.instrument_type,
            "sourceTicker": self.source_ticker,
            "sourceName": self.source_name,
            "sourceProvider": self.source_provider,
            "reportLaunched": os.environ.get("STOCKHELPER_REPORT_LAUNCHED_CHART") == "1",
            "pricePrecision": self._precision_for_price(),
            "basePrecision": self.price_precision,
            "selectionSequence": SELECTION_SEQUENCE,
            "labels": LABELS,
            "lineColors": LINE_COLORS,
            "values": self._json_safe(self.values),
            "ohlc": self._ohlc_payload(),
            "futureTimes": self._future_time_payload(),
            "ichimoku": self._ichimoku_payload(),
            "chartGroup": self._chart_group_payload(),
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
        const state = {series: [], candleSeries: null, clickHandlers: [], moveHandlers: [], yMin: 0, yMax: 1, width: 1, height: 1, dpr: 1, scaleMargins: options?.rightPriceScale?.scaleMargins || {top:0.08,bottom:0.12}};
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
            if (s.kind === 'candlestick' && Number.isFinite(Number(p.close))) out.push(p.open, p.high, p.low, p.close);
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
          const top = Math.max(18, state.height * (state.scaleMargins?.top ?? 0.08));
          const bottom = Math.max(28, state.height * (state.scaleMargins?.bottom ?? 0.12));
          const plotH = Math.max(1, state.height - top - bottom);
          const span = state.yMax - state.yMin || 1;
          return top + ((state.yMax - price) / span) * plotH;
        }
        function yToPrice(y) {
          const top = Math.max(18, state.height * (state.scaleMargins?.top ?? 0.08));
          const bottom = Math.max(28, state.height * (state.scaleMargins?.bottom ?? 0.12));
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
          const data = candleData();
          if (data.length) {
            const axisY = state.height - 22;
            ctx.beginPath(); ctx.moveTo(54, axisY); ctx.lineTo(state.width - 70, axisY); ctx.stroke();
            const steps = Math.min(5, data.length);
            for (let i = 0; i < steps; i++) {
              const idx = steps === 1 ? 0 : Math.round((i / (steps - 1)) * (data.length - 1));
              const x = xForIndex(idx);
              const label = String(data[idx]?.time || '').slice(5, 10);
              ctx.fillText(label, x - 14, axisY + 14);
            }
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
            if (!Number.isFinite(Number(p.close))) return;
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
          applyOptions(opts) { if (opts?.rightPriceScale?.scaleMargins) state.scaleMargins = opts.rightPriceScale.scaleMargins; draw(); },
          priceScale() { return {applyOptions(opts) { if (opts?.scaleMargins) state.scaleMargins = opts.scaleMargins; draw(); }}; },
          addSeries(type, opts) { return makeSeries(type === CandlestickSeries ? 'candlestick' : 'line', opts); },
          addCandlestickSeries(opts) { return makeSeries('candlestick', opts); },
          addLineSeries(opts) { return makeSeries('line', opts); },
          removeSeries(series) { state.series = state.series.filter(s => s !== series); if (state.candleSeries === series) state.candleSeries = null; draw(); },
          timeScale() { return {fitContent(){ draw(); }, setVisibleLogicalRange(){}, getVisibleLogicalRange(){ return null; }, timeToCoordinate(time){ return xForIndex(indexForTime(typeof time === 'string' ? time : String(time || '').slice(0, 10))); }, coordinateToTime(x){ const data=candleData(); if(!data.length) return null; const left=54, plotW=Math.max(1,state.width-124); const idx=Math.max(0,Math.min(data.length-1,Math.round(((x-left)/plotW)*Math.max(0,data.length-1)))); return data[idx]?.time || null; }, subscribeVisibleLogicalRangeChange(){}}; },
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
    .main {{ padding: 14px 0 14px 14px; min-width: 0; }}
    h3 {{ margin: 0 0 10px 0; }}
    button {{ background: #1f2937; color: #e5e7eb; border: 1px solid #334155; border-radius: 6px; padding: 8px; cursor: pointer; font-weight: 700; }}
    button.active {{ background: #2563eb; border-color: #2563eb; color: white; }}
    .level-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }}
    .toolbar {{ display: flex; gap: 8px; margin-bottom: 10px; align-items: center; }}
    .wedge-mini-btn {{ display:none; min-width:32px; padding:8px 6px; }}
    #chart-wrap {{ position: relative; height: calc(100vh - 230px); min-height: 360px; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden; }}
    #chart {{ position:absolute; inset:0; width: 100%; height: 100%; z-index:1; }}
    #cloud-overlay {{ position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 30; }}
    #icon-overlay {{ position:absolute; inset:0; pointer-events:none; z-index:60; overflow:hidden; }}
    .chart-icon {{ position:absolute; transform:translate(-50%,-50%); min-width:15px; height:15px; padding:0 3px; border-radius:999px; display:flex; align-items:center; justify-content:center; font-size:10px; line-height:1; font-weight:900; color:#0f172a; background:#f8fafc; border:2px solid currentColor; box-shadow:0 2px 8px rgba(0,0,0,.55); }}
    .chart-icon.anchor {{ color:#f8fafc; background:#111827; border-color:#f8fafc; text-shadow:0 1px 2px #000; }}
    .chart-icon.touch {{ color:#0f172a; background:#fbbf24; border-color:#0f172a; width:10px; min-width:10px; height:10px; padding:0; }}
    .chart-icon.cross {{ color:#f8fafc; background:#a855f7; border-color:#f8fafc; }}
    .chart-icon.end {{ color:#0f172a; background:#f8fafc; }}
    #chart-wrap.drawing-object {{ cursor: grabbing; }}
    #chart-wrap.line-handle-hover {{ cursor: pointer; }}
    #cursor-box {{ margin-bottom: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 16px; font-weight: 700; text-align: center; }}
    .side {{ border-left: 1px solid #1f2937; padding: 16px; background: #0b1220; overflow-y: auto; }}
    label {{ display: block; margin-top: 8px; }}
    input, select {{ width: 100%; color: black; background: white; font-size: 16px; padding: 6px 8px; border-radius: 4px; border: 1px solid #cbd5e1; }}
    input:disabled, select:disabled {{ opacity: 0.38; background: #475569; color: #cbd5e1; border-color: #334155; cursor: not-allowed; }}
    .muted {{ opacity: .5; }}
    .source {{ margin-bottom: 12px; font-weight: 700; color: #93c5fd; font-size: 16px; }}
    .chart-group-nav {{ display:none; margin-top:8px; padding:10px; border:1px solid #334155; border-radius:8px; background:#111827; }}
    .chart-group-nav h4 {{ margin:0 0 8px 0; color:#fde68a; font-size:15px; }}
    .chart-group-label {{ margin:0 0 8px 0; color:#bfdbfe; font-weight:800; font-size:13px; }}
    .chart-group-section {{ margin-top:8px; }}
    .chart-group-section-title {{ color:#cbd5e1; font-size:12px; font-weight:800; margin:5px 0; }}
    .chart-group-buttons {{ display:flex; flex-wrap:wrap; gap:6px; }}
    .chart-group-buttons button {{ padding:6px 8px; border-radius:999px; background:#1f2937; border-color:#475569; color:#e5e7eb; font-size:12px; }}
    .chart-group-buttons button.active {{ background:#2563eb; border-color:#93c5fd; color:white; box-shadow:0 0 0 2px rgba(147,197,253,.22); }}
    .values {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin-bottom: 8px; white-space: pre-wrap; }}
    .color-dot {{ width: 22px; height: 22px; padding: 0; border: 1px solid white; }}
    #chart-legend {{ display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; min-height: 20px; margin: 0 0 7px 0; font-size: 12px; font-weight: 700; }}
    #chart-legend span {{ display: inline-flex; align-items: center; gap: 5px; cursor: pointer; user-select: none; }}
    #chart-legend span.hidden {{ opacity: 0.38; text-decoration: line-through; }}
    #chart-legend button {{ padding: 0 5px; line-height: 16px; font-size: 11px; border-radius: 4px; background: #334155; color: #e5e7eb; }}
    .fib-label-contrast {{ color: #f8fafc; text-shadow: 0 1px 2px rgba(0,0,0,.65); }}
    #chart-legend i {{ width: 18px; height: 3px; display: inline-block; border-radius: 2px; }}
    .main.calc-open #chart-wrap {{ height: calc(100vh - 210px - var(--calc-drawer-height, 340px)); min-height: 180px; cursor: grab; }}
    .main.calc-open #chart-wrap.dragging {{ cursor: grabbing; }}
    #calc-drawer {{ display:none; position:relative; margin-top:8px; max-height:46vh; overflow:auto; background:rgba(15,23,42,.97); border:1px solid #334155; border-radius:12px; box-shadow:0 18px 50px rgba(0,0,0,.45); padding:10px 12px; }}
    #calc-drawer.open {{ display:block; }}
    #calc-head {{ display:grid; grid-template-columns:minmax(120px,1fr) minmax(760px,980px) minmax(80px,1fr); align-items:start; gap:12px; margin:0 0 4px 0; }}
    #calc-title {{ position:absolute; left:12px; top:50%; transform:translateY(-50%); width:max(120px, calc((100% - 980px) / 2 - 24px)); margin:0; text-align:center; font-size:18px; }}
    #calc-close {{ grid-column:3; justify-self:end; }}
    #calc-table {{ max-width: 980px; margin: 0 auto; }}
    #calc-drawer table {{ width:auto; min-width:760px; max-width:980px; border-collapse:collapse; font-size:13px; }}
    #calc-drawer th, #calc-drawer td {{ border:1px solid #334155; padding:4px 7px; text-align:right; white-space:nowrap; }}
    #calc-drawer th:first-child, #calc-drawer td:first-child {{ text-align:left; }}
    #calc-drawer th {{ background:#1e293b; color:#bfdbfe; position:sticky; top:0; }}
    #calc-summary {{ grid-column:2; display:flex; flex-wrap:wrap; justify-content:flex-start; gap:5px 12px; margin:0 auto 3px auto; width:100%; max-width:980px; color:#cbd5e1; font-size:13px; }}
    #calc-summary b {{ color:#f8fafc; }}
    #calc-warnings {{ margin-top:6px; color:#facc15; font-size:12px; }}
    #wedge-debug-panel {{ display:none; margin-top:10px; padding:10px; border:1px solid #334155; border-radius:10px; background:#0f172a; color:#dbeafe; font-size:12px; line-height:1.35; max-height:42vh; overflow:auto; white-space:pre-wrap; }}
    #wedge-debug-panel.open {{ display:block; }}
    #wedge-debug-panel h4 {{ margin:0 0 6px 0; color:#f8fafc; }}
    #wedge-debug-panel .muted {{ color:#94a3b8; }}
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
        <button id="reset-scanner-drawings" style="display:none" title="Restore the original scanner-created drawings and remove manual drawing changes">Reset scanner</button>
        <button id="find-new-wedge" style="display:none" title="Search for a larger valid alternative around the current wedge">🎲 Find new wedge</button>
        <button id="find-new-upper-wedge" class="wedge-mini-btn" title="Find a new upper wedge line">↑</button>
        <button id="find-new-lower-wedge" class="wedge-mini-btn" title="Find a new lower wedge line">↓</button>
        <span>Line color:</span>
        <button class="color-dot" data-color="#facc15" style="background:#facc15"></button>
        <button class="color-dot" data-color="#a855f7" style="background:#a855f7"></button>
        <button class="color-dot" data-color="#22c55e" style="background:#22c55e"></button>
      </div>
      <div id="cursor-box">D:---- -- -- O:-- H:-- L:-- C:-- DAY:-- CURSOR:--</div>
      <div id="chart-legend"></div>
      <div id="chart-wrap"><div id="chart"></div><canvas id="cloud-overlay"></canvas><div id="icon-overlay"></div></div>
      <section id="calc-drawer" aria-live="polite">
        <div id="calc-head">
          <h3 id="calc-title">Position calculation</h3>
          <div id="calc-summary"></div>
          <button id="calc-close" type="button">Close</button>
        </div>
        <div id="calc-table"></div>
        <div id="calc-warnings"></div>
      </section>
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
      <button id="calculate-btn" style="margin-top:16px;width:100%;padding:10px;background:#16a34a;color:white;border:none;border-radius:8px">Calculate position</button>
      <button id="wedge-debug-btn" style="margin-top:8px;width:100%;padding:10px;background:#7c3aed;color:white;border:none;border-radius:8px">Copy wedge debug</button>
      <div id="wedge-debug-panel"></div>
      <button id="finish-btn" style="margin-top:8px;width:100%;padding:10px;background:#2563eb;color:white;border:none;border-radius:8px">Save &amp; Close</button>
      <div id="chart-group-nav" class="chart-group-nav">
        <h4>⭐ Quick charts from 📊</h4>
        <div id="chart-group-label" class="chart-group-label"></div>
        <div id="chart-group-buttons" class="chart-group-buttons"></div>
      </div>
      <div id="result-box" style="margin-top:10px"></div>
    </aside>
  </div>
  <script>window.STOCKHELPER_PAYLOAD = {payload};</script>
  <script>
(() => {{
  const P = window.STOCKHELPER_PAYLOAD;
  const chartGroup = P.chartGroup || null;
  const seq = P.selectionSequence;
  const labels = P.labels;
  let levels = {{...(P.values || {{}})}};
  let levelPoints = {{...(levels.level_points || {{}})}};
  const deepClone = (value) => JSON.parse(JSON.stringify(value));
  const isScannerDrawnObject = (obj) => !!obj && (obj.group_id === 'auto-wedge' || obj.type === 'wedge' || obj.scanner === true || obj.source === 'scanner');
  let drawnObjects = Array.isArray(levels.drawn_objects) ? deepClone(levels.drawn_objects) : [];
  const initialScannerDrawnObjects = drawnObjects.filter(isScannerDrawnObject).map(deepClone);
  let activeField = null;
  let activeTool = 'level';
  let wedgeRouletteNoAlternative = false;
  let lineAnchor = null;
  let fibAnchor = null;
  let halfAnchor = null;
  let lineColor = P.lineColors.gold;
  const precision = P.pricePrecision || 2;
  const futureTimes = Array.isArray(P.futureTimes) ? P.futureTimes : [];
  const ohlc = Array.isArray(P.ohlc) ? P.ohlc : [];
  const ohlcWithFuture = [...ohlc, ...futureTimes.map(time => ({{time}}))];
  const ohlcByTime = new Map(ohlc.map((r, idx) => [r.time, {{...r, idx}}]));

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
  const fibRatios = [0, 0.382, 0.5, 0.618, 1];
  const fibGoldenColor = '#facc15';
  const fibHighlightColor = '#22c55e';
  const fibLineColor = fibGoldenColor;
  const fibColor = (ratio) => Math.abs(Number(ratio) - 0.618) < 0.0001 ? fibHighlightColor : fibGoldenColor;
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
    rightPriceScale: {{ borderColor: '#334155', minimumWidth: 78, entireTextOnly: true, scaleMargins: {{top:0.08, bottom:0.12}} }},
    timeScale: {{ visible: true, timeVisible: true, secondsVisible: false, borderColor: '#334155', rightOffset: 18, tickMarkFormatter: (time) => {{
      const d = typeof time === 'string' ? new Date(time + 'T00:00:00Z') : new Date(Date.UTC(time.year, time.month - 1, time.day));
      return d.getUTCMonth() === 0 ? String(d.getUTCFullYear()) : d.toLocaleString('en-US', {{month:'short', timeZone:'UTC'}});
    }} }},
    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
    localization: {{ priceFormatter: p => fmt(p) }},
  }});
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  let verticalPan = 0;
  let chartDrag = null;
  let lineObjectDrag = null;
  let lineDragFrame = null;
  const objectSeries = new WeakMap();
  let suppressChartClickUntil = 0;
  function restoreChartInteractions() {{
    try {{
      chart.applyOptions?.({{
        handleScroll: {{ mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true }},
        handleScale: {{ axisPressedMouseMove: true, mouseWheel: true, pinch: true }},
      }});
    }} catch(e) {{}}
  }}
  function applyVerticalPan() {{
    verticalPan = clamp(verticalPan, -0.30, 0.30);
    const margins = {{top:clamp(0.08 + verticalPan, 0.01, 0.50), bottom:clamp(0.12 - verticalPan, 0.01, 0.50)}};
    try {{ chart.priceScale?.('right')?.applyOptions({{scaleMargins:margins}}); }} catch(e) {{}}
    try {{ chart.applyOptions?.({{rightPriceScale:{{scaleMargins:margins}}}}); }} catch(e) {{}}
    requestAnimationFrame(drawCloud);
  }}
  $('chart-wrap').addEventListener('pointerdown', (ev) => {{
    if (ev.button === 0 && beginLineObjectDrag(ev)) return;
    if (!$('calc-drawer')?.classList.contains('open') || ev.button !== 0) return;
    chartDrag = {{id:ev.pointerId, y:ev.clientY, moved:false}};
    $('chart-wrap').classList.add('dragging');
    $('chart-wrap').setPointerCapture?.(ev.pointerId);
  }}, true);
  $('chart-wrap').addEventListener('pointermove', (ev) => {{
    if (moveLineObjectDrag(ev)) return;
    updateLineObjectHover(ev);
    if (!chartDrag || chartDrag.id !== ev.pointerId || !$('calc-drawer')?.classList.contains('open')) return;
    const dy = ev.clientY - chartDrag.y;
    if (Math.abs(dy) < 2) return;
    chartDrag.moved = chartDrag.moved || Math.abs(dy) > 4;
    if (chartDrag.moved) {{
      ev.preventDefault();
      verticalPan += dy / Math.max(260, $('chart-wrap').getBoundingClientRect().height);
      chartDrag.y = ev.clientY;
      applyVerticalPan();
    }}
  }}, true);
  const endChartDrag = (ev) => {{
    if (endLineObjectDrag(ev)) return;
    if (!chartDrag || chartDrag.id !== ev.pointerId) return;
    if (chartDrag.moved) suppressChartClickUntil = Date.now() + 300;
    $('chart-wrap').releasePointerCapture?.(ev.pointerId);
    $('chart-wrap').classList.remove('dragging');
    chartDrag = null;
  }};
  $('chart-wrap').addEventListener('pointerup', endChartDrag, true);
  $('chart-wrap').addEventListener('pointercancel', endChartDrag, true);
  window.addEventListener('pointerup', endChartDrag, true);
  window.addEventListener('pointercancel', endChartDrag, true);
  $('chart-wrap').addEventListener('click', (ev) => {{ if (Date.now() < suppressChartClickUntil) {{ ev.preventDefault(); ev.stopImmediatePropagation(); }} }}, true);
  const addLineSeries = (opts) => chart.addSeries ? chart.addSeries(LightweightCharts.LineSeries, opts) : chart.addLineSeries(opts);
  const addCandles = (opts) => chart.addSeries ? chart.addSeries(LightweightCharts.CandlestickSeries, opts) : chart.addCandlestickSeries(opts);
  const candleSeries = addCandles({{ upColor:'#f8fafc', downColor:'#22d3ee', borderUpColor:'#22d3ee', borderDownColor:'#0891b2', wickUpColor:'#22d3ee', wickDownColor:'#0891b2' }});
  candleSeries.setData(ohlcWithFuture);
  if (typeof candleSeries.applyOptions === 'function') candleSeries.applyOptions({{priceLineColor:'#f8fafc', priceLineWidth:1, priceLineStyle:LightweightCharts.LineStyle.Dotted}});
  chart.timeScale().fitContent();
  requestAnimationFrame(() => {{
    try {{
      const ts = chart.timeScale();
      if (ts.setVisibleLogicalRange && ohlc.length) ts.setVisibleLogicalRange({{from: 0, to: Math.max(ohlc.length - 1, 0) + 18}});
    }} catch(e) {{}}
    requestAnimationFrame(drawCloud);
  }});
  if (chart.timeScale().subscribeVisibleLogicalRangeChange) chart.timeScale().subscribeVisibleLogicalRangeChange(() => requestAnimationFrame(drawCloud));
  window.addEventListener('resize', () => requestAnimationFrame(drawCloud));
  const dynamicSeries = [];
  const levelSeries = new Map();
  let previewSeries = null;
  let fibPreviewSeries = [];
  let previewFrame = null;
  let fibPreviewFrame = null;
  let pendingPreview = null;
  let pendingFibPreviewTime = null;
  const hiddenLegendKeys = new Set();
  let suppressViewportCapture = false;
  const safeRemoveSeries = (series) => {{ try {{ if (series) chart.removeSeries(series); }} catch(e) {{ console.warn('removeSeries failed', e); }} }};
  const clearPreviews = () => {{ safeRemoveSeries(previewSeries); previewSeries = null; while(fibPreviewSeries.length) safeRemoveSeries(fibPreviewSeries.pop()); if (previewFrame) cancelAnimationFrame(previewFrame); if (fibPreviewFrame) cancelAnimationFrame(fibPreviewFrame); previewFrame = null; fibPreviewFrame = null; pendingPreview = null; pendingFibPreviewTime = null; }};
  const removeDynamic = () => {{ while(dynamicSeries.length) safeRemoveSeries(dynamicSeries.pop()); levelSeries.clear(); clearPreviews(); }};
  const addLine = (data, color, width=1.4, style=LightweightCharts.LineStyle.Solid, title='', legend=true, pointMarkers=false, rightLabel=false, legendKey=null, onDelete=null, autoscale=true) => {{
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
    if (!autoscale) options.autoscaleInfoProvider = () => null;
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


  function fibStartDate(row1, row2, ratio) {{
    const startIdx = Math.round(row1.idx + (row2.idx - row1.idx) * (1 - ratio));
    return dateAtIndex(startIdx);
  }}

  function fibPrice(low, high, ratio, isShort) {{
    const delta = high - low;
    return roundPrice(isShort ? low + delta * ratio : high - delta * ratio);
  }}

  function updateLinePreview(time, value) {{
    if (!lineAnchor || !Number.isFinite(value)) return;
    pendingPreview = {{time, value}};
    if (previewFrame) return;
    previewFrame = requestAnimationFrame(() => {{
      previewFrame = null;
      const pt = pendingPreview;
      pendingPreview = null;
      if (!pt || !lineAnchor) return;
      if (!previewSeries) previewSeries = addLineSeries({{color:'#94a3b8', lineWidth:1.2, lineStyle:LightweightCharts.LineStyle.Dotted, priceLineVisible:false, lastValueVisible:false, title:'', autoscaleInfoProvider:() => null}});
      try {{
        previewSeries.setData(normalizeLineData([{{time:lineAnchor.x, value:lineAnchor.y}}, {{time:pt.time, value:pt.value}}]));
        if (typeof previewSeries.applyOptions === 'function') previewSeries.applyOptions({{priceLineVisible:false,lastValueVisible:false,title:''}});
      }} catch(e) {{ console.warn('line preview failed', e); }}
    }});
  }}

  function drawFibPreview(time) {{
    if (!fibAnchor) return;
    const row1 = nearest(fibAnchor.x), row2 = nearest(time);
    if (!row1 || !row2 || row1.time === row2.time) return;
    const firstMid = fibAnchor.mid, secondMid = (row2.low + row2.high) / 2;
    const isShort = secondMid < firstMid;
    const low = isShort ? row2.low : row1.low, high = isShort ? row1.high : row2.high;
    if (!Number.isFinite(low) || !Number.isFinite(high) || high <= low) return;
    const xEnd = addDays(P.ohlc[P.ohlc.length-1].time, Math.max(2880, Math.abs(row2.idx-row1.idx)*24));
    const needed = fibRatios.length + 1;
    while (fibPreviewSeries.length < needed) {{
      fibPreviewSeries.push(addLineSeries({{color:'#94a3b8', lineWidth:1, lineStyle:LightweightCharts.LineStyle.Dotted, priceLineVisible:false, lastValueVisible:false, title:''}}));
    }}
    fibRatios.forEach((r, idx) => {{
      const y = fibPrice(low, high, r, isShort);
      const x0 = fibStartDate(row1, row2, r);
      const pct = `${{(r*100).toFixed(1)}}%`.replace('.0%','%');
      const opts = {{color:fibColor(r), lineWidth:r === 0.618 ? 1.4 : 1.0, lineStyle:LightweightCharts.LineStyle.Solid, priceLineVisible:false, lastValueVisible:true, title:pct}};
      try {{ fibPreviewSeries[idx].setData(normalizeLineData([{{time:x0, value:y}}, {{time:xEnd, value:y}}])); fibPreviewSeries[idx].applyOptions?.(opts); }} catch(e) {{ console.warn('fib preview failed', e); }}
    }});
    const boundary = fibPreviewSeries[fibRatios.length];
    const yA = fibPrice(low, high, 1, isShort), yB = fibPrice(low, high, 0, isShort);
    try {{ boundary.setData(normalizeLineData([{{time:row1.time, value:yA}}, {{time:row2.time, value:yB}}])); boundary.applyOptions?.({{color:fibLineColor, lineWidth:1, lineStyle:LightweightCharts.LineStyle.Dotted, priceLineVisible:false, lastValueVisible:false, title:''}}); }} catch(e) {{ console.warn('fib boundary preview failed', e); }}
  }}

  function updateFibPreview(time) {{
    if (!fibAnchor || !time) return;
    pendingFibPreviewTime = time;
    if (fibPreviewFrame) return;
    fibPreviewFrame = requestAnimationFrame(() => {{
      fibPreviewFrame = null;
      const nextTime = pendingFibPreviewTime;
      pendingFibPreviewTime = null;
      drawFibPreview(nextTime);
    }});
  }}

  function cloudPairs() {{
    const map = new Map();
    (P.ichimoku.spanA || []).forEach(p => map.set(p.time, {{time:p.time, a:Number(p.value)}}));
    (P.ichimoku.spanB || []).forEach(p => {{ const row = map.get(p.time) || {{time:p.time}}; row.b = Number(p.value); map.set(p.time, row); }});
    return [...map.values()].filter(p => p.time && Number.isFinite(p.a) && Number.isFinite(p.b)).sort((x, y) => compareTime(x.time, y.time));
  }}

  function wedgeSide(obj) {{
    const label = String(obj?.label || '').toLowerCase();
    if (label.includes('upper')) return 'upper';
    if (label.includes('lower')) return 'lower';
    return '';
  }}

  function candleExtremeForDate(date, side, fallback) {{
    const row = ohlcByTime.get(String(date).slice(0, 10));
    if (!row) return Number(fallback);
    if (side === 'upper') return roundPrice(row.high);
    if (side === 'lower') return roundPrice(row.low);
    return Number(fallback);
  }}

  function wedgeTouchPoints(obj) {{
    const side = wedgeSide(obj);
    const isUpper = side === 'upper';
    const isLower = side === 'lower';
    const endpoint = lineDisplayValues(obj);
    const realCandles = ohlc.filter(c => c && c.time && Number.isFinite(Number(c.high)) && Number.isFinite(Number(c.low)));
    const byTimeIndex = new Map(realCandles.map((c, idx) => [String(c.time).slice(0, 10), idx]));
    const fallbackAnchors = (Array.isArray(obj.anchor_x) ? obj.anchor_x : []).map((x, i) => {{
      const time = String(x).slice(0, 10);
      const raw = Number((obj.anchor_y || [])[i]);
      const value = candleExtremeForDate(time, side, raw);
      return {{time, value, anchor:true, computed_anchor:false, upper:isUpper, lower:isLower, idx: byTimeIndex.get(time) ?? ohlc.findIndex(c => c.time === time)}};
    }}).filter(p => p.time && Number.isFinite(p.value));
    if (!side || !endpoint) return fallbackAnchors;
    const e0 = nearest(endpoint.x0);
    const e1 = nearest(endpoint.x1);
    const idx0 = Number(e0?.idx);
    const idx1 = Number(e1?.idx);
    if (!Number.isFinite(idx0) || !Number.isFinite(idx1) || idx0 === idx1) return fallbackAnchors;
    const touchCandidates = [];
    const start = Math.min(idx0, idx1);
    const end = realCandles.length - 1;
    const avgRangeRows = realCandles.slice(Math.max(0, end - 29), end + 1)
      .map(c => Number(c.high) - Number(c.low))
      .filter(Number.isFinite);
    const avgRange = avgRangeRows.length ? avgRangeRows.reduce((a, b) => a + b, 0) / avgRangeRows.length : 0;
    for (let idx = start; idx <= end; idx += 1) {{
      const c = realCandles[idx];
      const time = String(c.time).slice(0, 10);
      const extreme = side === 'upper' ? Number(c.high) : Number(c.low);
      if (!Number.isFinite(extreme)) continue;
      const lineValue = lineValueForDate(obj, time);
      if (!Number.isFinite(lineValue)) continue;
      const closeTolerance = Math.max(Math.abs(lineValue) * 0.0005, avgRange * 0.08, Math.abs(lineValue) < 1 ? 0.0005 : 0.005);
      const touchTolerance = Math.max(Math.abs(lineValue) * 0.00025, Math.abs(lineValue) < 1 ? 0.00025 : 0.0025);
      const close = Number(c.close);
      const breakoutClose = side === 'upper' ? close > lineValue + closeTolerance : close < lineValue - closeTolerance;
      if (breakoutClose) break;
      // Preserve the scanner's touch definition: the relevant wick must reach
      // or pierce the trendline and the candle must close back inside.  Do not
      // count body-only intersections or candles that remain under/over the
      // line without the wick actually reaching it.
      const touched = side === 'upper'
        ? Number(c.high) >= lineValue - touchTolerance && close <= lineValue + closeTolerance
        : Number(c.low) <= lineValue + touchTolerance && close >= lineValue - closeTolerance;
      if (touched) {{
        const localLeft = Math.max(0, idx - 1);
        const localRight = Math.min(realCandles.length - 1, idx + 1);
        const localRows = realCandles.slice(localLeft, localRight + 1);
        const localExtreme = side === 'upper'
          ? Number(c.high) >= Math.max(...localRows.map(r => Number(r.high)))
          : Number(c.low) <= Math.min(...localRows.map(r => Number(r.low)));
        touchCandidates.push({{time, value: roundPrice(extreme), line_value:roundPrice(lineValue), anchor:false, computed_anchor:false, upper:isUpper, lower:isLower, idx, local_extreme:localExtreme}});
      }}
    }}
    let lastIdx = null;
    const points = [];
    touchCandidates.forEach(pt => {{
      if (lastIdx !== null && pt.idx - lastIdx <= 1) return;
      points.push(pt);
      lastIdx = pt.idx;
    }});
    const firstAnchor = points.find(pt => pt.local_extreme) || points[0];
    const secondAnchor = firstAnchor ? (points.find(pt => pt !== firstAnchor && pt.idx - firstAnchor.idx > 1 && pt.local_extreme) || points.find(pt => pt !== firstAnchor && pt.idx - firstAnchor.idx > 1)) : null;
    [firstAnchor, secondAnchor].filter(Boolean).forEach(pt => {{ pt.anchor = true; pt.computed_anchor = true; }});
    return points.sort((a, b) => (a.idx ?? 0) - (b.idx ?? 0));
  }}

  function wedgeDebugSnapshot() {{
    const wedges = drawnObjects.filter(obj => obj.type === 'wedge' || obj.group_id === 'auto-wedge');
    const upper = wedges.find(obj => wedgeSide(obj) === 'upper') || null;
    const lower = wedges.find(obj => wedgeSide(obj) === 'lower') || null;
    const realCandles = ohlc.filter(c => c && c.time && Number.isFinite(Number(c.open)) && Number.isFinite(Number(c.high)) && Number.isFinite(Number(c.low)) && Number.isFinite(Number(c.close)));
    const lines = [];
    lines.push(`WEDGE DEBUG: ${{P.symbol || ''}}`);
    lines.push(`Generated: ${{new Date().toISOString()}}`);
    if (!wedges.length) {{
      lines.push('No wedge lines on chart.');
      return lines.join('\\n');
    }}
    const touchMap = new Map();
    wedges.forEach(obj => {{
      const side = wedgeSide(obj) || 'line';
      const touches = wedgeTouchPoints(obj);
      touchMap.set(obj, touches);
      const anchors = touches.filter(pt => pt.anchor);
      lines.push('');
      lines.push(`${{String(obj.label || 'Wedge line')}} [${{side}}]`);
      lines.push(`  anchors: ${{anchors.map(pt => `${{pt.time}} @ ${{fmt(pt.value)}}${{pt.computed_anchor ? ' (auto)' : ''}}`).join(' | ') || '-'}}`);
      lines.push(`  touches: ${{touches.length}}`);
      touches.forEach((pt, i) => {{
        lines.push(`    ${{String(i + 1).padStart(2, '0')}}. ${{pt.time}} @ ${{fmt(pt.value)}}${{pt.line_value != null ? ` line=${{fmt(pt.line_value)}}` : ''}}${{pt.anchor ? (pt.computed_anchor ? ' (auto anchor)' : ' (anchor)') : ''}}`);
      }});
    }});

    const upperTouches = upper ? (touchMap.get(upper) || wedgeTouchPoints(upper)) : [];
    const lowerTouches = lower ? (touchMap.get(lower) || wedgeTouchPoints(lower)) : [];
    const activeBreakoutIdx = Math.max(
      ...[...upperTouches, ...lowerTouches]
        .filter(pt => pt.anchor)
        .map(pt => Number(pt.idx))
        .filter(Number.isFinite)
    );
    const oldestIdx = Math.min(
      ...[...upperTouches, ...lowerTouches]
        .map(pt => Number(pt.idx))
        .filter(Number.isFinite)
    );
    let breakout = null;
    realCandles.forEach((row, idx) => {{
      if (breakout || (Number.isFinite(activeBreakoutIdx) && idx <= activeBreakoutIdx)) return;
      const up = upper ? lineValueForDate(upper, row.time) : null;
      const lo = lower ? lineValueForDate(lower, row.time) : null;
      if (Number.isFinite(up) && Number(row.close) > up) breakout = {{time:row.time, direction:'long', line:'upper', value:roundPrice(up), close:roundPrice(row.close)}};
      if (!breakout && Number.isFinite(lo) && Number(row.close) < lo) breakout = {{time:row.time, direction:'short', line:'lower', value:roundPrice(lo), close:roundPrice(row.close)}};
    }});
    lines.push('');
    lines.push(`Breakout: ${{breakout ? `${{breakout.time}} ${{breakout.direction}} via ${{breakout.line}} line @ ${{fmt(breakout.value)}} (close ${{fmt(breakout.close)}})` : '-'}}`);
    lines.push('');
    const upperTouchDates = new Set(upperTouches.map(pt => pt.time));
    const lowerTouchDates = new Set(lowerTouches.map(pt => pt.time));
    const touchedDates = new Set([...upperTouchDates, ...lowerTouchDates]);
    lines.push('Touched candles only:');
    lines.push('Date,Open,High,Low,Close,UpperLine,LowerLine,Inside,TouchSide');
    realCandles.filter(row => touchedDates.has(row.time)).forEach(row => {{
      const up = upper ? lineValueForDate(upper, row.time) : null;
      const lo = lower ? lineValueForDate(lower, row.time) : null;
      const insideUpper = !Number.isFinite(up) || Number(row.close) <= up;
      const insideLower = !Number.isFinite(lo) || Number(row.close) >= lo;
      const touchSide = [
        upperTouchDates.has(row.time) ? 'upper' : '',
        lowerTouchDates.has(row.time) ? 'lower' : '',
      ].filter(Boolean).join('+');
      lines.push([
        row.time,
        fmt(row.open),
        fmt(row.high),
        fmt(row.low),
        fmt(row.close),
        Number.isFinite(up) ? fmt(up) : '',
        Number.isFinite(lo) ? fmt(lo) : '',
        insideUpper && insideLower ? 'yes' : 'no',
        touchSide,
      ].join(','));
    }});
    return lines.join('\\n');
  }}

  function updateWedgeDebugPanel(message = '') {{
    const panel = $('wedge-debug-panel');
    if (!panel || !panel.classList.contains('open')) return;
    const text = wedgeDebugSnapshot();
    panel.textContent = message ? `${{message}}\\n\\n${{text}}` : text;
  }}

  async function copyWedgeDebug() {{
    const panel = $('wedge-debug-panel');
    const text = wedgeDebugSnapshot();
    if (panel) {{
      panel.classList.add('open');
      panel.textContent = text;
    }}
    try {{
      await navigator.clipboard.writeText(text);
      updateWedgeDebugPanel('Copied wedge debug to clipboard.');
    }} catch (err) {{
      updateWedgeDebugPanel('Clipboard copy failed. Select and copy the debug text below.');
    }}
  }}

  function drawWedgeTouchPoints(ctx) {{
    drawnObjects.filter(obj => obj.type === 'wedge' || obj.group_id === 'auto-wedge').forEach(obj => {{
      const points = wedgeTouchPoints(obj);
      const anchorFill = obj.color || (String(obj.label || '').toLowerCase().includes('upper') ? '#dc2626' : '#2563eb');
      points.forEach(pt => {{
        const x = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(pt.time) : null;
        const y = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(pt.value) : null;
        if (x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) return;
        if (pt.anchor) {{
          ctx.save();
          ctx.translate(x, y);
          ctx.beginPath();
          ctx.arc(0, 0, 6.2, 0, Math.PI * 2);
          ctx.shadowColor = 'rgba(0,0,0,.55)';
          ctx.shadowBlur = 3;
          ctx.fillStyle = 'rgba(15,23,42,.35)';
          ctx.strokeStyle = '#f8fafc';
          ctx.lineWidth = 1.6;
          ctx.stroke();
          ctx.shadowBlur = 0;
          ctx.beginPath();
          ctx.arc(0, 0, 2.4, 0, Math.PI * 2);
          ctx.fillStyle = '#a855f7';
          ctx.fill();
          ctx.restore();
          return;
        }}
        ctx.beginPath();
        ctx.arc(x, y, 3.6, 0, Math.PI * 2);
        ctx.shadowColor = 'rgba(0,0,0,.55)';
        ctx.shadowBlur = 4;
        ctx.fillStyle = '#fbbf24';
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 1.1;
        ctx.fill();
        ctx.stroke();
        ctx.shadowBlur = 0;
      }});
    }});
  }}

  function drawLineObjectHandles(ctx) {{
    drawnObjects.forEach(obj => {{
      if (!isEditableLineObject(obj) || hiddenLegendKeys.has(editableObjectLegendKey(obj))) return;
      const pts = lineObjectPoints(obj);
      if (!pts) return;
      [pts.start, pts.end].forEach((pt, idx) => {{
        if (!Number.isFinite(pt.x) || !Number.isFinite(pt.y)) return;
        ctx.save();
        ctx.translate(pt.x, pt.y);
        ctx.beginPath();
        ctx.moveTo(0, -7);
        ctx.lineTo(7, 0);
        ctx.lineTo(0, 7);
        ctx.lineTo(-7, 0);
        ctx.closePath();
        ctx.shadowColor = 'rgba(0,0,0,.55)';
        ctx.shadowBlur = 5;
        ctx.fillStyle = '#f8fafc';
        ctx.strokeStyle = obj.color || P.lineColors.gold;
        ctx.lineWidth = 2.4;
        ctx.fill();
        ctx.stroke();
        ctx.shadowBlur = 0;
        ctx.beginPath();
        if (idx === 0) {{
          ctx.moveTo(-4, 0);
          ctx.lineTo(4, 0);
          ctx.moveTo(0, -4);
          ctx.lineTo(0, 4);
        }} else {{
          ctx.moveTo(-4, -4);
          ctx.lineTo(3, 0);
          ctx.lineTo(-4, 4);
          ctx.moveTo(3, 0);
          ctx.lineTo(-6, 0);
        }}
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 1.4;
        ctx.stroke();
        ctx.restore();
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
      if (pt.auto_wedge) {{
        ctx.beginPath();
        ctx.arc(x, y, 4.2, 0, Math.PI * 2);
        ctx.fillStyle = '#a855f7';
        ctx.strokeStyle = '#f8fafc';
        ctx.lineWidth = 1.4;
        ctx.fill();
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x - 2.8, y - 2.8);
        ctx.lineTo(x + 2.8, y + 2.8);
        ctx.moveTo(x + 2.8, y - 2.8);
        ctx.lineTo(x - 2.8, y + 2.8);
        ctx.strokeStyle = '#f8fafc';
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.restore();
        return;
      }}
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

  function addDomChartIcon(x, y, cls, text, color=null) {{
    const layer = $('icon-overlay');
    if (!layer || x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) return;
    const pad = 12;
    const maxX = Math.max(pad, (layer.clientWidth || 0) - pad);
    const maxY = Math.max(pad, (layer.clientHeight || 0) - pad);
    x = clamp(Number(x), pad, maxX);
    y = clamp(Number(y), pad, maxY);
    const icon = document.createElement('span');
    icon.className = `chart-icon ${{cls || ''}}`;
    icon.textContent = text;
    icon.style.left = `${{x}}px`;
    icon.style.top = `${{y}}px`;
    if (color) icon.style.borderColor = color;
    layer.appendChild(icon);
  }}

  function drawDomChartIcons() {{
    const layer = $('icon-overlay');
    if (!layer) return;
    layer.innerHTML = '';
    drawnObjects.filter(obj => obj.type === 'wedge' || obj.group_id === 'auto-wedge').forEach(obj => {{
      wedgeTouchPoints(obj).forEach(pt => {{
        const x = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(pt.time) : null;
        const y = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(pt.value) : null;
        addDomChartIcon(x, y, pt.anchor ? 'anchor' : 'touch', pt.anchor ? '◆' : '', obj.color || null);
      }});
    }});
    drawnObjects.forEach(obj => {{
      if (!isEditableLineObject(obj) || hiddenLegendKeys.has(editableObjectLegendKey(obj))) return;
      const pts = lineObjectPoints(obj);
      if (!pts) return;
      addDomChartIcon(pts.start.x, pts.start.y, 'anchor', '+', obj.color || null);
      addDomChartIcon(pts.end.x, pts.end.y, 'end', '▶', obj.color || null);
    }});
    const cross = levelPoints.line_cross_value;
    if (cross && !hiddenLegendKeys.has('level:line_cross_value')) {{
      const x = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(cross.date) : null;
      const y = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(cross.price ?? cross.plot_price) : null;
      addDomChartIcon(x, y, 'cross', '×');
    }}
  }}

  function pointDateFromEvent(ev) {{
    const rect = $('chart-wrap').getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const ts = chart.timeScale();
    const raw = ts.coordinateToTime ? ts.coordinateToTime(x) : null;
    if (typeof raw === 'string') return raw.slice(0, 10);
    if (raw && Number.isFinite(raw.year)) return `${{raw.year}}-${{String(raw.month).padStart(2,'0')}}-${{String(raw.day).padStart(2,'0')}}`;
    return nearest(null).time;
  }}

  function pointPriceFromEvent(ev) {{
    const rect = $('chart-wrap').getBoundingClientRect();
    return roundPrice(candleSeries.coordinateToPrice(ev.clientY - rect.top));
  }}

  function dateShiftDays(date, days) {{
    return addDays(String(date).slice(0, 10), days);
  }}

  function dayDelta(a, b) {{
    const ta = new Date(String(a).slice(0, 10) + 'T00:00:00Z').getTime();
    const tb = new Date(String(b).slice(0, 10) + 'T00:00:00Z').getTime();
    if (!Number.isFinite(ta) || !Number.isFinite(tb)) return 0;
    return Math.round((tb - ta) / 86400000);
  }}

  function isWedgeLineObject(obj) {{
    return obj && (obj.type === 'wedge' || obj.group_id === 'auto-wedge');
  }}

  function lineEndpointValues(obj) {{
    if (!obj) return null;
    const xs = Array.isArray(obj.anchor_x) && obj.anchor_x.length >= 2 ? obj.anchor_x : (Array.isArray(obj.x) && obj.x.length >= 2 ? obj.x : null);
    const ys = Array.isArray(obj.anchor_y) && obj.anchor_y.length >= 2 ? obj.anchor_y : (Array.isArray(obj.y) && obj.y.length >= 2 ? obj.y : null);
    if (xs && ys) {{
      const last = Math.min(xs.length, ys.length) - 1;
      const x0 = String(xs[0]).slice(0, 10), x1 = String(xs[last]).slice(0, 10);
      const y0 = Number(ys[0]), y1 = Number(ys[last]);
      return x0 && x1 && Number.isFinite(y0) && Number.isFinite(y1) ? {{x0, y0, x1, y1}} : null;
    }}
    const x0 = String(obj.x0 || '').slice(0, 10), x1 = String(obj.x1 || '').slice(0, 10);
    const y0 = Number(obj.y0), y1 = Number(obj.y1);
    return x0 && x1 && Number.isFinite(y0) && Number.isFinite(y1) ? {{x0, y0, x1, y1}} : null;
  }}

  function lineDisplayValues(obj) {{
    if (!obj) return null;
    if (isWedgeLineObject(obj)) {{
      const anchors = lineEndpointValues(obj);
      const xs = Array.isArray(obj.x) && obj.x.length >= 2 ? obj.x : null;
      const ys = Array.isArray(obj.y) && obj.y.length >= 2 ? obj.y : null;
      if (anchors && xs && ys) {{
        const last = Math.min(xs.length, ys.length) - 1;
        const x1 = String(xs[last]).slice(0, 10);
        const y1 = Number(ys[last]);
        if (x1 && Number.isFinite(y1)) return {{x0:anchors.x0, y0:anchors.y0, x1, y1}};
      }}
      if (anchors) return anchors;
    }}
    return lineEndpointValues(obj);
  }}

  function isEditableLineObject(obj) {{
    if (!obj || obj.type === 'fib' || obj.type === 'fib-boundary') return false;
    return obj.type === 'line' || isWedgeLineObject(obj);
  }}

  function editableObjectLegendKey(obj) {{
    if (isWedgeLineObject(obj)) return `wedge:${{obj.id || obj.label || ''}}`;
    return `obj:${{obj.id || obj.label || ''}}`;
  }}

  function dateRatio(x0, x1, x) {{
    const t0 = new Date(String(x0).slice(0, 10) + 'T00:00:00Z').getTime();
    const t1 = new Date(String(x1).slice(0, 10) + 'T00:00:00Z').getTime();
    const t = new Date(String(x).slice(0, 10) + 'T00:00:00Z').getTime();
    if (!Number.isFinite(t0) || !Number.isFinite(t1) || !Number.isFinite(t) || t1 === t0) return 0;
    return (t - t0) / (t1 - t0);
  }}

  function projectedLineValue(x0, y0, x1, y1, x) {{
    return Number(y0) + (Number(y1) - Number(y0)) * dateRatio(x0, x1, x);
  }}

  function setLineEndpointValues(obj, x0, y0, x1, y1, mode='both') {{
    x0 = String(x0).slice(0, 10);
    x1 = String(x1).slice(0, 10);
    y0 = roundPrice(Number(y0));
    y1 = roundPrice(Number(y1));
    if (isWedgeLineObject(obj)) {{
      const side = wedgeSide(obj);
      const anchorsX = Array.isArray(obj.anchor_x) ? obj.anchor_x.map(x => String(x).slice(0, 10)) : [];
      const anchorsY = Array.isArray(obj.anchor_y) ? obj.anchor_y.map(Number) : [];
      if (mode === 'start') {{
        x0 = nearest(x0).time;
        if (compareTime(x0, x1) >= 0) x0 = dateAtIndex(Math.max(0, nearest(x1).idx - 1));
        y0 = candleExtremeForDate(x0, side, y0);
        if (anchorsX[1] && Number.isFinite(anchorsY[1])) y1 = roundPrice(projectedLineValue(x0, y0, anchorsX[1], anchorsY[1], x1));
        obj.anchor_x = [x0, anchorsX[1] || x1];
        obj.anchor_y = [y0, Number.isFinite(anchorsY[1]) ? anchorsY[1] : candleExtremeForDate(x1, side, y1)];
      }} else if (!Array.isArray(obj.anchor_x) || !Array.isArray(obj.anchor_y)) {{
        obj.anchor_x = [x0, x1];
        obj.anchor_y = [candleExtremeForDate(x0, side, y0), candleExtremeForDate(x1, side, y1)];
      }}
    }}
    if (!x0 || !x1 || !Number.isFinite(y0) || !Number.isFinite(y1)) return;
    if (Array.isArray(obj.x) && Array.isArray(obj.y)) {{
      obj.x = [x0, x1];
      obj.y = [y0, y1];
    }} else {{
      obj.x0 = x0;
      obj.y0 = y0;
      obj.x1 = x1;
      obj.y1 = y1;
    }}
  }}

  function setDisplayEndPrice(obj, value) {{
    const next = roundPrice(Number(value));
    if (!Number.isFinite(next)) return;
    if (Array.isArray(obj?.y) && obj.y.length >= 2) {{
      obj.y[obj.y.length - 1] = next;
    }} else if (obj) {{
      obj.y1 = next;
    }}
  }}

  function enforceLineDirection(obj, expectedSign, originalDelta) {{
    if (!expectedSign) return;
    const pts = lineDisplayValues(obj);
    if (!pts) return;
    const currentSign = Math.sign(Number(pts.y1) - Number(pts.y0));
    if (currentSign === expectedSign) return;
    const minDelta = Math.max(Math.abs(Number(originalDelta) || 0), Math.abs(Number(pts.y0)) * 0.002, 0.01);
    setDisplayEndPrice(obj, Number(pts.y0) + expectedSign * minDelta);
  }}

  function editableLineData(obj) {{
    const pts = lineDisplayValues(obj);
    return pts ? normalizeLineData([{{time:pts.x0, value:pts.y0}}, {{time:pts.x1, value:pts.y1}}]) : [];
  }}

  function straightWedgeLineData(obj) {{
    const anchors = lineEndpointValues(obj);
    if (!anchors) return [];
    const display = lineDisplayValues(obj) || anchors;
    const endTime = display.x1 || anchors.x1;
    const endValue = projectedLineValue(anchors.x0, anchors.y0, anchors.x1, anchors.y1, endTime);
    // Render wedge boundaries as one straight segment. The second anchor is
    // deliberately not inserted as a series vertex, because even a tiny logical
    // projection mismatch creates a visible kink after that anchor. The endpoint
    // is projected from the two anchors in the same date coordinate space used by
    // the chart renderer, so the unbroken straight segment crosses anchor #2.
    return normalizeLineData([
      {{time:anchors.x0, value:anchors.y0}},
      {{time:endTime, value:roundPrice(endValue)}},
    ]);
  }}

  function clampLineHandlePoint(pt) {{
    const wrap = $('chart-wrap');
    const w = wrap ? wrap.clientWidth : 0;
    const h = wrap ? wrap.clientHeight : 0;
    if (!pt || !Number.isFinite(pt.x) || !Number.isFinite(pt.y) || !w || !h) return pt;
    const pad = 16;
    const x = Math.min(Math.max(pt.x, pad), Math.max(pad, w - pad));
    const y = Math.min(Math.max(pt.y, pad), Math.max(pad, h - pad));
    return {{...pt, actualX:pt.x, actualY:pt.y, offscreen:x !== pt.x || y !== pt.y, x, y}};
  }}

  function lineObjectPoints(obj) {{
    const pts = lineDisplayValues(obj);
    if (!pts) return null;
    const startActual = {{x: chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(pts.x0) : null, y: candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(pts.y0) : null}};
    const endActual = {{x: chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(pts.x1) : null, y: candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(pts.y1) : null}};
    if (startActual.x === null || endActual.x === null || startActual.y === null || endActual.y === null) return null;
    if (!Number.isFinite(startActual.x) || !Number.isFinite(startActual.y) || !Number.isFinite(endActual.x) || !Number.isFinite(endActual.y)) return null;
    return {{start:clampLineHandlePoint(startActual), end:clampLineHandlePoint(endActual), actualStart:startActual, actualEnd:endActual, values:pts}};
  }}

  function distanceToSegment(px, py, ax, ay, bx, by) {{
    const dx = bx - ax, dy = by - ay;
    if (dx === 0 && dy === 0) return Math.hypot(px - ax, py - ay);
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  }}

  function hitTestLineObject(ev) {{
    const rect = $('chart-wrap').getBoundingClientRect();
    const px = ev.clientX - rect.left, py = ev.clientY - rect.top;
    for (let i = drawnObjects.length - 1; i >= 0; i--) {{
      const obj = drawnObjects[i];
      if (!isEditableLineObject(obj) || hiddenLegendKeys.has(editableObjectLegendKey(obj))) continue;
      const pts = lineObjectPoints(obj);
      if (!pts) continue;
      if (Math.hypot(px - pts.start.x, py - pts.start.y) <= 11) return {{obj, idx:i, mode:'start', points:pts.values}};
      if (Math.hypot(px - pts.end.x, py - pts.end.y) <= 11) return {{obj, idx:i, mode:'end', points:pts.values}};
      if (distanceToSegment(px, py, pts.start.x, pts.start.y, pts.end.x, pts.end.y) <= 8) return {{obj, idx:i, mode:'move', points:pts.values}};
    }}
    return null;
  }}

  function updateDraggedObjectSeries() {{
    if (!lineObjectDrag) return;
    const series = objectSeries.get(lineObjectDrag.obj);
    const viewport = lineObjectDrag.viewport;
    if (series) {{
      try {{ series.setData(editableLineData(lineObjectDrag.obj)); }} catch(e) {{ console.warn('line drag update failed', e); }}
    }}
    if (viewport && chart.timeScale().setVisibleLogicalRange) {{
      try {{ chart.timeScale().setVisibleLogicalRange(viewport); }} catch(e) {{ console.warn('line drag viewport restore failed', e); }}
    }}
    requestAnimationFrame(() => {{
      if (viewport && chart.timeScale().setVisibleLogicalRange) {{
        try {{ chart.timeScale().setVisibleLogicalRange(viewport); }} catch(e) {{ console.warn('line drag viewport restore failed', e); }}
      }}
      drawCloud();
      updateWedgeDebugPanel();
    }});
  }}

  function scheduleDraggedObjectSeriesUpdate() {{
    if (lineDragFrame) return;
    lineDragFrame = requestAnimationFrame(() => {{
      lineDragFrame = null;
      updateDraggedObjectSeries();
    }});
  }}

  function beginLineObjectDrag(ev) {{
    if (activeTool !== 'level' || activeField) return false;
    const hit = hitTestLineObject(ev);
    if (!hit) return false;
    const date = pointDateFromEvent(ev), price = pointPriceFromEvent(ev);
    if (!date || !Number.isFinite(price)) return false;
    lineObjectDrag = {{
      id:ev.pointerId,
      ...hit,
      startDate:date,
      startPrice:price,
      original:{{...hit.points}},
      viewport:captureViewport(),
      originalSlopeSign:Math.sign(Number(hit.points.y1) - Number(hit.points.y0)),
      originalAnchors:{{
        x:Array.isArray(hit.obj.anchor_x) ? [...hit.obj.anchor_x] : null,
        y:Array.isArray(hit.obj.anchor_y) ? [...hit.obj.anchor_y] : null,
      }},
    }};
    $('chart-wrap').classList.add('drawing-object');
    $('chart-wrap').setPointerCapture?.(ev.pointerId);
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation?.();
    return true;
  }}

  function moveLineObjectDrag(ev) {{
    if (!lineObjectDrag || lineObjectDrag.id !== ev.pointerId) return false;
    const date = pointDateFromEvent(ev), price = pointPriceFromEvent(ev);
    if (!date || !Number.isFinite(price)) return true;
    const obj = lineObjectDrag.obj;
    const o = lineObjectDrag.original;
    if (lineObjectDrag.mode === 'start') {{
      setLineEndpointValues(obj, date, price, o.x1, o.y1, 'start');
      enforceLineDirection(obj, lineObjectDrag.originalSlopeSign, o.y1 - o.y0);
    }} else if (lineObjectDrag.mode === 'end') {{
      setLineEndpointValues(obj, o.x0, o.y0, date, price, 'end');
    }} else {{
      const dDays = dayDelta(lineObjectDrag.startDate, date);
      const dPrice = price - lineObjectDrag.startPrice;
      if (isWedgeLineObject(obj) && Array.isArray(lineObjectDrag.originalAnchors.x) && Array.isArray(lineObjectDrag.originalAnchors.y)) {{
        obj.anchor_x = lineObjectDrag.originalAnchors.x.map(d => dateShiftDays(d, dDays));
        obj.anchor_y = lineObjectDrag.originalAnchors.y.map(v => roundPrice(Number(v) + dPrice));
      }}
      setLineEndpointValues(obj, dateShiftDays(o.x0, dDays), o.y0 + dPrice, dateShiftDays(o.x1, dDays), o.y1 + dPrice, 'move');
    }}
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation?.();
    scheduleDraggedObjectSeriesUpdate();
    return true;
  }}

  function endLineObjectDrag(ev) {{
    if (!lineObjectDrag || lineObjectDrag.id !== ev.pointerId) return false;
    $('chart-wrap').releasePointerCapture?.(ev.pointerId);
    $('chart-wrap').classList.remove('drawing-object');
    if (lineDragFrame) {{ cancelAnimationFrame(lineDragFrame); lineDragFrame = null; }}
    updateDraggedObjectSeries();
    lineObjectDrag = null;
    suppressChartClickUntil = Date.now() + 300;
    restoreChartInteractions();
    ev.preventDefault();
    ev.stopPropagation();
    ev.stopImmediatePropagation?.();
    applyWedgeDerivedLevels();
    ['high', 'low', 'line_cross_value', 'stop_loss'].forEach(refreshLevelSeries);
    updatePanel();
    requestAnimationFrame(drawCloud);
    return true;
  }}

  function updateLineObjectHover(ev) {{
    if (lineObjectDrag) return;
    $('chart-wrap').classList.toggle('line-handle-hover', !!hitTestLineObject(ev));
  }}

  function lineValueForDate(obj, time) {{
    if (!obj) return null;
    if (isWedgeLineObject(obj)) {{
      const anchors = lineEndpointValues(obj);
      if (anchors) return projectedLineValue(anchors.x0, anchors.y0, anchors.x1, anchors.y1, time);
    }}
    if (Array.isArray(obj.x) && Array.isArray(obj.y)) {{
      const idx = obj.x.map(x => String(x).slice(0, 10)).indexOf(String(time).slice(0, 10));
      if (idx >= 0) return Number(obj.y[idx]);
    }}
    const endpoints = lineDisplayValues(obj);
    const x0 = endpoints ? endpoints.x0 : String(obj.x0 || '').slice(0, 10), x1 = endpoints ? endpoints.x1 : String(obj.x1 || '').slice(0, 10);
    const y0 = endpoints ? Number(endpoints.y0) : Number(obj.y0), y1 = endpoints ? Number(endpoints.y1) : Number(obj.y1);
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



  function wedgeExtremePoint(obj, side) {{
    const points = wedgeTouchPoints(obj || {{}}).filter(pt => Number.isFinite(Number(pt.value)));
    if (!points.length) return firstAnchorPoint(obj);
    const sorted = points.slice().sort((a, b) => side === 'lower' ? Number(a.value) - Number(b.value) : Number(b.value) - Number(a.value));
    const pt = sorted[0];
    return {{date:String(pt.time).slice(0, 10), price:roundPrice(Number(pt.value))}};
  }}

  function lastAnchorDate(obj) {{
    const dates = (Array.isArray(obj?.anchor_x) && obj.anchor_x.length ? obj.anchor_x : [obj?.x0, obj?.x1])
      .map(x => String(x || '').slice(0, 10))
      .filter(Boolean)
      .sort(compareTime);
    return dates.length ? dates[dates.length - 1] : null;
  }}

  function applyWedgeDerivedLevels() {{
    const wedges = drawnObjects.filter(obj => obj.type === 'wedge' || obj.group_id === 'auto-wedge');
    if (!wedges.length) {{
      if (levels.__wedge_auto_high__ || levelPoints.high?.auto_wedge) {{ delete levels.high; delete levelPoints.high; delete levels.__wedge_auto_high__; }}
      if (levels.__wedge_auto_low__ || levelPoints.low?.auto_wedge) {{ delete levels.low; delete levelPoints.low; delete levels.__wedge_auto_low__; }}
      return;
    }}
    const upper = wedges.find(obj => String(obj.label || '').toLowerCase().includes('upper'));
    const lower = wedges.find(obj => String(obj.label || '').toLowerCase().includes('lower'));
    const upperAnchor = wedgeExtremePoint(upper || wedges[0], 'upper');
    const lowerAnchor = wedgeExtremePoint(lower || wedges[1], 'lower');
    const highIsAuto = levels.high == null || levels.__wedge_auto_high__ || levelPoints.high?.auto_wedge;
    if (upperAnchor && highIsAuto) {{
      levels.high = upperAnchor.price;
      levels.__wedge_auto_high__ = true;
      levelPoints.high = {{price:upperAnchor.price, plot_price:upperAnchor.price, date:upperAnchor.date, auto_wedge:true}};
    }}
    const lowIsAuto = levels.low == null || levels.__wedge_auto_low__ || levelPoints.low?.auto_wedge;
    if (lowerAnchor && lowIsAuto) {{
      levels.low = lowerAnchor.price;
      levels.__wedge_auto_low__ = true;
      levelPoints.low = {{price:lowerAnchor.price, plot_price:lowerAnchor.price, date:lowerAnchor.date, auto_wedge:true}};
    }}
    const candidates = [];
    wedges.forEach(obj => {{
      const label = String(obj.label || '').toLowerCase();
      const isUpper = label.includes('upper');
      const isLower = label.includes('lower');
      const activeAfter = lastAnchorDate(obj);
      let prevInside = null;
      P.ohlc.forEach(row => {{
        if (activeAfter && compareTime(row.time, activeAfter) <= 0) return;
        const line = lineValueForDate(obj, row.time);
        if (!Number.isFinite(line)) return;
        const inside = isUpper ? row.close <= line : (isLower ? row.close >= line : true);
        const outsideBreak = (isUpper && row.close > line) || (isLower && row.close < line);
        if (prevInside === true && outsideBreak) candidates.push({{time:row.time, value:roundPrice(line), source:obj, isUpper, isLower}});
        prevInside = inside;
      }});
    }});
    candidates.sort((a, b) => compareTime(a.time, b.time));
    if (!candidates.length) {{
      if (levels.__wedge_auto_line_cross__ || levelPoints.line_cross_value?.auto_wedge) {{ delete levels.line_cross_value; delete levelPoints.line_cross_value; delete levels.__wedge_auto_line_cross__; }}
      if (levels.__wedge_auto_stop_loss__ || levelPoints.stop_loss?.auto_wedge) {{ delete levels.stop_loss; delete levelPoints.stop_loss; delete levels.__wedge_auto_stop_loss__; }}
      if (levels.__wedge_auto_position_type__) {{ delete levels.position_type; delete levels.__wedge_auto_position_type__; }}
      return;
    }}
    if (candidates.length) {{
      const cross = candidates[0];
      const wedgePositionType = cross.isLower ? 'short' : 'long';
      const lineCrossIsAuto = levels.line_cross_value == null || levels.__wedge_auto_line_cross__ || levelPoints.line_cross_value?.auto_wedge;
      if (lineCrossIsAuto) {{
        levels.line_cross_value = cross.value;
        levels.__wedge_auto_line_cross__ = true;
        levelPoints.line_cross_value = {{price:cross.value, plot_price:cross.value, date:cross.time, auto_wedge:true}};
      }}
      if (!levels.position_type || levels.__wedge_auto_position_type__) {{
        levels.position_type = wedgePositionType;
        levels.__wedge_auto_position_type__ = true;
        if ($('position-type')) $('position-type').value = wedgePositionType;
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

  function wedgeLineThroughExtremeObjects(candidate) {{
    const rows = ohlc.filter(r => r && r.time && Number.isFinite(Number(r.high)) && Number.isFinite(Number(r.low)));
    const dateForIdx = (idx) => rows[Math.max(0, Math.min(rows.length - 1, idx))]?.time;
    const lineAt = (a, b, idx) => a.price + (b.price - a.price) * ((idx - a.idx) / Math.max(1, b.idx - a.idx));
    const maxIdx = rows.length - 1;
    const projection = Math.max(80, Math.abs(candidate.upper.b.idx - candidate.upper.a.idx) * 2, Math.abs(candidate.lower.b.idx - candidate.lower.a.idx) * 2);
    let endIdx = maxIdx + projection;
    const us = (candidate.upper.b.price - candidate.upper.a.price) / Math.max(1, candidate.upper.b.idx - candidate.upper.a.idx);
    const ls = (candidate.lower.b.price - candidate.lower.a.price) / Math.max(1, candidate.lower.b.idx - candidate.lower.a.idx);
    const denom = us - ls;
    if (Math.abs(denom) > 1e-9) {{
      const ui = candidate.upper.a.price - us * candidate.upper.a.idx;
      const li = candidate.lower.a.price - ls * candidate.lower.a.idx;
      const cross = Math.ceil((li - ui) / denom);
      if (cross > maxIdx) endIdx = Math.max(endIdx, cross + 5);
    }}
    endIdx = Math.min(endIdx, maxIdx + Math.max(rows.length, 180));
    const make = (side, color, label, id, line) => {{
      const anchorX = [dateForIdx(line.a.idx), dateForIdx(line.b.idx)];
      const anchorY = [roundPrice(line.a.price), roundPrice(line.b.price)];
      const endTime = endIdx <= maxIdx ? dateForIdx(endIdx) : addDays(dateForIdx(maxIdx), endIdx - maxIdx);
      const x = [anchorX[0], anchorX[1], endTime];
      const y = [anchorY[0], anchorY[1], roundPrice(lineAt(line.a, line.b, endIdx))];
      return {{id, type:'wedge', label, x, y, x0:x[0], x1:x[x.length - 1], y0:y[0], y1:y[y.length - 1], anchor_x:anchorX, anchor_y:anchorY, price:y[y.length - 1], color, group_id:'auto-wedge'}};
    }};
    return [
      make('upper', '#dc2626', 'Falling wedge upper', 'auto-wedge-upper', candidate.upper),
      make('lower', '#2563eb', 'Falling wedge lower', 'auto-wedge-lower', candidate.lower),
    ];
  }}

  function findAlternativeWedgeCandidate(side='both') {{
    const rows = ohlc.filter(r => r && r.time && Number.isFinite(Number(r.high)) && Number.isFinite(Number(r.low)) && Number.isFinite(Number(r.close)));
    if (rows.length < 55) return null;
    const wedges = drawnObjects.filter(isWedgeLineObject);
    const upperObj = wedges.find(o => wedgeSide(o) === 'upper');
    const lowerObj = wedges.find(o => wedgeSide(o) === 'lower');
    if (!upperObj || !lowerObj) return null;
    const idxByTime = new Map(rows.map((r, i) => [String(r.time).slice(0,10), i]));
    const anchorIdx = (obj, pos) => idxByTime.get(String((obj.anchor_x || [])[pos] || '').slice(0,10));
    const curStart = Math.min(anchorIdx(upperObj, 0) ?? rows.length, anchorIdx(lowerObj, 0) ?? rows.length);
    const curUpperFirst = anchorIdx(upperObj, 0);
    const curUpperSecond = anchorIdx(upperObj, 1);
    const curLowerFirst = anchorIdx(lowerObj, 0);
    const curLowerSecond = anchorIdx(lowerObj, 1);
    const hi = i => Number(rows[i].high), lo = i => Number(rows[i].low), cl = i => Number(rows[i].close);
    const isHigh = i => i > 0 && i < rows.length - 1 && hi(i) >= hi(i - 1) && hi(i) >= hi(i + 1);
    const isLow = i => i > 0 && i < rows.length - 1 && lo(i) <= lo(i - 1) && lo(i) <= lo(i + 1);
    const tol = Math.max(...rows.slice(-30).map(r => Number(r.high) - Number(r.low)).filter(Number.isFinite), Math.abs(cl(rows.length - 1)) * 0.004) * 0.20;
    const end = rows.length - 1;
    const scoreCurrent = Math.max(1, end - curStart);
    const upperSeconds = side === 'lower' ? [curUpperSecond].filter(Number.isFinite) : [...new Set([curUpperSecond, ...Array.from({{length:Math.min(35, end)}}, (_, k) => end - 3 - k).filter(i => i > 5 && isHigh(i))])].filter(Number.isFinite);
    const lowerSeconds = side === 'upper' ? [curLowerSecond].filter(Number.isFinite) : [...new Set([curLowerSecond, ...Array.from({{length:Math.min(35, end)}}, (_, k) => end - 3 - k).filter(i => i > 5 && isLow(i))])].filter(Number.isFinite);
    let best = null;
    for (const u2 of upperSeconds) for (const l2 of lowerSeconds) {{
      const u1s = side === 'lower' && Number.isFinite(curUpperFirst) ? [curUpperFirst] : [];
      if (side !== 'lower') for (let i = Math.max(1, u2 - 260); i <= u2 - 5; i++) if (isHigh(i) && hi(i) > hi(u2)) u1s.push(i);
      const l1s = side === 'upper' && Number.isFinite(curLowerFirst) ? [curLowerFirst] : [];
      if (side !== 'upper') for (let i = Math.max(1, l2 - 260); i <= l2 - 5; i++) if (isLow(i) && lo(i) < lo(l2)) l1s.push(i);
      for (const u1 of u1s) for (const l1 of l1s) {{
        const us = (hi(u2) - hi(u1)) / (u2 - u1), ls = (lo(l2) - lo(l1)) / (l2 - l1);
        if (!(us < 0) || us >= ls || ls > Math.abs(us) * 1.10) continue;
        const line = (a, av, b, bv, i) => av + (bv - av) * ((i - a) / (b - a));
        let invalid = false, upperTouches = 2, lowerTouches = 2;
        const first = Math.min(u1, l1);
        for (let i = first; i <= end; i++) {{
          const up = line(u1, hi(u1), u2, hi(u2), i), low = line(l1, lo(l1), l2, lo(l2), i);
          if (low >= up || (cl(i) > up + tol * 0.1 && i < end - 5) || (cl(i) < low - tol * 0.1 && i < end - 5)) {{ invalid = true; break; }}
          if (i > u2 && hi(i) >= up - tol && cl(i) <= up + tol * 0.1) upperTouches++;
          if (i > l2 && lo(i) <= low + tol && cl(i) >= low - tol * 0.1) lowerTouches++;
        }}
        if (invalid || upperTouches < 2 || lowerTouches < 2) continue;
        const duration = end - first;
        if (duration <= scoreCurrent * 1.15 && hi(u1) <= candleExtremeForDate((upperObj.anchor_x || [])[0], 'upper', 0) && lo(l1) >= candleExtremeForDate((lowerObj.anchor_x || [])[0], 'lower', Infinity)) continue;
        const widthStart = line(u1, hi(u1), u2, hi(u2), first) - line(l1, lo(l1), l2, lo(l2), first);
        const widthEnd = line(u1, hi(u1), u2, hi(u2), end) - line(l1, lo(l1), l2, lo(l2), end);
        if (widthStart <= 0 || widthEnd <= 0 || widthEnd >= widthStart * 0.95) continue;
        const score = duration * 10 + widthStart + (upperTouches + lowerTouches) * 15 + Math.max(0, hi(u1) - hi(u2)) + Math.max(0, lo(l2) - lo(l1));
        if (!best || score > best.score) best = {{score, upper:{{a:{{idx:u1, price:hi(u1)}}, b:{{idx:u2, price:hi(u2)}}}}, lower:{{a:{{idx:l1, price:lo(l1)}}, b:{{idx:l2, price:lo(l2)}}}}}};
      }}
    }}
    return best;
  }}

  function restoreScannerWedgeFromRoulette() {{
    if (!initialScannerDrawnObjects.length) return false;
    drawnObjects = drawnObjects.filter(o => !isWedgeLineObject(o)).concat(initialScannerDrawnObjects.map(deepClone));
    wedgeRouletteNoAlternative = false;
    applyWedgeDerivedLevels();
    ['high', 'low', 'line_cross_value', 'stop_loss'].forEach(refreshLevelSeries);
    render();
    updateWedgeDebugPanel('Restored the original scanner wedge.');
    return true;
  }}

  function findNewWedge(side='both') {{
    const candidate = findAlternativeWedgeCandidate(side);
    if (!candidate) {{
      if (wedgeRouletteNoAlternative && restoreScannerWedgeFromRoulette()) return;
      wedgeRouletteNoAlternative = true;
      updateWedgeDebugPanel(`No larger valid ${{side === 'upper' ? 'upper-line ' : (side === 'lower' ? 'lower-line ' : '')}}alternative wedge found. Click 🎲 Find new wedge again to restore the scanner wedge.`);
      return;
    }}
    wedgeRouletteNoAlternative = false;
    drawnObjects = drawnObjects.filter(o => !isWedgeLineObject(o)).concat(wedgeLineThroughExtremeObjects(candidate));
    applyWedgeDerivedLevels();
    ['high', 'low', 'line_cross_value', 'stop_loss'].forEach(refreshLevelSeries);
    render();
    updateWedgeDebugPanel('Found and loaded a larger valid wedge alternative. Save & Close to keep it for future allsearch calculations.');
  }}


  function drawWedgeStraightLines(ctx) {{
    drawnObjects.filter(obj => isWedgeLineObject(obj) && !hiddenLegendKeys.has(editableObjectLegendKey(obj))).forEach(obj => {{
      const anchors = lineEndpointValues(obj);
      if (!anchors) return;
      const x0 = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(anchors.x0) : null;
      const x1 = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(anchors.x1) : null;
      const y0 = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(anchors.y0) : null;
      const y1 = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(anchors.y1) : null;
      if (![x0, x1, y0, y1].every(Number.isFinite) || x0 === x1) return;
      const slope = (y1 - y0) / (x1 - x0);
      const leftX = Math.max(0, Math.min(x0, x1));
      const rightX = Math.max($('chart-wrap').clientWidth || 0, x0, x1);
      ctx.save();
      ctx.strokeStyle = obj.color || '#facc15';
      ctx.lineWidth = 3;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(leftX, y0 + slope * (leftX - x0));
      ctx.lineTo(rightX, y0 + slope * (rightX - x0));
      ctx.stroke();
      ctx.restore();
    }});
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
    if (!levels.__show_ichimoku__) {{ drawWedgeStraightLines(ctx); drawWedgeTouchPoints(ctx); drawValuePointers(ctx); drawLineObjectHandles(ctx); drawDomChartIcons(); return; }}
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
    drawWedgeStraightLines(ctx);
    drawWedgeTouchPoints(ctx);
    drawValuePointers(ctx);
    drawLineObjectHandles(ctx);
    drawDomChartIcons();
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

  function fibRatioValue(obj) {{
    if (Number.isFinite(Number(obj.ratio))) return Number(obj.ratio);
    const label = fibPercentLabel(obj);
    if (!label) return NaN;
    return Number(label.replace('%', '')) / 100;
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
      const series = addLine([{{time:x0, value:pt.plot_price ?? pt.price}}, {{time:x1, value:pt.plot_price ?? pt.price}}], levelColors[field] || '#94a3b8', 2, LightweightCharts.LineStyle.Solid, `${{labels[field]}}: ${{fmt(pt.price)}}`, true, false, false, `level:${{field}}`, deleteFn, false);
      if (series) levelSeries.set(field, series);
      if (field === 'entry') {{
        const entrySeries = addLine([{{time:pt.date, value:pt.price}}], levelColors[field], 2.2, LightweightCharts.LineStyle.Solid, '', false, false, false, 'level:entry-point', null, false);
        if (entrySeries) levelSeries.set('entry-point', entrySeries);
      }}
    }});
    (levels.__half_points__ || []).forEach((pt, i) => {{
      const series = addLine([{{time:pt.date, value:pt.price}}], '#a855f7', 2, LightweightCharts.LineStyle.Solid, 'Half point', true, false, false, `half:${{i}}`, null, false);
      if (series) levelSeries.set(`half:${{i}}`, series);
    }});
    const seenFibLegend = new Set();
    let wedgeLegendAdded = false;
    drawnObjects.forEach(obj => {{
      const isFib = obj.type === 'fib';
      const isFibBoundary = obj.type === 'fib-boundary';
      const color = isFib ? fibColor(fibRatioValue(obj)) : (isFibBoundary ? fibLineColor : (obj.color || P.lineColors.gold));
      const isWedge = obj.type === 'wedge' || obj.group_id === 'auto-wedge';
      const fibKey = (isFib || isFibBoundary) ? `fib-group:${{obj.group_id || obj.id}}` : null;
      const objKey = isWedge ? `wedge:${{obj.id || obj.label || Math.random()}}` : ((isFib || isFibBoundary) ? fibKey : `obj:${{obj.id || obj.label || Math.random()}}`);
      const deleteFn = (isFib || isFibBoundary) ? (() => {{ drawnObjects = drawnObjects.filter(o => o.group_id !== obj.group_id); hiddenLegendKeys.delete(fibKey); }}) : (isWedge ? (() => {{ drawnObjects = drawnObjects.filter(o => o !== obj); hiddenLegendKeys.delete(objKey); }}) : (() => {{ drawnObjects = drawnObjects.filter(o => o.id !== obj.id); hiddenLegendKeys.delete(objKey); }}));
      let objectLegend = '';
      let showLegend = false;
      if (isFib) {{
        objectLegend = 'Fibonacci';
        showLegend = !seenFibLegend.has(fibKey);
        seenFibLegend.add(fibKey);
        if (showLegend) addLegend(objectLegend, color, fibKey, deleteFn);
      }} else if (isFibBoundary) {{
        objectLegend = '';
        showLegend = false;
      }} else if (isWedge) {{
        objectLegend = obj.label || 'Falling wedge';
        showLegend = true;
      }} else {{
        objectLegend = obj.label || 'LINE';
        showLegend = true;
      }}
      const seriesTitle = isFib ? (fibPercentLabel(obj) || objectLegend) : objectLegend;
      let series = null;
      if (isWedge) {{
        addLegend(seriesTitle, color, objKey, deleteFn);
      }} else if (Array.isArray(obj.x) && Array.isArray(obj.y)) {{
        series = addLine(obj.x.map((x, i) => ({{time:String(x).slice(0,10), value:Number(obj.y[i])}})), color, isFib ? 1.2 : 2, LightweightCharts.LineStyle.Solid, seriesTitle, showLegend && !isFib, false, isFib, objKey, deleteFn, !isEditableLineObject(obj));
      }} else {{
        const x1 = isFib ? extendFuture(obj.x1, 720) : String(obj.x1).slice(0,10);
        series = addLine([{{time:String(obj.x0).slice(0,10), value:Number(obj.y0)}}, {{time:x1, value:Number(obj.y1)}}], color, isFib && String(obj.label || '').includes('61.8%') ? 1.4 : (isFib ? 1.0 : 2), LightweightCharts.LineStyle.Solid, seriesTitle, showLegend && !isFib, false, isFib, objKey, deleteFn, !isEditableLineObject(obj));
      }}
      if (series && isEditableLineObject(obj)) objectSeries.set(obj, series);
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
    const resetScannerBtn = $('reset-scanner-drawings');
    if (resetScannerBtn) resetScannerBtn.style.display = initialScannerDrawnObjects.length ? 'block' : 'none';
    const hasWedgeObjects = drawnObjects.some(isWedgeLineObject);
    const findNewWedgeBtn = $('find-new-wedge');
    if (findNewWedgeBtn) findNewWedgeBtn.style.display = hasWedgeObjects ? 'block' : 'none';
    ['find-new-upper-wedge', 'find-new-lower-wedge'].forEach(id => {{ const btn = $(id); if (btn) btn.style.display = hasWedgeObjects ? 'block' : 'none'; }});
    const seenFib = new Set();
    drawnObjects.forEach((obj, idx) => {{
      if (obj.type === 'fib' && obj.group_id) {{ if (seenFib.has(obj.group_id)) return; seenFib.add(obj.group_id); picker.add(new Option(`FIB group (${{String(obj.group_id).slice(0,8)}})`, `fib-group:${{obj.group_id}}`)); return; }}
      picker.add(new Option(`${{obj.label || 'OBJ'}} (${{String(obj.id || idx).slice(0,8)}})`, obj.id || `obj-index:${{idx}}`));
    }});
    updateWedgeDebugPanel();
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

  function chartGroupOpenUrl(command) {{
    const url = new URL('/open-chart', chartGroup.reportServer);
    url.searchParams.set('command', command);
    if (chartGroup.id) url.searchParams.set('group', chartGroup.id);
    return url.href;
  }}

  function setupChartGroupNav() {{
    const wrap = $('chart-group-nav');
    const label = $('chart-group-label');
    const buttons = $('chart-group-buttons');
    if (!wrap || !buttons || !chartGroup || !Array.isArray(chartGroup.items) || chartGroup.items.length < 2 || !chartGroup.reportServer) return;
    wrap.style.display = 'block';
    if (label) label.textContent = chartGroup.label || 'Group charts';
    buttons.innerHTML = '';
    const current = String(chartGroup.current || '');
    const go = (command, clickedButton=null) => {{
      if (!command || command === current) return;
      if (clickedButton) clickedButton.textContent = 'Loading…';
      window.location.replace(chartGroupOpenUrl(command));
    }};
    const sections = new Map();
    chartGroup.items.forEach(item => {{
      const section = item.section || '';
      if (!sections.has(section)) sections.set(section, []);
      sections.get(section).push(item);
    }});
    sections.forEach((items, section) => {{
      let target = buttons;
      if (section) {{
        const block = document.createElement('div');
        block.className = 'chart-group-section';
        const title = document.createElement('div');
        title.className = 'chart-group-section-title';
        title.textContent = section;
        target = document.createElement('div');
        target.className = 'chart-group-buttons';
        block.appendChild(title);
        block.appendChild(target);
        buttons.appendChild(block);
      }}
      items.forEach((item) => {{
        const command = item.command || '';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = item.label || command || 'Chart';
        btn.classList.toggle('active', !!current && command === current);
        btn.onclick = () => go(command, btn);
        target.appendChild(btn);
      }});
    }});
  }}

  seq.forEach(field => {{ const b = document.createElement('button'); b.id = field + '-btn'; b.textContent = labels[field]; b.onclick = () => {{ clearPreviews(); const same = activeTool === 'level' && activeField === field; activeTool='level'; activeField=same ? null : field; lineAnchor=fibAnchor=halfAnchor=null; updatePanel(); }}; $('level-buttons').appendChild(b); }});
  $('position-type').value = levels.position_type || 'long'; $('capital').value = levels.capital || 255000;
  $('lot-cost').value = levels.lot_cost && levels.lot_cost !== 0 ? levels.lot_cost : ''; $('pip-value').value = levels.__stock_cfd_mode__ ? 1 : ((levels.pip_value && levels.pip_value !== 0) ? levels.pip_value : '');
  $('spread-mult').value = levels.spread_multiplier && levels.spread_multiplier !== 0 ? levels.spread_multiplier : '';
  $('tool-line').onclick = () => {{ const same = activeTool === 'line'; clearPreviews(); activeTool=same ? 'level' : 'line'; activeField=null; fibAnchor=halfAnchor=null; updatePanel(); }};
  $('tool-fib').onclick = () => {{ const same = activeTool === 'fib'; clearPreviews(); activeTool=same ? 'level' : 'fib'; activeField=null; lineAnchor=halfAnchor=null; updatePanel(); }};
  $('tool-half').onclick = () => {{ const same = activeTool === 'half'; clearPreviews(); activeTool=same ? 'level' : 'half'; activeField=null; lineAnchor=fibAnchor=null; updatePanel(); }};
  document.querySelectorAll('.color-dot').forEach(b => b.onclick = () => lineColor = b.dataset.color);
  $('ichimoku-toggle').onclick = () => {{ levels.__show_ichimoku__ = !levels.__show_ichimoku__; render(); }};
  $('reset-all').onclick = () => {{ levels = {{}}; levelPoints = {{}}; drawnObjects = []; lineAnchor=fibAnchor=halfAnchor=null; activeTool='level'; activeField=null; render(); applyInstrumentControls(); }};
  $('stock-cfd-toggle').onclick = () => {{ levels.__stock_cfd_mode__ = !levels.__stock_cfd_mode__; if (levels.__stock_cfd_mode__) $('pip-value').value = 1; applyInstrumentControls(); }};
  $('currency-fee-toggle').onclick = () => {{ levels.apply_currency_conversion_fee = !levels.apply_currency_conversion_fee; applyInstrumentControls(); if ($('calc-drawer').classList.contains('open')) calculatePosition(true); }};
  $('wedge-debug-btn').onclick = () => copyWedgeDebug();
  $('find-new-wedge').onclick = () => findNewWedge('both');
  $('find-new-upper-wedge').onclick = () => findNewWedge('upper');
  $('find-new-lower-wedge').onclick = () => findNewWedge('lower');
  $('reset-scanner-drawings').onclick = () => {{
    if (!initialScannerDrawnObjects.length) return;
    drawnObjects = initialScannerDrawnObjects.map(deepClone);
    if (levels.__wedge_auto_high__ || levelPoints.high?.auto_wedge) {{ delete levels.high; delete levelPoints.high; delete levels.__wedge_auto_high__; }}
    if (levels.__wedge_auto_low__ || levelPoints.low?.auto_wedge) {{ delete levels.low; delete levelPoints.low; delete levels.__wedge_auto_low__; }}
    if (levels.__wedge_auto_line_cross__ || levelPoints.line_cross_value?.auto_wedge) {{ delete levels.line_cross_value; delete levelPoints.line_cross_value; delete levels.__wedge_auto_line_cross__; }}
    if (levels.__wedge_auto_stop_loss__ || levelPoints.stop_loss?.auto_wedge) {{ delete levels.stop_loss; delete levelPoints.stop_loss; delete levels.__wedge_auto_stop_loss__; }}
    hiddenLegendKeys.clear();
    lineAnchor=fibAnchor=halfAnchor=null;
    applyWedgeDerivedLevels();
    render();
  }};
  $('delete-object').onclick = () => {{ const id = $('object-picker').value; if (!id) return; if (id.startsWith('fib-group:')) {{ const gid = id.split(':')[1]; drawnObjects = drawnObjects.filter(o => o.group_id !== gid); }} else if (id.startsWith('obj-index:')) {{ const idx = Number(id.split(':')[1]); drawnObjects = drawnObjects.filter((_, i) => i !== idx); }} else drawnObjects = drawnObjects.filter(o => o.id !== id); render(); }};

  function commitLineDrawing(time, price) {{
    const obj = {{id:crypto.randomUUID(), type:'line', label:'LINE', x0:lineAnchor.x, y0:lineAnchor.y, x1:time, y1:price, color:lineColor}};
    drawnObjects.push(obj);
    const objKey = `obj:${{obj.id}}`;
    const deleteFn = () => {{ drawnObjects = drawnObjects.filter(o => o.id !== obj.id); hiddenLegendKeys.delete(objKey); }};
    addLegend(obj.label, obj.color, objKey, deleteFn);
    const data = editableLineData(obj);
    if (previewSeries) {{
      try {{
        previewSeries.setData(data);
        previewSeries.applyOptions?.({{color:obj.color, lineWidth:2, lineStyle:LightweightCharts.LineStyle.Solid, priceLineVisible:false, lastValueVisible:false, title:'', autoscaleInfoProvider:() => null}});
        dynamicSeries.push(previewSeries);
        objectSeries.set(obj, previewSeries);
      }} catch(e) {{ console.warn('line commit failed', e); safeRemoveSeries(previewSeries); }}
      previewSeries = null;
    }} else {{
      const series = addLine(data, obj.color, 2, LightweightCharts.LineStyle.Solid, obj.label, false, false, false, objKey, null, false);
      if (series) objectSeries.set(obj, series);
    }}
    lineAnchor = null;
    updatePanel();
    requestAnimationFrame(drawCloud);
  }}

  function forgetLevelSeries(key) {{
    const series = levelSeries.get(key);
    if (series) safeRemoveSeries(series);
    levelSeries.delete(key);
  }}

  function refreshLevelSeries(field) {{
    forgetLevelSeries(field);
    if (field === 'entry') forgetLevelSeries('entry-point');
    const pt = levelPoints[field];
    if (!pt) {{ updatePanel(); requestAnimationFrame(drawCloud); return; }}
    const levelColors = {{high:'#d946ef', low:'#14b8a6', entry:'#22c55e', stop_loss:'#ef4444', check_zr_value_fibo_or_elevation:'#f59e0b', line_cross_value:'#3b82f6'}};
    const deleteFn = deleteSelectedLevel(field);
    if (field === 'line_cross_value') {{
      addLegend(`${{labels[field]}}: ${{fmt(pt.price)}}`, levelColors[field] || '#3b82f6', `level:${{field}}`, deleteFn);
    }} else {{
      const base = nearest(pt.date);
      const x0 = dateAtIndex(base.idx - 5);
      const x1 = dateAtIndex(base.idx + 5);
      const series = addLine([{{time:x0, value:pt.plot_price ?? pt.price}}, {{time:x1, value:pt.plot_price ?? pt.price}}], levelColors[field] || '#94a3b8', 2, LightweightCharts.LineStyle.Solid, `${{labels[field]}}: ${{fmt(pt.price)}}`, true, false, false, `level:${{field}}`, deleteFn, false);
      if (series) levelSeries.set(field, series);
      if (field === 'entry') {{
        const entrySeries = addLine([{{time:pt.date, value:pt.price}}], levelColors[field], 2.2, LightweightCharts.LineStyle.Solid, '', false, false, false, 'level:entry-point', null, false);
        if (entrySeries) levelSeries.set('entry-point', entrySeries);
      }}
    }}
    updatePanel();
    requestAnimationFrame(drawCloud);
  }}

  function refreshHalfSeries() {{
    [...levelSeries.keys()].filter(k => String(k).startsWith('half:')).forEach(forgetLevelSeries);
    (levels.__half_points__ || []).forEach((pt, i) => {{
      const series = addLine([{{time:pt.date, value:pt.price}}], '#a855f7', 2, LightweightCharts.LineStyle.Solid, 'Half point', true, false, false, `half:${{i}}`, null, false);
      if (series) levelSeries.set(`half:${{i}}`, series);
    }});
    updatePanel();
    requestAnimationFrame(drawCloud);
  }}

  chart.subscribeClick(param => {{
    if (Date.now() < suppressChartClickUntil) return;
    if (!param || !param.point) return;
    const price = roundPrice(candleSeries.coordinateToPrice(param.point.y));
    const time = typeof param.time === 'string' ? param.time : (param.time ? `${{param.time.year}}-${{String(param.time.month).padStart(2,'0')}}-${{String(param.time.day).padStart(2,'0')}}` : nearest(null).time);
    if (!Number.isFinite(price)) return;
    if (activeTool === 'line') {{ if (!lineAnchor) {{ lineAnchor = {{x:time, y:price}}; updateLinePreview(addDays(time, 1), price); updatePanel(); }} else {{ commitLineDrawing(time, price); }} return; }}
    if (activeTool === 'fib') {{
      const row = nearest(time); const mid = (row.low + row.high) / 2;
      if (!fibAnchor) {{ fibAnchor = {{x:row.time, mid}}; updateFibPreview(row.time); updatePanel(); return; }}
      const row1 = nearest(fibAnchor.x), row2 = nearest(time); const firstMid = fibAnchor.mid, secondMid = (row2.low + row2.high)/2; const isShort = secondMid < firstMid;
      const low = isShort ? row2.low : row1.low, high = isShort ? row1.high : row2.high; const gid = crypto.randomUUID();
      const xEnd = addDays(P.ohlc[P.ohlc.length-1].time, Math.max(2880, Math.abs(row2.idx-row1.idx)*24));
      fibRatios.forEach((r) => {{ const y = fibPrice(low, high, r, isShort); const pct = `${{(r*100).toFixed(1)}}%`.replace('.0%','%'); drawnObjects.push({{id:crypto.randomUUID(), type:'fib', label:`FIB ${{pct}} (${{fmt(y)}})`, ratio:r, x0:fibStartDate(row1, row2, r), x1:xEnd, y0:y, y1:y, price:y, color:fibColor(r), group_id:gid, direction:isShort?'short':'long'}}); }});
      drawnObjects.push({{id:crypto.randomUUID(), type:'fib-boundary', label:'FIB anchor', x0:row1.time, x1:row2.time, y0:fibPrice(low, high, 1, isShort), y1:fibPrice(low, high, 0, isShort), color:fibLineColor, group_id:gid}});
      fibAnchor=null; clearPreviews(); render(); return;
    }}
    if (activeTool === 'half') {{ if (!halfAnchor) {{ levels.__half_points__ = [{{date:time, price}}]; halfAnchor = {{x:time, y:price}}; refreshHalfSeries(); return; }} const midpoint = roundPrice((halfAnchor.y + price)/2); levels.stop_loss = midpoint; levelPoints.stop_loss = {{price:midpoint, plot_price:midpoint, date:time}}; levels.__half_points__ = [{{date:halfAnchor.x, price:halfAnchor.y}}, {{date:time, price}}]; halfAnchor=null; refreshHalfSeries(); refreshLevelSeries('stop_loss'); return; }}
    if (activeTool === 'level' && activeField) {{ const row = nearest(time); let selected = price, plot = price; if (activeField === 'high' || activeField === 'low') {{ selected = roundPrice(activeField === 'high' ? row.high : row.low); plot = selected; }} levels[activeField] = selected; levelPoints[activeField] = {{price:selected, plot_price:plot, date:row.time}}; if (activeField === 'stop_loss') {{ levels.__half_points__ = []; refreshHalfSeries(); }} refreshLevelSeries(activeField); }}
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
    if (activeTool === 'fib' && fibAnchor && time) updateFibPreview(time);
  }});

  function collectLevelsForSave(finished=false) {{
    const stockCfdMode = !!levels.__stock_cfd_mode__;
    const pipValue = stockCfdMode ? 1 : Number($('pip-value').value || 0);
    const spreadMult = Number($('spread-mult').value || 0);
    return {{...levels,
      position_type:$('position-type').value,
      capital:roundPrice(Number($('capital').value || 255000)),
      lot_cost:roundPrice(Number($('lot-cost').value || 0)),
      pip_value:Number(pipValue.toFixed(4)),
      spread_multiplier:Number(spreadMult.toFixed(4)),
      spread:Number((stockCfdMode ? spreadMult : spreadMult*pipValue).toFixed(4)),
      spread_pips: stockCfdMode ? Number((spreadMult/0.01).toFixed(2)) : null,
      drawn_objects:drawnObjects,
      level_points:levelPoints,
      __finished__:!!finished}};
  }}

  function money(v, currency='PLN') {{
    const n = Number(v || 0);
    return n.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}}) + ' ' + currency;
  }}
  function numText(v, digits=2) {{
    const n = Number(v || 0);
    return n.toLocaleString(undefined, {{minimumFractionDigits:digits, maximumFractionDigits:digits}});
  }}
  function renderCalculation(data) {{
    const drawer = $('calc-drawer'), summary = $('calc-summary'), table = $('calc-table'), warnings = $('calc-warnings');
    drawer.classList.add('open');
    $('calc-drawer').closest('.main')?.classList.add('calc-open');
    if (!data || !data.ok) {{
      summary.innerHTML = `<b>Unable to calculate:</b> ${{(data && data.error) ? data.error : 'unknown error'}}`;
      table.innerHTML = ''; warnings.innerHTML = ''; return;
    }}
    const currency = data.currency || 'PLN';
    const b = data.basics || {{}};
    const chips = [];
    chips.push(`<span><b>Instrument:</b> ${{data.instrument_type || P.instrumentType}}</span>`);
    chips.push(`<span><b>Position:</b> ${{(data.position_type || $('position-type').value || 'long').toUpperCase()}}</span>`);
    if (Number.isFinite(Number(b.entry))) chips.push(`<span><b>Entry:</b> ${{fmt(Number(b.entry))}}</span>`);
    if (Number.isFinite(Number(b.stop_loss))) chips.push(`<span><b>Stop loss:</b> ${{fmt(Number(b.stop_loss))}}</span>`);
    if (Number.isFinite(Number(b.max_capital))) chips.push(`<span><b>Max capital:</b> ${{money(b.max_capital, currency)}}</span>`);
    if (data.fx_conversion_fee_applicable) chips.push(`<span><b>FX conversion fee ${{numText(data.fx_conversion_fee_pct || 1, 0)}}%:</b> ${{data.fx_conversion_fee_enabled ? 'ON' : 'OFF'}}</span>`);
    if (Number.isFinite(Number(b.lot_cost))) chips.push(`<span><b>Lot cost:</b> ${{money(b.lot_cost, currency)}}</span>`);
    if (Number.isFinite(Number(b.spread))) chips.push(`<span><b>Spread:</b> ${{numText(b.spread, 4)}}</span>`);
    if (data.take_profit != null) chips.push(`<span><b>Take profit:</b> ${{fmt(Number(data.take_profit))}}</span>`);
    if (data.risk_reward != null) chips.push(`<span><b>Risk/reward:</b> ${{numText(data.risk_reward, 2)}}:1</span>`);
    if (data.profit != null) chips.push(`<span><b>Profit:</b> ${{money(data.profit, currency)}} (${{numText(data.profit_percent, 2)}}%)</span>`);
    if (data.zr_ratio != null) chips.push(`<span><b>Additional Z/R:</b> ${{numText(data.zr_ratio, 2)}}:1</span>`);
    summary.innerHTML = chips.join('');
    table.innerHTML = `<table><thead><tr><th>Risk Level</th><th>Position Size</th><th>Engaged Capital</th><th>Potential Loss With Spread</th><th>Loss %</th></tr></thead><tbody>${{(data.rows||[]).map(r => `<tr><td>${{r.risk_label}}</td><td>${{numText(r.position_size, r.position_unit === 'Shares' ? 0 : 3)}} ${{r.position_unit}}</td><td>${{money(r.capital_used, currency)}}</td><td>${{money(r.potential_loss, currency)}}</td><td>${{numText(r.loss_percent, 2)}}%</td></tr>`).join('')}}</tbody></table>`;
    warnings.innerHTML = (data.warnings || []).map(w => `<div>⚠️ ${{w}}</div>`).join('');
    requestAnimationFrame(() => {{
      document.documentElement.style.setProperty('--calc-drawer-height', `${{Math.ceil(drawer.getBoundingClientRect().height + 10)}}px`);
      window.dispatchEvent(new Event('resize'));
      applyVerticalPan();
    }});
  }}
  async function calculatePosition(show=true) {{
    const current = collectLevelsForSave(false);
    try {{
      const resp = await fetch('/calculate', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{levels:current}})}});
      const data = await resp.json();
      if (data && data.ok) levels = {{...levels, position_calculations:data}};
      if (show) renderCalculation(data);
      return data;
    }} catch(e) {{
      const data = {{ok:false, error:String(e)}};
      if (show) renderCalculation(data);
      return data;
    }}
  }}
  $('calculate-btn').onclick = () => calculatePosition(true);
  $('calc-close').onclick = () => {{ $('calc-drawer').classList.remove('open'); $('calc-drawer').closest('.main')?.classList.remove('calc-open'); window.dispatchEvent(new Event('resize')); }};

  $('finish-btn').onclick = async () => {{
    const calc = await calculatePosition(false);
    levels = collectLevelsForSave(true);
    if (calc && calc.ok) levels.position_calculations = calc;
    let screenshot = null; try {{ screenshot = chart.takeScreenshot(true, false).toDataURL('image/png'); }} catch(e) {{}}
    const resp = await fetch('/finish', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{levels, screenshot}})}});
    if (resp.ok) {{ $('result-box').textContent = 'Saved. Closing app...'; setTimeout(() => {{ fetch('/shutdown', {{method:'POST', keepalive:true}}); try {{ window.close(); }} catch(e) {{}} }}, 250); }}
  }};

  setInterval(() => fetch('/heartbeat', {{method:'POST', keepalive:true}}).catch(()=>{{}}), 1000);
  if (!P.reportLaunched) {{ window.addEventListener('beforeunload', () => navigator.sendBeacon('/shutdown')); }}
  setupChartGroupNav();
  applyWedgeDerivedLevels(); applyInstrumentControls(); render();
}})();
  </script>
</body>
</html>"""


    def _position_calculation_payload(self, levels: dict) -> dict:
        def _num(key: str, default: float = 0.0) -> float:
            try:
                value = levels.get(key, default)
                return float(default if value in (None, "") else value)
            except (TypeError, ValueError):
                return float(default)

        entry = _num("entry")
        stop_loss = _num("stop_loss")
        high = _num("high")
        low = _num("low")
        capital = _num("capital", 255000.0)
        position_type = str(levels.get("position_type") or "long").lower()
        position_type = "short" if position_type == "short" else "long"
        stock_cfd_mode = bool(levels.get("__stock_cfd_mode__"))
        effective_instrument = "commodity" if stock_cfd_mode else self.instrument_type
        risk_levels = sorted(DEFAULT_RISK_LEVELS)
        rows = []
        warnings = []
        currency = "PLN"

        if entry <= 0 or capital <= 0 or stop_loss <= 0:
            return {"ok": False, "error": "Select entry, stop loss, and capital before calculating."}

        try:
            if effective_instrument == "stock":
                conversion_fee_pct = float(levels.get("currency_conversion_fee_pct", 0.01) or 0.01) if levels.get("apply_currency_conversion_fee") else 0.0
                max_capital = capital
                try:
                    if "Volume" in self.df.columns:
                        turnover = (pd.to_numeric(self.df["Close"], errors="coerce") * pd.to_numeric(self.df["Volume"], errors="coerce")).dropna()
                        if len(turnover) >= 10:
                            max_capital = float(turnover.tail(10).mean()) * 0.01
                        else:
                            warnings.append("Turnover history is short; max capital uses available capital.")
                    else:
                        warnings.append("Volume data is unavailable; max capital uses available capital.")
                except Exception as exc:
                    warnings.append(f"Could not derive turnover max capital: {exc}")
                for risk in risk_levels:
                    result = calculate_stock_position(entry, stop_loss, capital, risk, max_capital, conversion_fee_pct=conversion_fee_pct, position_type=position_type)
                    rows.append({
                        "risk": risk,
                        "risk_label": f"{risk * 100:.1f}%",
                        "position_size": result.get("shares", 0),
                        "position_unit": "Shares",
                        "capital_used": round(float(result.get("capital_used", 0.0)), 2),
                        "potential_loss": round(float(result.get("potential_loss", 0.0)), 2),
                        "loss_percent": round(float(result.get("risk_percent", 0.0)), 2),
                    })
                basics = {"entry": entry, "stop_loss": stop_loss, "max_capital": round(max_capital, 2)}
            else:
                lot_cost = _num("lot_cost")
                pip_value = 1.0 if stock_cfd_mode else _num("pip_value")
                spread = _num("spread")
                pip_size = _num("pip_size", 0.0001 if effective_instrument == "forex" else 1.0)
                if lot_cost <= 0:
                    return {"ok": False, "error": "Lot cost must be greater than zero before calculating."}
                if pip_value <= 0:
                    return {"ok": False, "error": "Pip value must be greater than zero before calculating."}
                conversion_fee_pct = float(levels.get("currency_conversion_fee_pct", 0.01) or 0.01) if levels.get("apply_currency_conversion_fee") else 0.0
                for risk in risk_levels:
                    result = calculate_position_size(
                        entry=entry,
                        stop_loss=stop_loss,
                        capital=capital,
                        risk_percent=risk,
                        pip_value=pip_value,
                        lot_cost=lot_cost,
                        spread=spread,
                        pip_size=pip_size,
                        position_type=position_type,
                        instrument_type=effective_instrument,
                        conversion_fee_pct=conversion_fee_pct,
                    )
                    rows.append({
                        "risk": risk,
                        "risk_label": f"{risk * 100:.1f}%",
                        "position_size": result.get("lots", 0),
                        "position_unit": "Lots",
                        "capital_used": round(float(result.get("capital_used", 0.0)), 2),
                        "potential_loss": round(float(result.get("potential_loss", 0.0)), 2),
                        "loss_percent": round(float(result.get("risk_percent", 0.0)), 2),
                    })
                basics = {"entry": entry, "stop_loss": stop_loss, "lot_cost": lot_cost, "pip_value": pip_value, "spread": spread}

            take_profit = None
            risk_reward = None
            profit = None
            profit_percent = None
            if high and low and levels.get("line_cross_value") not in (None, ""):
                try:
                    take_profit = calculate_take_profit(entry, high, low, position_type, start_value=_num("line_cross_value"))
                    base = next((r for r in rows if float(r.get("position_size", 0) or 0) > 0), None)
                    if base and float(base.get("potential_loss", 0) or 0) > 0:
                        if base["position_unit"] == "Shares":
                            profit = float(base["position_size"]) * ((take_profit - entry) if position_type == "long" else (entry - take_profit))
                        else:
                            pip_size = _num("pip_size", 0.0001 if effective_instrument == "forex" else 1.0)
                            pip_value = 1.0 if stock_cfd_mode else _num("pip_value")
                            profit = abs(take_profit - entry) / pip_size * float(base["position_size"]) * pip_value
                        profit_percent = (profit / capital) * 100 if capital else None
                        risk_reward = profit / float(base["potential_loss"])
                except Exception as exc:
                    warnings.append(f"Take-profit preview unavailable: {exc}")

            zr_ratio = None
            if levels.get("check_zr_value_fibo_or_elevation") not in (None, ""):
                try:
                    zr_ratio = calculate_distance_ratio(entry, stop_loss, _num("check_zr_value_fibo_or_elevation"))
                except Exception as exc:
                    warnings.append(f"Additional Z/R preview unavailable: {exc}")

            return {
                "ok": True,
                "instrument_type": effective_instrument,
                "position_type": position_type,
                "currency": currency,
                "fx_conversion_fee_applicable": bool(levels.get("__currency_fee_eligible__")),
                "fx_conversion_fee_enabled": bool(levels.get("apply_currency_conversion_fee")),
                "fx_conversion_fee_pct": round(float(levels.get("currency_conversion_fee_pct", 0.01) or 0.01) * 100, 2),
                "rows": rows,
                "basics": basics,
                "take_profit": None if take_profit is None else round(float(take_profit), self._precision_for_price(take_profit)),
                "risk_reward": None if risk_reward is None else round(float(risk_reward), 2),
                "profit": None if profit is None else round(float(profit), 2),
                "profit_percent": None if profit_percent is None else round(float(profit_percent), 2),
                "zr_ratio": None if zr_ratio is None else round(float(zr_ratio), 2),
                "warnings": warnings,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def run(self):
        app = Flask(__name__)
        server_holder: dict[str, object] = {}
        heartbeat = {"ts": time.time(), "seen": False}
        first_heartbeat_grace = 45 if os.environ.get("STOCKHELPER_REPORT_LAUNCHED_CHART") == "1" else 4

        class QuietRequestHandler(WSGIRequestHandler):
            def log(self, type, message, *args):  # noqa: A003
                return

        @app.route("/")
        def _index():
            return self._html()

        @app.route("/calculate", methods=["POST"])
        def _calculate():
            payload = request.get_json(silent=True) or {}
            levels = payload.get("levels") or {}
            return jsonify(self._position_calculation_payload(levels))

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
            heartbeat["seen"] = True
            return "ok"

        chart_url = f"http://127.0.0.1:{self.server_port}/"
        url_file = os.environ.get("STOCKHELPER_CHART_URL_FILE")
        server = make_server("127.0.0.1", self.server_port, app, threaded=True, request_handler=QuietRequestHandler)
        server_holder["server"] = server
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        if url_file:
            try:
                Path(url_file).write_text(chart_url, encoding="utf-8")
            except Exception:
                pass
        if os.environ.get("STOCKHELPER_CHART_NO_AUTO_OPEN") != "1":
            threading.Timer(0.8, lambda: webbrowser.open(chart_url)).start()
        try:
            while server_thread.is_alive():
                if self._finished:
                    server.shutdown()
                    break
                heartbeat_timeout = 4 if heartbeat.get("seen") else first_heartbeat_grace
                if time.time() - heartbeat["ts"] > heartbeat_timeout:
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
