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
    .layout {{ display: grid; grid-template-columns: 1fr 430px; height: 100vh; }}
    .main {{ padding: 14px 0 14px 14px; min-width: 0; }}
    h3 {{ margin: 0 0 10px 0; }}
    button {{ background: #1f2937; color: #e5e7eb; border: 1px solid #334155; border-radius: 6px; padding: 8px; cursor: pointer; font-weight: 700; }}
    button.active {{ background: #2563eb; border-color: #2563eb; color: white; }}
    .level-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }}
    .toolbar {{ display: flex; gap: 8px; margin-bottom: 10px; align-items: center; }}
    .wedge-mini-btn {{ display:none; min-width:32px; padding:8px 6px; }}
    #chart-wrap {{ position: relative; height: calc(100vh - 230px); min-height: 360px; border: 1px solid #1f2937; border-radius: 8px; overflow: hidden; }}
    body.close-mode .layout {{ grid-template-columns: 1fr; }}
    body.close-mode .side, body.close-mode .toolbar, body.close-mode .level-grid, body.close-mode #cursor-box, body.close-mode #chart-legend, body.close-mode #calc-drawer, body.close-mode .main>h3 {{ display:none !important; }}
    body.close-mode .main {{ padding:14px; }}
    body.close-mode #chart-wrap {{ height:calc(100vh - 96px); min-height:520px; border-color:#22c55e; box-shadow:0 0 0 1px rgba(34,197,94,.35),0 24px 80px rgba(0,0,0,.45); }}
    #close-mode-panel {{ display:none; align-items:center; gap:10px; margin:0 0 10px; padding:10px 12px; border:1px solid rgba(34,197,94,.45); border-radius:14px; background:linear-gradient(135deg,rgba(22,101,52,.30),rgba(15,23,42,.92)); }}
    body.close-mode #close-mode-panel {{ display:flex; }}
    #close-mode-panel strong {{ color:#86efac; font-size:18px; }}
    .close-line-control {{ display:flex; align-items:center; gap:6px; padding:6px 8px; border:1px solid rgba(148,163,184,.28); border-radius:10px; background:rgba(15,23,42,.74); cursor:grab; }}
    .close-line-control.active {{ border-color:#38bdf8; box-shadow:0 0 0 2px rgba(56,189,248,.16); }}
    .close-line-control span {{ font-weight:900; font-size:12px; letter-spacing:.06em; }}
    .close-line-control input {{ width:120px; }}
    #close-mode-save {{ background:linear-gradient(135deg,#16a34a,#22c55e); color:#052e16; border-color:#86efac; }}
    #chart {{ position:absolute; inset:0; width: 100%; height: 100%; z-index:1; }}
    #chart .tv-lightweight-charts {{ width:100% !important; height:100% !important; }}
    #cloud-overlay {{ position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 30; }}
    #icon-overlay {{ position:absolute; inset:0; pointer-events:none; z-index:60; overflow:hidden; }}
    .chart-icon {{ position:absolute; transform:translate(-50%,-50%); min-width:12px; height:12px; padding:0 2px; border-radius:999px; display:flex; align-items:center; justify-content:center; font-size:8px; line-height:1; font-weight:900; color:#0f172a; background:#f8fafc; border:1.5px solid currentColor; box-shadow:0 2px 8px rgba(0,0,0,.55); }}
    .chart-icon.anchor {{ color:#f8fafc; background:#111827; border-color:#f8fafc; text-shadow:0 1px 2px #000; }}
    .chart-icon.touch {{ color:#0f172a; background:#fbbf24; border-color:#0f172a; width:7px; min-width:7px; height:7px; padding:0; }}
    .chart-icon.cross {{ color:#f8fafc; background:#a855f7; border-color:#f8fafc; }}
    .chart-icon.end {{ color:#0f172a; background:#f8fafc; }}
    #chart-wrap.drawing-object {{ cursor: grabbing; }}
    #chart-wrap.line-handle-hover {{ cursor: pointer; }}
    #cursor-box {{ margin-bottom: 8px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 16px; font-weight: 700; text-align: center; }}
    .side {{ border-left: 1px solid rgba(96,165,250,.18); padding: 14px; background: radial-gradient(circle at 20% 0, rgba(37,99,235,.12), transparent 34%), #020817; overflow-y: auto; }}
    .side-card {{ margin-bottom:10px; padding:11px; border:1px solid rgba(148,163,184,.28); border-radius:16px; background:linear-gradient(145deg, rgba(15,23,42,.94), rgba(2,6,23,.92)); box-shadow:0 14px 36px rgba(0,0,0,.30), inset 0 1px 0 rgba(255,255,255,.04); }}
    .manual-card {{ padding:18px; border-radius:22px; background:linear-gradient(135deg,rgba(31,41,55,.78),rgba(15,23,42,.92) 52%,rgba(2,6,23,.96)); box-shadow:0 22px 60px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.08); }}
    .instrument-hero {{ display:grid; grid-template-columns:42px 1fr; gap:10px; align-items:center; margin-bottom:8px; }}
    .hero-icon,.section-icon {{ display:grid; place-items:center; border-radius:12px; background:linear-gradient(135deg,#0b5ed7,#0ea5e9); color:white; box-shadow:0 10px 24px rgba(14,165,233,.20); font-size:22px; }}
    .hero-icon {{ width:42px; height:42px; }}
    .section-icon {{ width:26px; height:26px; font-size:14px; background:rgba(37,99,235,.18); color:#c7d2fe; box-shadow:none; }}
    #identity {{ margin:0; font-size:20px; line-height:1.08; color:#f8fafc; font-weight:900; letter-spacing:-.03em; }}
    .identity-sub {{ color:#9fb4d6; font-weight:700; margin-top:2px; font-size:13px; }}
    .meta-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; padding-top:8px; border-top:1px solid rgba(148,163,184,.18); }}
    .meta-field.full {{ grid-column:1 / -1; }}
    .meta-label,.side-section-title {{ display:flex; align-items:center; gap:6px; color:#b8c7e6; font-weight:800; font-size:12px; margin-bottom:6px; }}
    .meta-value {{ min-height:38px; display:flex; align-items:center; justify-content:space-between; gap:8px; padding:8px 10px; border:1px solid #334155; border-radius:11px; background:rgba(2,6,23,.42); color:#f8fafc; font-size:15px; font-weight:900; }}
    #source {{ color:#f8fafc; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.03em; }}
    #stock-cfd-toggle {{ width:100%; min-height:38px; margin:0; display:none; justify-content:space-between; align-items:center; text-align:left; padding:8px 64px 8px 10px; border-radius:11px; border:1px solid #334155; background:rgba(2,6,23,.42); color:#f8fafc; position:relative; }}
    #stock-cfd-toggle::after {{ content:''; position:absolute; right:10px; top:50%; transform:translateY(-50%); width:42px; height:22px; border-radius:999px; background:#1e293b; box-shadow:inset 0 0 0 1px rgba(255,255,255,.08); }}
    #stock-cfd-toggle::before {{ content:''; position:absolute; right:29px; top:50%; transform:translateY(-50%); width:18px; height:18px; border-radius:50%; background:#cbd5e1; z-index:1; box-shadow:0 2px 8px rgba(0,0,0,.45); transition:right .18s ease, background .18s ease; }}
    #stock-cfd-toggle.active::after {{ background:linear-gradient(90deg,#2563eb,#60a5fa); box-shadow:0 0 18px rgba(96,165,250,.35); }}
    #stock-cfd-toggle.active::before {{ right:13px; background:#fff; }}
    .side-card-head {{ display:flex; align-items:center; gap:9px; margin-bottom:9px; }}
    .manual-card .side-card-head {{ padding-bottom:14px; border-bottom:1px solid rgba(148,163,184,.20); margin-bottom:14px; }}
    .side-card-head h4 {{ margin:0; color:#dbeafe; font-size:16px; }}
    .manual-card .side-card-head h4 {{ color:#f8fafc; font-size:24px; letter-spacing:-.03em; }}
    label {{ display: block; margin-top: 8px; }}
    input, select, textarea {{ width: 100%; min-height:38px; color: #f8fafc; background: rgba(15,23,42,.86); font-size: 14px; padding: 8px 10px; border-radius: 11px; border: 1px solid #334155; }}
    .manual-card label {{ color:#cbd5e1; font-size:14px; margin-top:10px; }}
    .manual-card input,.manual-card select {{ min-height:42px; border-radius:13px; background:rgba(15,23,42,.62); border-color:rgba(96,165,250,.32); }}
    .manual-card input:focus,.manual-card select:focus {{ outline:none; border-color:#60a5fa; box-shadow:0 0 0 3px rgba(59,130,246,.18), 0 0 24px rgba(59,130,246,.18); }}
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
    .values {{ display:grid; grid-template-columns:1fr 1fr; gap:7px; margin-bottom: 4px; }}
    .value-tile {{ min-height:58px; padding:8px; border:1px solid #334155; border-radius:12px; background:rgba(2,6,23,.38); text-align:center; }}
    .value-tile .value-label {{ color:#aebcda; text-transform:uppercase; font-weight:900; font-size:11px; letter-spacing:.05em; }}
    .value-tile .value-number {{ margin-top:5px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:17px; font-weight:900; color:#f8fafc; }}
    .value-tile.entry .value-number {{ color:#4ade80; }}
    .value-tile.stop_loss .value-number {{ color:#fb7185; }}
    .color-dot {{ width: 22px; height: 22px; padding: 0; border: 1px solid white; }}
    #chart-legend {{ display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; min-height: 20px; margin: 0 0 7px 0; font-size: 12px; font-weight: 700; }}
    #chart-legend span {{ display: inline-flex; align-items: center; gap: 5px; cursor: pointer; user-select: none; }}
    #chart-legend span.hidden {{ opacity: 0.38; text-decoration: line-through; }}
    #chart-legend button {{ padding: 0 5px; line-height: 16px; font-size: 11px; border-radius: 4px; background: #334155; color: #e5e7eb; }}
    .side-action-btn {{ margin-top:9px;width:100%;padding:12px 14px;color:white;border:none;border-radius:16px;font-size:16px;font-weight:900;letter-spacing:-.01em;line-height:1.15;text-align:center;box-shadow:0 10px 28px rgba(0,0,0,.22);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px; }} .side-action-btn .btn-icon {{ width:36px;height:36px;border-radius:12px;display:inline-grid;place-items:center;background:rgba(255,255,255,.13);box-shadow:inset 0 1px 0 rgba(255,255,255,.14),0 8px 18px rgba(0,0,0,.18);font-size:20px; }}
    .action-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }} .action-grid.no-wedge {{ grid-template-columns:1fr; }} .action-grid.no-wedge #journal-toggle-btn {{ min-height:58px; }}
    .action-grid .side-action-btn {{ min-height:52px; }}
    #calculate-btn {{ min-height:58px; background:linear-gradient(135deg,#0f766e,#22c55e) !important; border:1px solid rgba(134,239,172,.80); box-shadow:0 16px 34px rgba(34,197,94,.24), inset 0 1px 0 rgba(255,255,255,.14); }}
    #calculate-btn .btn-icon {{ background:rgba(220,252,231,.18); color:#dcfce7; }}
    #calculate-btn::after {{ content:none; }}
    #setup-debug-btn {{ background:linear-gradient(135deg,rgba(88,28,135,.72),rgba(49,46,129,.80)) !important; border:1px solid #c084fc; box-shadow:0 14px 30px rgba(168,85,247,.18), inset 0 1px 0 rgba(255,255,255,.12); }}
    #journal-toggle-btn {{ background:linear-gradient(135deg,#9a3412,#f59e0b) !important; border:1px solid #fcd34d; box-shadow:0 14px 30px rgba(245,158,11,.20), inset 0 1px 0 rgba(255,255,255,.12); }}
    #journal-toggle-btn .btn-icon {{ background:rgba(254,243,199,.18); color:#fef3c7; }}
    #finish-btn {{ background:linear-gradient(135deg,#1d4ed8,#7c3aed) !important; border:1px solid #93c5fd; min-height:66px; box-shadow:0 18px 38px rgba(37,99,235,.28), inset 0 1px 0 rgba(255,255,255,.14); }}
    #finish-btn .btn-icon {{ background:rgba(219,234,254,.18); color:#dbeafe; }}
    #currency-fee-toggle {{ min-height:46px !important;padding:9px 64px 9px 12px !important;font-size:14px !important;border-radius:14px !important;background:rgba(15,23,42,.58)!important;border:1px solid rgba(148,163,184,.25)!important;display:flex!important;align-items:center;justify-content:space-between;position:relative; }}
    #currency-fee-toggle::after {{ content:''; position:absolute; right:12px; top:50%; transform:translateY(-50%); width:42px; height:22px; border-radius:999px; background:#1e293b; box-shadow:inset 0 0 0 1px rgba(255,255,255,.08); }}
    #currency-fee-toggle::before {{ content:''; position:absolute; right:31px; top:50%; transform:translateY(-50%); width:18px; height:18px; border-radius:50%; background:#cbd5e1; z-index:1; box-shadow:0 2px 8px rgba(0,0,0,.45); transition:right .18s ease, background .18s ease; }}
    #currency-fee-toggle.active::after {{ background:linear-gradient(90deg,#2563eb,#60a5fa); box-shadow:0 0 18px rgba(96,165,250,.35); }}
    #currency-fee-toggle.active::before {{ right:15px; background:#fff; }}
    #result-box {{ margin-top:12px; padding:14px; border:1px solid rgba(34,197,94,.45); border-radius:16px; background:linear-gradient(135deg,rgba(6,78,59,.45),rgba(2,6,23,.65)); color:#d1fae5; font-weight:800; overflow-wrap:anywhere; }}
    #result-box:empty {{ display:none; }}
    #journal-panel {{ margin-top:12px;padding:14px;border:1px solid rgba(96,165,250,.35);border-radius:18px;background:linear-gradient(145deg, rgba(15,23,42,.98), rgba(2,6,23,.96));box-shadow:0 18px 55px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.06); }}
    #journal-panel h4 {{ display:flex;align-items:center;gap:10px;margin:0 0 12px 0;color:#f8fafc;font-size:18px; }}
    #journal-panel h4::before {{ content:'🧾';display:inline-grid;place-items:center;width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#0ea5e9,#2563eb);box-shadow:0 0 24px rgba(37,99,235,.35); }}
    #journal-panel label {{ margin-top:11px;color:#b6c7e6;text-transform:uppercase;letter-spacing:.06em;font-size:11px;font-weight:900; }}
    #journal-panel input,#journal-panel select,#journal-panel textarea {{ margin-top:5px;color:#e5e7eb;background:rgba(15,23,42,.78);border:1px solid #334155;border-radius:12px;padding:10px 12px;outline:none;box-shadow:inset 0 1px 0 rgba(255,255,255,.04); }}
    #journal-panel input:focus,#journal-panel select:focus,#journal-panel textarea:focus {{ border-color:#60a5fa;box-shadow:0 0 0 3px rgba(96,165,250,.18); }}
    #journal-currency-buttons,#calculation-currency-buttons {{ display:grid !important;gap:7px;margin-top:7px; }}
    #journal-currency-buttons {{ grid-template-columns:repeat(3,1fr); }}
    #calculation-currency-buttons {{ grid-template-columns:repeat(4,1fr); }}
    #journal-currency-buttons button,#calculation-currency-buttons button {{ border-radius:999px;padding:8px;background:#111827;color:#bfdbfe;border:1px solid #334155; }}
    #journal-currency-buttons button.active,#calculation-currency-buttons button.active {{ background:linear-gradient(135deg,#2563eb,#06b6d4);color:white;border-color:#93c5fd; }}
    #journal-notes {{ min-height:170px; resize:vertical; }}
    #journal-preview {{ display:none; white-space:pre-wrap;background:rgba(2,6,23,.76);border:1px solid #334155;border-radius:14px;padding:10px;margin-top:10px;color:#dbeafe;font-size:12px;max-height:170px;overflow:auto; }}
    #journal-panel.show-preview #journal-preview {{ display:block; }}
    .manual-card.journal-open > label,.manual-card.journal-open > input,.manual-card.journal-open > select,.manual-card.journal-open > #calculation-currency-buttons,.manual-card.journal-open > #currency-fee-toggle,.manual-card.journal-open > #object-picker,.manual-card.journal-open > #delete-object,.manual-card.journal-open > #calculate-btn,.manual-card.journal-open > .action-grid,.manual-card.journal-open > #finish-btn,.manual-card.journal-open > #wedge-debug-panel {{ display:none !important; }}
    .manual-card.journal-open #journal-panel {{ margin-top:0; padding:16px; min-height:520px; }}
    #journal-close-panel {{ width:auto;margin-left:auto;padding:6px 10px;border-radius:999px;background:#1e293b;border:1px solid #475569;color:#dbeafe;font-size:12px; }}
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
      <div id="close-mode-panel"><strong>💰 Close adjust</strong><span>Grab a line, click chart, or edit inputs.</span><label class="close-line-control active" data-line="sold"><span>🟢 SOLD</span><input id="close-mode-price" type="number" step="any"></label><label class="close-line-control" data-line="entry"><span>🔵 ENTRY</span><input id="close-mode-entry" type="number" step="any"></label><label class="close-line-control" data-line="sl"><span>🔴 SL</span><input id="close-mode-stop-loss" type="number" step="any" placeholder="last SL"></label><label class="close-line-control"><span>↕ SIDE</span><select id="close-mode-direction"><option value="long">↗ LONG</option><option value="short">↘ SHORT</option></select></label><button id="close-mode-save" type="button">Accept closing screenshot</button><span id="close-mode-status"></span></div>
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
      <section class="side-card instrument-card">
        <div class="instrument-hero">
          <div class="hero-icon">↗</div>
          <div><h2 id="identity"></h2><div class="identity-sub">Name / Ticker</div></div>
        </div>
        <div class="meta-grid">
          <div class="meta-field"><div class="meta-label">🏛 Instrument</div><div class="meta-value" id="instrument-title"></div></div>
          <div class="meta-field"><div class="meta-label">🛡 CFD mode</div><button id="stock-cfd-toggle"></button></div>
          <div class="meta-field full"><div class="meta-label">📄 Source</div><div class="meta-value"><span id="source"></span></div></div>
        </div>
      </section>
      <section class="side-card selected-card">
        <div class="side-card-head"><span class="section-icon">◎</span><h4>Selected values</h4></div>
        <div id="values-panel" class="values"></div>
        <div id="chart-group-nav" class="chart-group-nav">
          <h4>⭐ Quick charts from 📊</h4>
          <div id="chart-group-label" class="chart-group-label"></div>
          <div id="chart-group-buttons" class="chart-group-buttons"></div>
        </div>
      </section>
      <section class="side-card manual-card">
        <div class="side-card-head"><span class="section-icon">✎</span><h4>Manual inputs</h4></div>
        <label id="position-type-label">Position type</label>
        <select id="position-type"><option value="long">LONG</option><option value="short">SHORT</option></select>
        <label>Capital</label><input id="capital" type="number" />
        <label>Calculation currency</label><div id="calculation-currency-buttons"><button type="button" data-currency="PLN">PLN</button><button type="button" data-currency="USD">USD</button><button type="button" data-currency="EUR">EUR</button><button type="button" data-currency="GBP">GBP</button></div><input id="calculation-currency" type="hidden" value="PLN" />
        <button id="currency-fee-toggle" style="margin-top:8px;width:100%;display:none"></button>
        <label id="lot-cost-label">Lot cost</label><input id="lot-cost" type="number" />
        <label id="pip-value-label">Pip value</label><input id="pip-value" type="number" />
        <label id="spread-mult-label">Spread multiplier (spread = Multiplier * pip_value)</label><input id="spread-mult" type="number" />
        <select id="object-picker" style="display:none"><option value="">-- select --</option></select>
        <button id="delete-object" style="display:none">Delete selected object</button>
        <button id="calculate-btn" class="side-action-btn"><span class="btn-icon">🧮</span><span>Calculate position</span></button>
        <div class="action-grid">
          <button id="setup-debug-btn" class="side-action-btn"><span class="btn-icon">📈</span><span>Setup information</span></button>
          <button id="journal-toggle-btn" class="side-action-btn"><span class="btn-icon">🧾</span><span>Add journal entry</span></button>
        </div>
        <button id="finish-btn" class="side-action-btn"><span class="btn-icon">💾</span><span>Save &amp; Close</span></button>
        <div id="journal-panel" style="display:none">
          <h4>Transaction journal <button id="journal-close-panel" type="button">Close</button></h4>
          <label>Technique</label><select id="journal-technique"><option>Kliny</option><option>Ichimoku</option><option>Fibo</option><option>Manual</option></select>
          <label>Transaction amount</label><input id="journal-amount" placeholder="e.g. 5000" /><div id="journal-currency-buttons"><button type="button" data-currency="PLN">PLN</button><button type="button" data-currency="USD">USD</button><button type="button" data-currency="EUR">EUR</button></div><input id="journal-currency" type="hidden" value="PLN" />
          <label>Reason</label><select id="journal-reason"></select>
          <div id="journal-touches-row"><label>Touches</label><input id="journal-touches" placeholder="e.g. 3" /></div>
          <label>Notes / why entry</label><textarea id="journal-notes" rows="5" placeholder="Setup, highlighted values, risk, context"></textarea>
          <div id="journal-preview"></div>
          <button id="journal-save-btn" class="side-action-btn" style="background:#ea580c">Save journal + screenshot</button>
        </div>
        <div id="wedge-debug-panel"></div>
        <div id="result-box"></div>
      </section>
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
  const wedgeRouletteSeen = {{both:new Set(), upper:new Set(), lower:new Set()}};
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
  function resizeChartToContainer() {{
    const el = $('chart');
    if (!el || !chart.applyOptions) return;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {{
      try {{ chart.applyOptions({{width: Math.floor(r.width), height: Math.floor(r.height)}}); }} catch(e) {{}}
      requestAnimationFrame(drawCloud);
    }}
  }}
  if (window.ResizeObserver) new ResizeObserver(resizeChartToContainer).observe($('chart'));
  window.addEventListener('resize', resizeChartToContainer);
  requestAnimationFrame(resizeChartToContainer);
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

  function scannerCandlesCsv(limit = 140) {{
    const realCandles = ohlc.filter(c => c && c.time && Number.isFinite(Number(c.open)) && Number.isFinite(Number(c.high)) && Number.isFinite(Number(c.low)) && Number.isFinite(Number(c.close)));
    const rows = realCandles.slice(Math.max(0, realCandles.length - limit));
    const lines = ['Date,Open,High,Low,Close,Volume'];
    rows.forEach(row => lines.push([row.time, fmt(row.open), fmt(row.high), fmt(row.low), fmt(row.close), row.volume ?? ''].join(',')));
    return lines.join('\n');
  }}

  function ichimokuDebugSnapshot() {{
    const lines = [];
    lines.push(`ICHIMOKU DEBUG: ${{P.symbol || ''}}`);
    lines.push(`Generated: ${{new Date().toISOString()}}`);
    lines.push(`Visible: ${{levels.__show_ichimoku__ ? 'yes' : 'no'}}`);
    lines.push('Latest values:');
    ['tenkan','kijun','spanA','spanB','chikou'].forEach(k => {{
      const arr = P.ichimoku?.[k] || [];
      const last = arr.length ? arr[arr.length - 1] : null;
      lines.push(`  ${{k}}: ${{last ? `${{last.time}} @ ${{fmt(last.value)}}` : '-'}}`);
    }});
    lines.push('');
    lines.push('Candles data for scanner formations (latest candles):');
    lines.push(scannerCandlesCsv());
    return lines.join('\n');
  }}

  function fiboDebugSnapshot() {{
    const fibs = drawnObjects.filter(obj => obj.type === 'fib' || obj.type === 'fib-boundary');
    const lines = [];
    lines.push(`FIBO DEBUG: ${{P.symbol || ''}}`);
    lines.push(`Generated: ${{new Date().toISOString()}}`);
    if (!fibs.length) lines.push('No Fibonacci lines on chart.');
    const groups = new Map();
    fibs.forEach(obj => {{ const gid = obj.group_id || obj.id || 'manual'; if (!groups.has(gid)) groups.set(gid, []); groups.get(gid).push(obj); }});
    groups.forEach((items, gid) => {{
      lines.push('');
      lines.push(`FIB group: ${{gid}}`);
      items.forEach(obj => lines.push(`  ${{obj.label || obj.type}}: ${{obj.x0 || ''}}->${{obj.x1 || ''}} ${{fmt(obj.y0)}}${{obj.y1 !== obj.y0 ? `->${{fmt(obj.y1)}}` : ''}} ${{obj.direction || ''}}`));
    }});
    lines.push('');
    lines.push('Candles data for scanner formations (latest candles):');
    lines.push(scannerCandlesCsv());
    return lines.join('\n');
  }}

  function setupDebugSnapshot() {{
    const tech = selectedJournalTechnique();
    if (tech === 'Ichimoku') return ichimokuDebugSnapshot();
    if (tech === 'Fibo') return fiboDebugSnapshot();
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

  function updateSetupDebugPanel(message = '') {{
    const panel = $('wedge-debug-panel');
    if (!panel || !panel.classList.contains('open')) return;
    const text = setupDebugSnapshot();
    panel.textContent = message ? `${{message}}\\n\\n${{text}}` : text;
  }}

  async function copySetupDebug() {{
    const panel = $('wedge-debug-panel');
    if (panel?.classList.contains('open')) {{
      panel.classList.remove('open');
      panel.textContent = '';
      return;
    }}
    const text = setupDebugSnapshot();
    if (panel) {{
      panel.classList.add('open');
      panel.textContent = text;
    }}
    try {{
      await navigator.clipboard.writeText(text);
      updateSetupDebugPanel('Copied setup debug to clipboard.');
    }} catch (err) {{
      updateSetupDebugPanel('Clipboard copy failed. Select and copy the debug text below.');
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
          ctx.arc(0, 0, 4.6, 0, Math.PI * 2);
          ctx.shadowColor = 'rgba(0,0,0,.55)';
          ctx.shadowBlur = 3;
          ctx.fillStyle = 'rgba(15,23,42,.35)';
          ctx.strokeStyle = '#f8fafc';
          ctx.lineWidth = 1.2;
          ctx.stroke();
          ctx.shadowBlur = 0;
          ctx.beginPath();
          ctx.arc(0, 0, 1.7, 0, Math.PI * 2);
          ctx.fillStyle = '#a855f7';
          ctx.fill();
          ctx.restore();
          return;
        }}
        ctx.beginPath();
        ctx.arc(x, y, 2.5, 0, Math.PI * 2);
        ctx.shadowColor = 'rgba(0,0,0,.55)';
        ctx.shadowBlur = 4;
        ctx.fillStyle = '#fbbf24';
        ctx.strokeStyle = '#0f172a';
        ctx.lineWidth = 0.9;
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
        ctx.arc(x, y, 3.2, 0, Math.PI * 2);
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
      ctx.arc(x, y, 4.2, 0, Math.PI * 2);
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
    const axisPadX = 78;
    const axisPadY = 44;
    const maxX = Math.max(pad, (layer.clientWidth || 0) - axisPadX);
    const maxY = Math.max(pad, (layer.clientHeight || 0) - axisPadY);
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
    if (x > rect.width) {{
      const extraCandles = Math.min(120, Math.max(5, Math.round((x - rect.width) / 7)));
      return addDays(P.ohlc[P.ohlc.length - 1]?.time || nearest(null).time, extraCandles);
    }}
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
        const rawY1 = Number(ys[last]);
        const y1 = obj.free_extension ? rawY1 : projectedLineValue(anchors.x0, anchors.y0, anchors.x1, anchors.y1, x1);
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
      }} else if (mode === 'end' && anchorsX[0] && Number.isFinite(anchorsY[0])) {{
        if (compareTime(x1, anchorsX[0]) <= 0) x1 = dateAtIndex(Math.min(P.ohlc.length - 1, nearest(anchorsX[0]).idx + 1));
        x0 = anchorsX[0];
        y0 = anchorsY[0];
        obj.free_extension = true;
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
    const axisPadX = 78;
    const axisPadY = 44;
    const x = Math.min(Math.max(pt.x, pad), Math.max(pad, w - axisPadX));
    const y = Math.min(Math.max(pt.y, pad), Math.max(pad, h - axisPadY));
    return {{...pt, actualX:pt.x, actualY:pt.y, offscreen:x !== pt.x || y !== pt.y, x, y}};
  }}

  function lineObjectPoints(obj) {{
    const pts = lineDisplayValues(obj);
    if (!pts) return null;
    if (isWedgeLineObject(obj)) {{
      const anchors = lineEndpointValues(obj);
      if (!anchors) return null;
      const display = lineDisplayValues(obj) || anchors;
      const startActual = {{x: chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(anchors.x0) : null, y: candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(anchors.y0) : null}};
      const wrap = $('chart-wrap');
      const maxVisibleX = Math.max(24, (wrap?.clientWidth || 0) - 24);
      let endTime = display.x1;
      let endX = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(endTime) : null;
      if (!Number.isFinite(endX) || endX > maxVisibleX) {{
        endX = maxVisibleX;
        const raw = chart.timeScale().coordinateToTime ? chart.timeScale().coordinateToTime(endX) : null;
        endTime = typeof raw === 'string' ? raw.slice(0, 10) : (raw && Number.isFinite(raw.year) ? `${{raw.year}}-${{String(raw.month).padStart(2,'0')}}-${{String(raw.day).padStart(2,'0')}}` : addDays(P.ohlc[P.ohlc.length - 1]?.time || anchors.x1, 5));
      }}
      let endY = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(display.y1) : null;
      const anchor2 = {{x: chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(anchors.x1) : null, y: candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(anchors.y1) : null}};
      if (!Number.isFinite(endX) || !Number.isFinite(endY)) {{ endX = anchor2.x; endY = anchor2.y; endTime = anchors.x1; }}
      const endActual = {{x:endX, y:endY}};
      if (![startActual.x, startActual.y, endActual.x, endActual.y].every(Number.isFinite)) return null;
      const values = {{x0:anchors.x0, y0:anchors.y0, x1:endTime, y1:display.y1}};
      return {{start:clampLineHandlePoint(startActual), end:clampLineHandlePoint(endActual), actualStart:startActual, actualEnd:endActual, values}};
    }}
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
      updateSetupDebugPanel();
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
    if (levels.__journal_close_mode__) return false;
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
      const display = lineDisplayValues(obj);
      if (display) return projectedLineValue(display.x0, display.y0, display.x1, display.y1, time);
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
      return {{id, type:'wedge', label, x, y, x0:x[0], x1:x[x.length - 1], y0:y[0], y1:y[y.length - 1], anchor_x:anchorX, anchor_y:anchorY, price:y[y.length - 1], color, group_id:'auto-wedge', free_extension:false}};
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
    const currentSignature = [curUpperFirst, curUpperSecond, curLowerFirst, curLowerSecond].join('|');
    const sigFor = (u1, u2, l1, l2) => [u1, u2, l1, l2].join('|');
    const upperSeconds = side === 'lower' ? [curUpperSecond].filter(Number.isFinite) : [...new Set([curUpperSecond, ...Array.from({{length:Math.min(45, end)}}, (_, k) => end - 3 - k).filter(i => i > 5 && isHigh(i))])].filter(i => Number.isFinite(i) && isHigh(i));
    const lowerSeconds = side === 'upper' ? [curLowerSecond].filter(Number.isFinite) : [...new Set([curLowerSecond, ...Array.from({{length:Math.min(45, end)}}, (_, k) => end - 3 - k).filter(i => i > 5 && isLow(i))])].filter(i => Number.isFinite(i) && isLow(i));
    const candidates = [];
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
        if (side === 'both' && duration <= scoreCurrent * 1.15 && hi(u1) <= candleExtremeForDate((upperObj.anchor_x || [])[0], 'upper', 0) && lo(l1) >= candleExtremeForDate((lowerObj.anchor_x || [])[0], 'lower', Infinity)) continue;
        const widthStart = line(u1, hi(u1), u2, hi(u2), first) - line(l1, lo(l1), l2, lo(l2), first);
        const widthEnd = line(u1, hi(u1), u2, hi(u2), end) - line(l1, lo(l1), l2, lo(l2), end);
        if (widthStart <= 0 || widthEnd <= 0 || widthEnd >= widthStart * 0.95) continue;
        const signature = sigFor(u1, u2, l1, l2);
        if (signature === currentSignature) continue;
        const changedSecondIsExtreme = (side === 'lower' || isHigh(u2)) && (side === 'upper' || isLow(l2));
        if (!changedSecondIsExtreme) continue;
        const biggerThanCurrent = duration > scoreCurrent * 1.02;
        const score = duration * 10 + widthStart + (upperTouches + lowerTouches) * 15 + Math.max(0, hi(u1) - hi(u2)) + Math.max(0, lo(l2) - lo(l1));
        candidates.push({{signature, biggerThanCurrent, score, duration, upper:{{a:{{idx:u1, price:hi(u1)}}, b:{{idx:u2, price:hi(u2)}}}}, lower:{{a:{{idx:l1, price:lo(l1)}}, b:{{idx:l2, price:lo(l2)}}}}}});
      }}
    }}
    candidates.sort((a, b) => (Number(b.biggerThanCurrent) - Number(a.biggerThanCurrent)) || (b.duration - a.duration) || (b.score - a.score));
    const seen = wedgeRouletteSeen[side] || wedgeRouletteSeen.both;
    let chosen = candidates.find(c => !seen.has(c.signature));
    if (!chosen && candidates.length) {{
      seen.clear();
      chosen = candidates[0];
    }}
    if (chosen) seen.add(chosen.signature);
    return chosen || null;
  }}

  function restoreScannerWedgeFromRoulette() {{
    if (!initialScannerDrawnObjects.length) return false;
    drawnObjects = drawnObjects.filter(o => !isWedgeLineObject(o)).concat(initialScannerDrawnObjects.map(deepClone));
    wedgeRouletteNoAlternative = false;
    Object.values(wedgeRouletteSeen).forEach(s => s.clear());
    applyWedgeDerivedLevels();
    ['high', 'low', 'line_cross_value', 'stop_loss'].forEach(refreshLevelSeries);
    render();
    updateSetupDebugPanel('Restored the original scanner wedge.');
    return true;
  }}

  function findNewWedge(side='both') {{
    const candidate = findAlternativeWedgeCandidate(side);
    if (!candidate) {{
      if (side === 'both' && wedgeRouletteNoAlternative && restoreScannerWedgeFromRoulette()) return;
      wedgeRouletteNoAlternative = true;
      updateSetupDebugPanel(`No larger valid ${{side === 'upper' ? 'upper-line ' : (side === 'lower' ? 'lower-line ' : '')}}alternative wedge found. ${{side === 'both' ? 'Click 🎲 Find new wedge again to restore the scanner wedge.' : 'Current wedge was left unchanged.'}}`);
      return;
    }}
    wedgeRouletteNoAlternative = false;
    drawnObjects = drawnObjects.filter(o => !isWedgeLineObject(o)).concat(wedgeLineThroughExtremeObjects(candidate));
    applyWedgeDerivedLevels();
    ['high', 'low', 'line_cross_value', 'stop_loss'].forEach(refreshLevelSeries);
    render();
    const sizeText = candidate.biggerThanCurrent ? 'larger' : 'smaller';
    updateSetupDebugPanel(`Found and loaded the next ${{sizeText}} valid wedge alternative. Click again to loop through remaining possibilities. Save & Close to keep it for future allsearch calculations.`);
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
      const display = lineDisplayValues(obj) || anchors;
      const displayEndY = candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(display.y1) : null;
      const endSourceX = chart.timeScale().timeToCoordinate ? chart.timeScale().timeToCoordinate(display.x1) : null;
      const endSourceY = Number.isFinite(displayEndY) ? displayEndY : y1;
      const slope = Number.isFinite(endSourceX) && endSourceX !== x0 ? (endSourceY - y0) / (endSourceX - x0) : (y1 - y0) / (x1 - x0);
      let endX = endSourceX;
      if (!Number.isFinite(endX)) endX = $('chart-wrap').clientWidth || x1;
      const leftX = Math.max(0, Math.min(x0, x1));
      const rightX = Math.max(leftX, endX);
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
    const chartEl = $('chart');
    if (!canvas || !chartEl) return;
    const rect = chartEl.getBoundingClientRect();
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
      const series = addLine([{{time:x0, value:pt.plot_price ?? pt.price}}, {{time:x1, value:pt.plot_price ?? pt.price}}], levelColors[field] || '#94a3b8', 1.15, LightweightCharts.LineStyle.Solid, `${{labels[field]}}: ${{fmt(pt.price)}}`, true, false, false, `level:${{field}}`, deleteFn, false);
      if (series) levelSeries.set(field, series);
      if (field === 'entry') {{
        const entrySeries = addLine([{{time:pt.date, value:pt.price}}], levelColors[field], 1.35, LightweightCharts.LineStyle.Solid, '', false, false, false, 'level:entry-point', null, false);
        if (entrySeries) levelSeries.set('entry-point', entrySeries);
      }}
    }});
    (levels.__half_points__ || []).forEach((pt, i) => {{
      const series = addLine([{{time:pt.date, value:pt.price}}], '#a855f7', 1.15, LightweightCharts.LineStyle.Solid, 'Half point', true, false, false, `half:${{i}}`, null, false);
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
    $('values-panel').innerHTML = seq.map(k => `<div class="value-tile ${{k}}"><div class="value-label">${{labels[k]}}</div><div class="value-number">${{levels[k] == null ? '--' : fmt(levels[k])}}</div></div>`).join('');
    const picker = $('object-picker'); picker.innerHTML = '<option value="">-- select --</option>';
    const resetScannerBtn = $('reset-scanner-drawings');
    if (resetScannerBtn) resetScannerBtn.style.display = initialScannerDrawnObjects.length ? 'block' : 'none';
    const hasWedgeObjects = drawnObjects.some(isWedgeLineObject);
    const setupInfoBtn = $('setup-debug-btn');
    if (setupInfoBtn) {{
      const tech = selectedJournalTechnique();
      const showInfo = ['Kliny', 'Ichimoku', 'Fibo'].includes(tech);
      setupInfoBtn.style.display = showInfo ? 'flex' : 'none';
      setupInfoBtn.querySelector('span:last-child').textContent = `${{tech}} information`;
      setupInfoBtn.closest('.action-grid')?.classList.toggle('no-wedge', !showInfo);
    }}
    const findNewWedgeBtn = $('find-new-wedge');
    if (findNewWedgeBtn) findNewWedgeBtn.style.display = hasWedgeObjects ? 'block' : 'none';
    ['find-new-upper-wedge', 'find-new-lower-wedge'].forEach(id => {{ const btn = $(id); if (btn) btn.style.display = hasWedgeObjects ? 'block' : 'none'; }});
    const seenFib = new Set();
    drawnObjects.forEach((obj, idx) => {{
      if (obj.type === 'fib' && obj.group_id) {{ if (seenFib.has(obj.group_id)) return; seenFib.add(obj.group_id); picker.add(new Option(`FIB group (${{String(obj.group_id).slice(0,8)}})`, `fib-group:${{obj.group_id}}`)); return; }}
      picker.add(new Option(`${{obj.label || 'OBJ'}} (${{String(obj.id || idx).slice(0,8)}})`, obj.id || `obj-index:${{idx}}`));
    }});
    updateSetupDebugPanel();
  }}

  const FX_TO_PLN = {{PLN:1, USD:3.92, EUR:4.25, GBP:5.05}};

  function setCalculationCurrencyButtons(currency) {{
    const target = String(currency || 'PLN').toUpperCase();
    document.querySelectorAll('#calculation-currency-buttons button[data-currency]').forEach(btn => btn.classList.toggle('active', btn.dataset.currency === target));
  }}

  function convertMoneyField(id, fromCurrency, toCurrency, digits=2) {{
    const el = $(id);
    if (!el || el.disabled) return;
    const value = Number(el.value || 0);
    if (!Number.isFinite(value) || value === 0) return;
    const fromRate = FX_TO_PLN[fromCurrency] || 1;
    const toRate = FX_TO_PLN[toCurrency] || 1;
    el.value = Number((value * fromRate / toRate).toFixed(digits));
  }}

  function changeCalculationCurrency(toCurrency, convert=true) {{
    const to = String(toCurrency || 'PLN').toUpperCase();
    const from = String($('calculation-currency').value || levels.calculation_currency || 'PLN').toUpperCase();
    if (to === from) {{ setCalculationCurrencyButtons(to); return; }}
    if (convert) {{
      convertMoneyField('capital', from, to, 2);
      convertMoneyField('lot-cost', from, to, 2);
      convertMoneyField('pip-value', from, to, 4);
    }}
    $('calculation-currency').value = to;
    levels.calculation_currency = to;
    setCalculationCurrencyButtons(to);
    applyInstrumentControls();
    if ($('calc-drawer').classList.contains('open')) calculatePosition(true);
  }}

  function applyInstrumentControls() {{
    const stockCfdOn = !!levels.__stock_cfd_mode__;
    const originalIsStock = P.instrumentType === 'stock' || stockCfdOn;
    const disabled = originalIsStock && !stockCfdOn;
    const sourceUpper = String(P.sourceTicker || '').toUpperCase();
    const symbolUpper = String(P.symbol || '').toUpperCase();
    const indexLike = P.instrumentType === 'commodity' && ['^','DE40','US500','US100','US30','JP225','WIG20','UK100','EU50','DAX','CAC','AEX','SMI','IBEX'].some(t => sourceUpper.includes(t) || symbolUpper.includes(t));
    $('identity').textContent = `${{P.sourceName || P.symbol}}${{P.sourceTicker ? ` (${{P.sourceTicker}})` : ''}}`;
    $('instrument-title').textContent = `${{originalIsStock && stockCfdOn ? 'STOCK CFD' : (indexLike ? 'COMMODITY/INDEX' : P.instrumentType.toUpperCase())}}`;
    $('source').textContent = `${{P.sourceProvider}}`;
    $('stock-cfd-toggle').style.display = originalIsStock ? 'flex' : 'none';
    $('stock-cfd-toggle').textContent = `${{stockCfdOn ? 'ON' : 'OFF'}}`;
    $('stock-cfd-toggle').classList.toggle('active', stockCfdOn);
    const instrumentCurrency = () => {{
      const source = String(P.sourceTicker || P.symbol || '').toUpperCase();
      if (source.endsWith('.US') || source.endsWith('.F') || source.includes('USD')) return 'USD';
      if (source.endsWith('.DE') || source.endsWith('.FR') || source.endsWith('.NL') || source.endsWith('.ES') || source.endsWith('.IT') || source.includes('EUR')) return 'EUR';
      if (source.endsWith('.L') || source.includes('GBP')) return 'GBP';
      return 'PLN';
    }};
    const selectedCurrency = String($('calculation-currency')?.value || levels.calculation_currency || 'PLN').toUpperCase();
    const stockCurrencyMatches = originalIsStock && !stockCfdOn && selectedCurrency === instrumentCurrency();
    const feeEligible = !!levels.__currency_fee_eligible__ && !stockCurrencyMatches;
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
    $('currency-fee-toggle').style.display = feeEligible ? 'block' : 'none';
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
  $('position-type').value = levels.position_type || 'long'; $('capital').value = levels.capital || 255000; $('calculation-currency').value = levels.calculation_currency || levels.currency || 'PLN'; setCalculationCurrencyButtons($('calculation-currency').value);
  $('lot-cost').value = levels.lot_cost && levels.lot_cost !== 0 ? levels.lot_cost : ''; $('pip-value').value = levels.__stock_cfd_mode__ ? 1 : ((levels.pip_value && levels.pip_value !== 0) ? levels.pip_value : '');
  $('spread-mult').value = levels.spread_multiplier && levels.spread_multiplier !== 0 ? levels.spread_multiplier : '';
  $('tool-line').onclick = () => {{ const same = activeTool === 'line'; clearPreviews(); activeTool=same ? 'level' : 'line'; activeField=null; fibAnchor=halfAnchor=null; updatePanel(); }};
  $('tool-fib').onclick = () => {{ const same = activeTool === 'fib'; clearPreviews(); activeTool=same ? 'level' : 'fib'; activeField=null; lineAnchor=halfAnchor=null; updatePanel(); }};
  $('tool-half').onclick = () => {{ const same = activeTool === 'half'; clearPreviews(); activeTool=same ? 'level' : 'half'; activeField=null; lineAnchor=fibAnchor=null; updatePanel(); }};
  document.querySelectorAll('.color-dot').forEach(b => b.onclick = () => lineColor = b.dataset.color);
  $('ichimoku-toggle').onclick = () => {{ levels.__show_ichimoku__ = !levels.__show_ichimoku__; render(); }};
  $('reset-all').onclick = () => {{ levels = {{}}; levelPoints = {{}}; drawnObjects = []; lineAnchor=fibAnchor=halfAnchor=null; activeTool='level'; activeField=null; $('calculation-currency').value='PLN'; setCalculationCurrencyButtons('PLN'); render(); applyInstrumentControls(); }};
  $('stock-cfd-toggle').onclick = () => {{ levels.__stock_cfd_mode__ = !levels.__stock_cfd_mode__; if (levels.__stock_cfd_mode__) $('pip-value').value = 1; applyInstrumentControls(); }};
  $('currency-fee-toggle').onclick = () => {{ levels.apply_currency_conversion_fee = !levels.apply_currency_conversion_fee; applyInstrumentControls(); if ($('calc-drawer').classList.contains('open')) calculatePosition(true); }};
  document.querySelectorAll('#calculation-currency-buttons button[data-currency]').forEach(btn => btn.onclick = () => changeCalculationCurrency(btn.dataset.currency || 'PLN', true));
  $('setup-debug-btn').onclick = () => copySetupDebug();
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
    wedgeRouletteNoAlternative = false;
    Object.values(wedgeRouletteSeen).forEach(s => s.clear());
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
      const series = addLine([{{time:x0, value:pt.plot_price ?? pt.price}}, {{time:x1, value:pt.plot_price ?? pt.price}}], levelColors[field] || '#94a3b8', 1.15, LightweightCharts.LineStyle.Solid, `${{labels[field]}}: ${{fmt(pt.price)}}`, true, false, false, `level:${{field}}`, deleteFn, false);
      if (series) levelSeries.set(field, series);
      if (field === 'entry') {{
        const entrySeries = addLine([{{time:pt.date, value:pt.price}}], levelColors[field], 1.35, LightweightCharts.LineStyle.Solid, '', false, false, false, 'level:entry-point', null, false);
        if (entrySeries) levelSeries.set('entry-point', entrySeries);
      }}
    }}
    updatePanel();
    requestAnimationFrame(drawCloud);
  }}

  function refreshHalfSeries() {{
    [...levelSeries.keys()].filter(k => String(k).startsWith('half:')).forEach(forgetLevelSeries);
    (levels.__half_points__ || []).forEach((pt, i) => {{
      const series = addLine([{{time:pt.date, value:pt.price}}], '#a855f7', 1.15, LightweightCharts.LineStyle.Solid, 'Half point', true, false, false, `half:${{i}}`, null, false);
      if (series) levelSeries.set(`half:${{i}}`, series);
    }});
    updatePanel();
    requestAnimationFrame(drawCloud);
  }}

  chart.subscribeClick(param => {{
    if (levels.__journal_close_mode__) return;
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


  function activeJournalTechnique() {{
    if (levels.__journal_source_technique__) return levels.__journal_source_technique__;
    if (drawnObjects.some(isWedgeLineObject)) return 'Kliny';
    if (drawnObjects.some(obj => obj.type === 'fib' || obj.type === 'fib-boundary')) return 'Fibo';
    if (levels.__show_ichimoku__) return 'Ichimoku';
    return 'Manual';
  }}
  function selectedJournalTechnique() {{
    return $('journal-technique')?.value || activeJournalTechnique();
  }}
  const journalReasonOptions = {{
    Kliny: [
      ['wedge_breakout', 'Wedge breakout'],
      ['wedge_retest', 'Wedge retest'],
      ['wedge_stop_loss', 'Wedge stop loss review'],
      ['manual', 'Manual']
    ],
    Ichimoku: [
      ['ichimoku_cloud_breakout', 'Cloud breakout'],
      ['ichimoku_retest_pattern', 'Retest + candle pattern']
    ],
    Fibo: [
      ['fibo_618_pattern', 'Fibo 61.8 + candle pattern']
    ],
    Manual: [
      ['manual', 'Manual'],
      ['stop_loss_review', 'Stop loss review'],
      ['other', 'Other']
    ]
  }};
  function reasonOptionsForTechnique(tech) {{
    return journalReasonOptions[tech] || journalReasonOptions.Manual;
  }}
  function candlePatternLabel() {{
    const last = ohlc[ohlc.length - 1] || {{}};
    const open = Number(last.open), high = Number(last.high), low = Number(last.low), close = Number(last.close);
    if (![open, high, low, close].every(Number.isFinite)) return 'candle pattern';
    const body = Math.abs(close - open);
    const range = Math.max(0.000001, high - low);
    const upper = high - Math.max(open, close);
    const lower = Math.min(open, close) - low;
    if (lower > body * 2 && upper < range * 0.35) return close >= open ? 'bullish hammer' : 'hammer';
    if (upper > body * 2 && lower < range * 0.35) return close <= open ? 'bearish shooting star' : 'shooting star';
    if (body / range < 0.18) return 'doji';
    return close >= open ? 'bullish candle' : 'bearish candle';
  }}
  function reasonLabel(value, label) {{
    if (String(value).startsWith('ichimoku_retest') || String(value).startsWith('fibo_')) return label.replace('candle pattern', candlePatternLabel());
    return label;
  }}
  function setJournalReasonOptions(tech, preferred=null) {{
    const reason = $('journal-reason');
    if (!reason) return;
    const oldValue = preferred || reason.value;
    const opts = reasonOptionsForTechnique(tech);
    reason.innerHTML = opts.map(([value, label]) => `<option value="${{value}}">${{reasonLabel(value, label)}}</option>`).join('');
    reason.value = opts.some(([value]) => value === oldValue) ? oldValue : opts[0][0];
  }}
  function activeJournalReason() {{
    const tech = activeJournalTechnique();
    return reasonOptionsForTechnique(tech)[0][0];
  }}
  function reasonUsesTouches(reasonValue) {{
    return String(reasonValue || '').startsWith('wedge_');
  }}
  function updateJournalTouchesVisibility() {{
    const row = $('journal-touches-row');
    const touches = $('journal-touches');
    const visible = reasonUsesTouches($('journal-reason')?.value);
    if (row) row.style.display = visible ? 'block' : 'none';
    if (touches && !visible && !touches.dataset.manual) touches.value = '';
  }}
  function wedgeTouchCountsBySide() {{
    const counts = {{upper:new Set(), lower:new Set()}};
    drawnObjects.filter(isWedgeLineObject).forEach(obj => {{
      const side = wedgeSide(obj) === 'upper' ? 'upper' : 'lower';
      wedgeTouchPoints(obj).forEach(pt => counts[side].add(`${{pt.time}}|${{Number(pt.value).toFixed(6)}}`));
    }});
    return {{upper:counts.upper.size, lower:counts.lower.size}};
  }}
  function wedgeTouchCountText() {{
    const c = wedgeTouchCountsBySide();
    return `upper ${{c.upper}} / lower ${{c.lower}}`;
  }}
  function autoJournalNotes() {{
    const lines = [];
    lines.push(`Auto context: ${{selectedJournalTechnique()}} / ${{($('journal-reason') && $('journal-reason').selectedOptions[0]?.textContent) || ''}}`);
    lines.push(`Direction: ${{($('position-type') && $('position-type').value) || ''}}`);
    ['entry','stop_loss','check_zr_value_fibo_or_elevation','line_cross_value','high','low'].forEach(k => {{ if (levels[k] != null) lines.push(`${{labels[k] || k}}: ${{fmt(levels[k])}}`); }});
    if (reasonUsesTouches($('journal-reason')?.value)) lines.push(`Wedge touches: ${{wedgeTouchCountText()}}`);
    if (levels.position_calculations?.ok) {{
      const b = levels.position_calculations.basics || {{}};
      if (Number.isFinite(Number(b.max_capital))) lines.push(`Calculated capital: ${{money(b.max_capital, levels.position_calculations.currency || 'PLN')}}`);
      if (levels.position_calculations.risk_reward != null) lines.push(`Risk/reward: ${{numText(levels.position_calculations.risk_reward, 2)}}:1`);
    }}
    return lines.join('\\n');
  }}
  function autofillJournal(force=false) {{
    const tech = $('journal-technique'), reason = $('journal-reason'), touches = $('journal-touches'), notes = $('journal-notes');
    if (tech && (force || !tech.dataset.manual)) tech.value = activeJournalTechnique();
    setJournalReasonOptions(tech?.value || activeJournalTechnique(), (force || !reason?.dataset.manual) ? activeJournalReason() : reason?.value);
    updateJournalTouchesVisibility();
    if (touches && (force || !touches.dataset.manual) && reasonUsesTouches(reason?.value)) touches.value = wedgeTouchCountText();
  }}
  function journalScreenshotRange() {{
    const idxs = [];
    drawnObjects.forEach(obj => {{
      [...(obj.x || []), obj.x0, obj.x1, obj.time, obj.date].filter(Boolean).forEach(t => {{
        const row = ohlcByTime.get(String(t).slice(0, 10));
        if (row && Number.isFinite(row.idx)) idxs.push(row.idx);
      }});
    }});
    ['entry','stop_loss','check_zr_value_fibo_or_elevation','line_cross_value'].forEach(k => {{ if (levels[k] != null && ohlc.length) idxs.push(ohlc.length - 1); }});
    if (selectedJournalTechnique() === 'Ichimoku' || levels.__show_ichimoku__) {{
      ['tenkan','kijun','spanA','spanB','chikou'].forEach(k => (P.ichimoku?.[k] || []).forEach(pt => {{
        const row = ohlcByTime.get(String(pt.time).slice(0, 10));
        if (row && Number.isFinite(row.idx)) idxs.push(row.idx);
      }}));
    }}
    if (!idxs.length) return null;
    const pad = Math.max(24, Math.round(ohlc.length * ((selectedJournalTechnique() === 'Ichimoku' || levels.__show_ichimoku__) ? 0.12 : 0.07)));
    return {{from: Math.max(0, Math.min(...idxs) - pad), to: Math.min(Math.max(ohlc.length - 1, 0) + 8, Math.max(...idxs) + pad)}};
  }}
  async function withZoomedJournalViewport(fn) {{
    const ts = chart.timeScale();
    const previous = ts.getVisibleLogicalRange ? ts.getVisibleLogicalRange() : null;
    const range = journalScreenshotRange();
    try {{
      if (range && ts.setVisibleLogicalRange) ts.setVisibleLogicalRange(range);
      else if (ts.fitContent) ts.fitContent();
    }} catch(e) {{ console.warn('journal screenshot zoom failed', e); }}
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    try {{ return await fn(); }} finally {{ if (previous && ts.setVisibleLogicalRange) requestAnimationFrame(() => {{ try {{ ts.setVisibleLogicalRange(previous); }} catch(e) {{}} requestAnimationFrame(drawCloud); }}); }}
  }}
  async function captureJournalScreenshot(calcData=null) {{
    return withZoomedJournalViewport(async () => {{
      drawCloud();
      await new Promise(resolve => requestAnimationFrame(resolve));
      let base = null;
      try {{ base = chart.takeScreenshot(true, false); }} catch(e) {{ base = null; }}
      const overlay = $('cloud-overlay');
      if (!base || !base.width || !base.height) return null;
      const drawerHeight = calcData && calcData.ok ? 190 : 0;
      const canvas = document.createElement('canvas');
      canvas.width = base.width;
      canvas.height = base.height + drawerHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(base, 0, 0);
      if (overlay && overlay.width && overlay.height) ctx.drawImage(overlay, 0, 0, base.width, base.height);
      if (drawerHeight) {{
        const y0 = base.height;
        const b = calcData.basics || {{}};
        const currency = calcData.currency || 'PLN';
        const reasonText = $('journal-reason')?.selectedOptions?.[0]?.textContent || '';
        const lines = [
          ['Instrument', calcData.instrument_type || P.instrumentType || P.symbol],
          ['Position', String(calcData.position_type || $('position-type').value || '').toUpperCase()],
          ['Entry', Number.isFinite(Number(b.entry)) ? fmt(Number(b.entry)) : ''],
          ['Stop loss', Number.isFinite(Number(b.stop_loss)) ? fmt(Number(b.stop_loss)) : ''],
          ['Max capital', Number.isFinite(Number(b.max_capital)) ? money(b.max_capital, currency) : ''],
          ['Setup', reasonText],
          ['Risk/reward', calcData.risk_reward != null ? `${{numText(calcData.risk_reward, 2)}}:1` : ''],
          ['Profit', calcData.profit != null ? `${{money(calcData.profit, currency)}} (${{numText(calcData.profit_percent, 2)}}%)` : '']
        ].filter(([,v]) => v !== '');
        const grad = ctx.createLinearGradient(0, y0, canvas.width, y0 + drawerHeight);
        grad.addColorStop(0, '#071426'); grad.addColorStop(1, '#0f172a');
        ctx.fillStyle = grad; ctx.fillRect(0, y0, canvas.width, drawerHeight);
        ctx.strokeStyle = '#38bdf8'; ctx.globalAlpha = .45; ctx.strokeRect(0.5, y0 + 0.5, canvas.width - 1, drawerHeight - 1); ctx.globalAlpha = 1;
        ctx.fillStyle = '#f8fafc'; ctx.font = 'bold 20px Inter, Arial'; ctx.fillText('Position calculation', 18, y0 + 32);
        ctx.font = '13px ui-monospace, Menlo, monospace';
        lines.forEach(([k, v], i) => {{
          const x = 18 + (i % 4) * Math.floor(canvas.width / 4);
          const y = y0 + 62 + Math.floor(i / 4) * 46;
          ctx.fillStyle = '#93c5fd'; ctx.fillText(String(k).toUpperCase(), x, y);
          ctx.fillStyle = '#e5e7eb'; ctx.font = 'bold 15px ui-monospace, Menlo, monospace'; ctx.fillText(String(v).slice(0, 32), x, y + 20); ctx.font = '13px ui-monospace, Menlo, monospace';
        }});
      }}
      return canvas.toDataURL('image/png');
    }});
  }}
  function journalPayload() {{
    autofillJournal(false);
    const reasonText = $('journal-reason')?.selectedOptions?.[0]?.textContent || '';
    const preview = [
      'Instrument: ' + P.symbol,
      'Technique: ' + (($('journal-technique') && $('journal-technique').value) || ''),
      'Direction: ' + (($('position-type') && $('position-type').value) || ''),
      'Amount: ' + (($('journal-amount') && $('journal-amount').value) || '') + ' ' + (($('journal-currency') && $('journal-currency').value) || 'PLN'),
      'Entry: ' + (levels.entry || ''),
      'Stop loss: ' + (levels.stop_loss || ''),
      'Take profit/check: ' + (levels.check_zr_value_fibo_or_elevation || ''),
      'Reason: ' + reasonText,
      ...(reasonUsesTouches($('journal-reason')?.value) ? ['Touches: ' + (($('journal-touches') && $('journal-touches').value) || '')] : []),
      '',
      (($('journal-notes') && $('journal-notes').value) || '')
    ].join('\\n');
    if ($('journal-preview')) $('journal-preview').textContent = preview;
    return {{
      symbol: P.symbol,
      sourceTicker: P.sourceTicker || '',
      instrumentType: P.instrumentType || '',
      technique: (($('journal-technique') && $('journal-technique').value) || ''),
      direction: (($('position-type') && $('position-type').value) || ''),
      amount: (($('journal-amount') && $('journal-amount').value) || ''),
      amount_currency: (($('journal-currency') && $('journal-currency').value) || 'PLN'),
      entry: levels.entry || '',
      stop_loss: levels.stop_loss || '',
      take_profit: levels.check_zr_value_fibo_or_elevation || '',
      line_cross_value: levels.line_cross_value || '',
      high: levels.high || '',
      low: levels.low || '',
      reason: (($('journal-reason') && $('journal-reason').value) || ''),
      reason_label: reasonText,
      pattern: reasonText,
      touches: reasonUsesTouches($('journal-reason')?.value) ? (($('journal-touches') && $('journal-touches').value) || '') : '',
      notes: (($('journal-notes') && $('journal-notes').value) || ''),
      preview,
      levels: collectLevelsForSave(false)
    }};
  }}
  function bindJournal() {{
    const toggle = $('journal-toggle-btn');
    if (!toggle) return;
    toggle.onclick = () => {{ const p = $('journal-panel'); const card = p?.closest('.manual-card'); const opening = p.style.display === 'none'; p.style.display = opening ? 'block' : 'none'; card?.classList.toggle('journal-open', opening); if (opening) autofillJournal(false); journalPayload(); }};
    const closePanel = $('journal-close-panel');
    if (closePanel) closePanel.onclick = () => {{ const p = $('journal-panel'); p.style.display = 'none'; p.closest('.manual-card')?.classList.remove('journal-open'); }};
    ['journal-technique','journal-reason','journal-touches','journal-notes'].forEach(id => {{ const el=$(id); if(el) el.addEventListener('input', () => {{ el.dataset.manual='1'; journalPayload(); }}); if(el) el.addEventListener('change', () => {{ el.dataset.manual='1'; if(id==='journal-technique') {{ const reason=$('journal-reason'); if (reason) delete reason.dataset.manual; setJournalReasonOptions(el.value, activeJournalReason()); }} updateJournalTouchesVisibility(); if(id==='journal-reason' && reasonUsesTouches(el.value) && $('journal-touches') && !$('journal-touches').dataset.manual) $('journal-touches').value = wedgeTouchCountText(); journalPayload(); }}); }});
    ['journal-amount','position-type'].forEach(id => {{ const el=$(id); if(el) el.addEventListener('input', journalPayload); if(el) el.addEventListener('change', journalPayload); }});
    document.querySelectorAll('#journal-currency-buttons button[data-currency]').forEach(btn => btn.onclick = () => {{ $('journal-currency').value = btn.dataset.currency || 'PLN'; document.querySelectorAll('#journal-currency-buttons button').forEach(b => b.classList.toggle('active', b === btn)); journalPayload(); }});
    document.querySelector('#journal-currency-buttons button[data-currency="PLN"]')?.classList.add('active');
    const save = $('journal-save-btn');
    if (save) save.onclick = async () => {{
      const calc = await calculatePosition(false);
      if (calc && calc.ok) levels.position_calculations = calc;
      autofillJournal(false);
      const payload = journalPayload();
      payload.screenshot = await captureJournalScreenshot(calc);
      const resp = await fetch('/journal-entry', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(payload)}});
      const data = await resp.json();
      $('result-box').textContent = data.ok ? ('Journal saved: ' + data.id) : ('Journal save failed: ' + (data.error || resp.status));
    }};
  }}

  function collectLevelsForSave(finished=false) {{
    const stockCfdMode = !!levels.__stock_cfd_mode__;
    const pipValue = stockCfdMode ? 1 : Number($('pip-value').value || 0);
    const spreadMult = Number($('spread-mult').value || 0);
    return {{...levels,
      position_type:$('position-type').value,
      capital:roundPrice(Number($('capital').value || 255000)),
      calculation_currency:String($('calculation-currency').value || 'PLN').toUpperCase(),
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


  function setupJournalCloseMode() {{
    const cfg = levels || {{}};
    if (!cfg.__journal_close_mode__) return;
    document.body.classList.add('close-mode');
    const soldInput = $('close-mode-price');
    const entryInput = $('close-mode-entry');
    const slInput = $('close-mode-stop-loss');
    const directionInput = $('close-mode-direction');
    const saveBtn = $('close-mode-save');
    const statusEl = $('close-mode-status');
    const first = ohlc[0]?.time, last = ohlc[ohlc.length - 1]?.time;
    const asNum = (value, fallback=null) => {{ const n=Number(String(value ?? '').replace(',','.')); return Number.isFinite(n) ? n : fallback; }};
    const latestClose = asNum(ohlc[ohlc.length - 1]?.close, 0);
    const initialEntry = asNum(cfg.__journal_entry_price__ || cfg.entry, latestClose);
    const initialSold = asNum(cfg.__journal_close_price__ || cfg.exit_price, latestClose);
    const initialSl = asNum(cfg.__journal_stop_loss__ || cfg.stop_loss, null);
    if (soldInput) soldInput.value = Number.isFinite(initialSold) ? initialSold : '';
    if (entryInput) entryInput.value = Number.isFinite(initialEntry) ? initialEntry : '';
    if (slInput) slInput.value = Number.isFinite(initialSl) ? initialSl : '';
    if (directionInput) directionInput.value = (cfg.__journal_direction__ || cfg.direction || cfg.position_type || 'long') === 'short' ? 'short' : 'long';
    let activeLine = 'sold';
    let dragLine = null;
    const lines = {{
      sold: {{input:soldInput, color:'#22c55e', width:3, label:'SOLD', series:null, marker:null}},
      entry: {{input:entryInput, color:'#60a5fa', width:2, label:'ENTRY', series:null, marker:null}},
      sl: {{input:slInput, color:'#ef4444', width:2, label:'SL', series:null, marker:null}},
    }};
    Object.values(lines).forEach(line => {{
      line.series = addLineSeries({{color:line.color, lineWidth:line.width, priceLineVisible:true, lastValueVisible:true, title:line.label, autoscaleInfoProvider:() => null}});
      line.marker = addLineSeries({{color:line.color, lineWidth:1, priceLineVisible:false, lastValueVisible:false, title:'', autoscaleInfoProvider:() => null}});
    }});
    function linePrice(key) {{ return asNum(lines[key]?.input?.value, null); }}
    function setActiveLine(key) {{
      if (!lines[key]) return;
      activeLine = key;
      document.querySelectorAll('.close-line-control').forEach(el => el.classList.toggle('active', el.dataset.line === key));
    }}
    function lineStartTime(key, price) {{
      if (!Array.isArray(ohlc) || !ohlc.length) return first;
      let idx = Math.max(0, ohlc.length - 45);
      for (let i = ohlc.length - 1; i >= 0; i--) {{
        const row = ohlc[i] || {{}};
        const hi = Number(row.high);
        const lo = Number(row.low);
        if (Number.isFinite(hi) && Number.isFinite(lo) && price >= Math.min(lo, hi) && price <= Math.max(lo, hi)) {{
          idx = i;
          break;
        }}
      }}
      return ohlc[idx]?.time || first;
    }}
    function drawLine(key) {{
      const line = lines[key];
      const p = linePrice(key);
      if (!line || !Number.isFinite(p) || !first || !last) return;
      const startTime = lineStartTime(key, p);
      line.series.setData(normalizeLineData([{{time:startTime,value:p}},{{time:last,value:p}}]));
      line.marker.setData([{{time:last,value:p}}]);
      try {{ line.marker.setMarkers([{{time:last, position:'inBar', color:line.color, shape:key==='sold'?'circle':'square', text:line.label+' @ '+fmt(p)}}]); }} catch(e) {{}}
    }}
    function drawAllLines() {{ Object.keys(lines).forEach(drawLine); }}
    function setLineFromY(key, y) {{
      let p = null;
      try {{ p = candleSeries.coordinateToPrice ? candleSeries.coordinateToPrice(y) : chart.priceScale('right').coordinateToPrice(y); }} catch(e) {{ p = null; }}
      if (Number.isFinite(Number(p)) && lines[key]?.input) {{ lines[key].input.value = fmt(Number(p)); drawLine(key); }}
    }}
    function lineY(key) {{
      const p = linePrice(key);
      if (!Number.isFinite(p)) return null;
      try {{ return candleSeries.priceToCoordinate ? candleSeries.priceToCoordinate(p) : chart.priceScale('right').priceToCoordinate(p); }} catch(e) {{ return null; }}
    }}
    function nearestLine(y) {{
      let best=null, dist=Infinity;
      Object.keys(lines).forEach(key => {{ const ly=lineY(key); if (Number.isFinite(ly)) {{ const d=Math.abs(ly-y); if (d<dist) {{ best=key; dist=d; }} }} }});
      return dist <= 14 ? best : null;
    }}
    document.querySelectorAll('.close-line-control[data-line]').forEach(el => {{
      el.addEventListener('pointerdown', () => setActiveLine(el.dataset.line));
      el.addEventListener('click', () => setActiveLine(el.dataset.line));
    }});
    Object.entries(lines).forEach(([key,line]) => line.input?.addEventListener('input', () => {{ setActiveLine(key); drawLine(key); }}));
    drawAllLines();
    const wrap = $('chart-wrap');
    wrap?.addEventListener('pointerdown', ev => {{
      if (!document.body.classList.contains('close-mode') || ev.button !== 0) return;
      const rect = wrap.getBoundingClientRect();
      const hit = nearestLine(ev.clientY - rect.top);
      if (!hit) return;
      dragLine = hit;
      setActiveLine(hit);
      wrap.setPointerCapture?.(ev.pointerId);
      ev.preventDefault();
    }}, true);
    wrap?.addEventListener('pointermove', ev => {{
      if (!dragLine) return;
      const rect = wrap.getBoundingClientRect();
      setLineFromY(dragLine, ev.clientY - rect.top);
      ev.preventDefault();
    }}, true);
    const endDrag = ev => {{ if (!dragLine) return; dragLine=null; wrap?.releasePointerCapture?.(ev.pointerId); }};
    wrap?.addEventListener('pointerup', endDrag, true);
    wrap?.addEventListener('pointercancel', endDrag, true);
    chart.subscribeClick((param) => {{
      if (!document.body.classList.contains('close-mode') || !param.point || dragLine) return;
      setLineFromY(activeLine, Number(param.point.y));
    }});
    saveBtn.onclick = async () => {{
      drawAllLines();
      let screenshot = '';
      try {{ screenshot = chart.takeScreenshot(true, false).toDataURL('image/png'); }} catch(e) {{ console.warn('close screenshot failed', e); }}
      const entry = linePrice('entry');
      const sold = linePrice('sold');
      let direction = String(directionInput?.value || cfg.__journal_direction__ || cfg.direction || cfg.position_type || '').toLowerCase();
      if (direction !== 'short' && direction !== 'long') {{ const sl=linePrice('sl'); direction = Number.isFinite(sl) && Number.isFinite(entry) && sl > entry ? 'short' : 'long'; }}
      const outcome = Number.isFinite(entry) && Number.isFinite(sold) ? ((direction === 'short' ? sold <= entry : sold >= entry) ? 'profit' : 'loss') : 'closed';
      const resp = await fetch('/journal-close-from-chart', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{id:cfg.__journal_entry_id__ || '', outcome, direction, entry:entryInput?.value || '', exit_price:soldInput?.value || '', stop_loss:slInput?.value || '', screenshot}})}});
      const data = await resp.json().catch(()=>({{ok:false}}));
      const msg = data.ok ? 'Closing screenshot saved. Closing chart...' : ('Closing screenshot failed: '+(data.error||resp.status));
      if (statusEl) statusEl.textContent = msg;
      if ($('result-box')) $('result-box').textContent = msg;
      if (data.ok) setTimeout(() => {{ fetch('/shutdown', {{method:'POST', keepalive:true}}); try {{ window.close(); }} catch(e) {{}} }}, 550);
    }};
    requestAnimationFrame(() => {{ try {{ chart.timeScale().fitContent(); }} catch(e) {{}} resizeChartToContainer(); }});
  }}
  setupJournalCloseMode();

  bindJournal();
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
        requested_currency = str(levels.get("calculation_currency") or levels.get("currency") or "PLN").upper()
        currency = requested_currency if requested_currency in {"PLN", "USD", "EUR", "GBP"} else "PLN"

        def _instrument_currency() -> str:
            source = str(self.source_ticker or self.symbol or "").upper()
            if source.endswith(".US") or source.endswith(".F") or "USD" in source:
                return "USD"
            if source.endswith((".DE", ".FR", ".NL", ".ES", ".IT")) or "EUR" in source:
                return "EUR"
            if source.endswith(".L") or "GBP" in source:
                return "GBP"
            return "PLN"

        if entry <= 0 or capital <= 0 or stop_loss <= 0:
            return {"ok": False, "error": "Select entry, stop loss, and capital before calculating."}

        try:
            stock_currency_matches = effective_instrument == "stock" and currency == _instrument_currency()
            fx_fee_applicable = bool(levels.get("__currency_fee_eligible__")) and not stock_currency_matches
            if effective_instrument == "stock":
                conversion_fee_pct = float(levels.get("currency_conversion_fee_pct", 0.01) or 0.01) if fx_fee_applicable and levels.get("apply_currency_conversion_fee") else 0.0
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
                "fx_conversion_fee_applicable": fx_fee_applicable,
                "fx_conversion_fee_enabled": bool(levels.get("apply_currency_conversion_fee")) and fx_fee_applicable,
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

        @app.route("/journal-entry", methods=["POST"])
        def _journal_entry():
            payload = request.get_json(silent=True) or {}
            try:
                from journal import save_entry
                entry = save_entry(payload)
                return jsonify({"ok": True, "id": entry.get("id")})
            except Exception as exc:
                return jsonify({"ok": False, "error": str(exc)}), 500

        @app.route("/journal-close-from-chart", methods=["POST"])
        def _journal_close_from_chart():
            payload = request.get_json(silent=True) or {}
            try:
                from journal import close_entry, update_entry
                entry_id = str(payload.get("id") or "")
                if payload.get("entry") not in (None, ""):
                    update_entry(entry_id, {"entry": str(payload.get("entry") or ""), "direction": str(payload.get("direction") or "")})
                entry = close_entry(
                    entry_id,
                    str(payload.get("outcome") or "closed"),
                    "",
                    str(payload.get("exit_price") or ""),
                    str(payload.get("screenshot") or ""),
                    "manual",
                    "",
                    str(payload.get("stop_loss") or ""),
                    str(payload.get("direction") or ""),
                )
                return jsonify({"ok": bool(entry), "entry": entry})
            except Exception as exc:
                return jsonify({"ok": False, "error": str(exc)}), 500

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
