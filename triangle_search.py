from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from io import StringIO
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from chart_program.chart_loader import load_or_update_daily_data

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PROJECT_ROOT / "chart_program" / "data"
INDEX_CACHE_DIR = DATA_ROOT / "index_tickers"
RESULT_DIR = DATA_ROOT / "triangle_search"


@dataclass
class TrendLine:
    first_idx: int
    second_idx: int
    first_value: float
    second_value: float

    @property
    def slope(self) -> float:
        span = self.second_idx - self.first_idx
        return 0.0 if span == 0 else (self.second_value - self.first_value) / span

    def value_at(self, idx: int) -> float:
        return self.first_value + self.slope * (idx - self.first_idx)


@dataclass
class TriangleCandidate:
    top: TrendLine
    bottom: TrendLine
    top_touches: int
    bottom_touches: int
    top_anchor_dates: tuple[str, str]
    bottom_anchor_dates: tuple[str, str]
    breakout_date: str | None
    breakout_side: str | None
    line_cross_value: float | None
    target_price: float | None
    score: int
    span: int


class IndexTickerProvider:
    INDEX_SYMBOLS = {"WIG20": "wig20", "MWIG40": "mwig40", "SWIG80": "swig80"}
    INDEX_FALLBACK_TICKERS = {
        # Lokalny fallback, żeby `python run -search wig20` działało także
        # gdy Stooq nie zwraca tabeli komponentów indeksu.
        # Format: tickery skrócone (bez .WA), zgodne z użyciem w stockhelper.
        "WIG20": [
            "ALE", "ALR", "BDX", "CDR", "DNP", "EBP", "KGH", "KRU", "KTY", "LPP",
            "MBK", "MDV", "PCO", "PEO", "PGE", "PKN", "PKO", "PZU", "TPE", "ZAB",
        ],
    }

    def resolve(self, search_value: str) -> tuple[str, list[str]]:
        key = search_value.strip().upper()
        if key in self.INDEX_SYMBOLS:
            return key, self._load_or_fetch_index_tickers(key)
        return key, [key]

    def _load_or_fetch_index_tickers(self, index_name: str) -> list[str]:
        INDEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = INDEX_CACHE_DIR / f"{index_name}.csv"
        if cache_path.exists():
            cached = pd.read_csv(cache_path)
            if not cached.empty and "ticker" in cached.columns:
                return sorted(set(cached["ticker"].astype(str).str.upper().tolist()))
        try:
            tickers = self._fetch_index_tickers(index_name)
            pd.DataFrame({"ticker": tickers}).to_csv(cache_path, index=False)
            return tickers
        except Exception:
            fallback = self.INDEX_FALLBACK_TICKERS.get(index_name, [])
            if fallback:
                tickers = sorted(set(t.upper() for t in fallback))
                pd.DataFrame({"ticker": tickers}).to_csv(cache_path, index=False)
                return tickers
            raise

    def _fetch_index_tickers(self, index_name: str) -> list[str]:
        symbol = self.INDEX_SYMBOLS[index_name]
        urls = [
            f"https://stooq.pl/q/i/?{urlencode({'s': symbol, 'i': '0', 'l': '1'})}",
            f"https://stooq.com/q/i/?{urlencode({'s': symbol, 'i': '0', 'l': '1'})}",
        ]
        errors: list[str] = []
        tables: list[pd.DataFrame] = []
        for url in urls:
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                html = urlopen(req, timeout=20).read().decode("utf-8", errors="replace")
                tables = pd.read_html(StringIO(html))
                if tables:
                    break
            except Exception as exc:
                errors.append(f"{url}: {exc}")

        for df in tables:
            cols = [str(c).lower() for c in df.columns]
            if any("ticker" in c or "symbol" in c or "walor" in c for c in cols):
                for col in df.columns:
                    series = df[col].astype(str)
                    vals = [v.strip().upper() for v in series if v and v.strip() and v.strip().isalpha() and len(v.strip()) <= 6]
                    if len(vals) >= 5:
                        return sorted(set(vals))
        joined = " | ".join(errors) if errors else "brak tabel z tickerami na stronie"
        raise ValueError(f"Nie udało się pobrać tickerów indeksu {index_name} ze Stooqa. Próby: {joined}")


class TriangleDetector:
    def __init__(
        self,
        min_sessions: int = 40,
        breakout_fresh_sessions: int = 5,
        max_bars: int = 280,
        anchor_step: int = 1,
        max_candidates: int = 220000,
        max_line_break_ratio: float = 0.35,
        min_convergence_ratio: float = -0.05,
        enforce_swings: bool = True,
    ):
        self.min_sessions = min_sessions
        self.breakout_fresh_sessions = breakout_fresh_sessions
        self.max_bars = max_bars
        self.anchor_step = max(1, anchor_step)
        self.max_candidates = max_candidates
        self.max_line_break_ratio = max_line_break_ratio
        self.min_convergence_ratio = min_convergence_ratio
        self.enforce_swings = enforce_swings

    def find_best(self, df: pd.DataFrame, ticker: str | None = None) -> TriangleCandidate | None:
        if len(df) < self.min_sessions:
            return None
        data = df.sort_values("Date").reset_index(drop=True)
        best: TriangleCandidate | None = None
        n = len(data)
        start = max(0, n - self.max_bars)
        checked = 0
        for i in range(start, n - self.min_sessions, self.anchor_step):
            for j in range(i + 10, n - 5, self.anchor_step):
                top = TrendLine(i, j, float(data.loc[i, "High"]), float(data.loc[j, "High"]))
                for k in range(start, n - self.min_sessions, self.anchor_step):
                    for l in range(k + 5, n - 1, self.anchor_step):
                        bottom = TrendLine(k, l, float(data.loc[k, "Low"]), float(data.loc[l, "Low"]))
                        checked += 1
                        if checked > self.max_candidates:
                            return best
                        if self.enforce_swings:
                            if not (self._is_swing_high(data, i) and self._is_swing_high(data, j)):
                                continue
                            if not (self._is_swing_low(data, k) and self._is_swing_low(data, l)):
                                continue
                        cand = self._evaluate(data, top, bottom)
                        if not cand:
                            continue
                        if not best or self._is_better(cand, best):
                            best = cand
        return best

    def _evaluate(self, data: pd.DataFrame, top: TrendLine, bottom: TrendLine) -> TriangleCandidate | None:
        end = len(data) - 1
        span_start = min(top.first_idx, bottom.first_idx)
        span = end - span_start + 1
        if span < self.min_sessions:
            return None
        if top.value_at(end) <= bottom.value_at(end):
            return None
        start_distance = top.value_at(span_start) - bottom.value_at(span_start)
        end_distance = top.value_at(end) - bottom.value_at(end)
        if start_distance <= 0 or end_distance <= 0:
            return None
        convergence_ratio = (start_distance - end_distance) / start_distance
        if convergence_ratio < self.min_convergence_ratio:
            return None

        validation_start = max(top.second_idx, bottom.second_idx)
        top_breaks, bottom_breaks, first_breakout = self._boundary_break_stats(data, top, bottom, validation_start)
        observations = max(1, end - validation_start + 1)
        if (top_breaks / observations) > self.max_line_break_ratio or (bottom_breaks / observations) > self.max_line_break_ratio:
            return None

        top_touches = self._count_touches(data, top, is_top=True)
        bottom_touches = self._count_touches(data, bottom, is_top=False)
        if top_touches < 2 or bottom_touches < 2:
            return None

        breakout_date = None
        breakout_side = None
        line_cross_value = None
        if first_breakout is not None:
            idx, breakout_side = first_breakout
            breakout_date = data.loc[idx, "Date"].date().isoformat()
            line_cross_value = top.value_at(idx) if breakout_side == "up" else bottom.value_at(idx)

        if breakout_date:
            last = data.loc[end, "Date"].date()
            bo = datetime.fromisoformat(breakout_date).date()
            if (last - bo).days > self.breakout_fresh_sessions + 2:
                return None

        height = max(top.first_value, top.second_value) - min(bottom.first_value, bottom.second_value)
        target_price = None
        if line_cross_value is not None:
            target_price = line_cross_value + height if breakout_side == "up" else line_cross_value - height

        score = top_touches + bottom_touches
        return TriangleCandidate(
            top=top,
            bottom=bottom,
            top_touches=top_touches,
            bottom_touches=bottom_touches,
            top_anchor_dates=(data.loc[top.first_idx, "Date"].date().isoformat(), data.loc[top.second_idx, "Date"].date().isoformat()),
            bottom_anchor_dates=(data.loc[bottom.first_idx, "Date"].date().isoformat(), data.loc[bottom.second_idx, "Date"].date().isoformat()),
            breakout_date=breakout_date,
            breakout_side=breakout_side,
            line_cross_value=line_cross_value,
            target_price=target_price,
            score=score,
            span=span,
        )

    def _is_swing_high(self, data: pd.DataFrame, idx: int, lookback: int = 2) -> bool:
        left = max(0, idx - lookback)
        right = min(len(data) - 1, idx + lookback)
        value = float(data.loc[idx, "High"])
        return value >= float(data.loc[left:right, "High"].max())

    def _is_swing_low(self, data: pd.DataFrame, idx: int, lookback: int = 2) -> bool:
        left = max(0, idx - lookback)
        right = min(len(data) - 1, idx + lookback)
        value = float(data.loc[idx, "Low"])
        return value <= float(data.loc[left:right, "Low"].min())

    def _boundary_break_stats(
        self,
        data: pd.DataFrame,
        top: TrendLine,
        bottom: TrendLine,
        start_idx: int,
    ) -> tuple[int, int, tuple[int, str] | None]:
        top_breaks = 0
        bottom_breaks = 0
        first_breakout: tuple[int, str] | None = None
        for idx in range(start_idx, len(data)):
            close = float(data.loc[idx, "Close"])
            tv = top.value_at(idx)
            bv = bottom.value_at(idx)
            if close > tv:
                top_breaks += 1
                if first_breakout is None:
                    first_breakout = (idx, "up")
            elif close < bv:
                bottom_breaks += 1
                if first_breakout is None:
                    first_breakout = (idx, "down")
        return top_breaks, bottom_breaks, first_breakout

    def _count_touches(self, data: pd.DataFrame, line: TrendLine, is_top: bool) -> int:
        eps = 0.004
        touched_idxs: list[int] = [line.first_idx, line.second_idx]
        start = min(line.first_idx, line.second_idx)
        for idx in range(start, len(data)):
            lv = line.value_at(idx)
            high = float(data.loc[idx, "High"])
            low = float(data.loc[idx, "Low"])
            close = float(data.loc[idx, "Close"])
            if is_top:
                near = abs(high - lv) <= max(0.01, abs(lv) * eps)
                ok_close = close <= lv
                wick_hit = high >= lv
                if ok_close and (near or wick_hit):
                    touched_idxs.append(idx)
            else:
                near = abs(low - lv) <= max(0.01, abs(lv) * eps)
                ok_close = close >= lv
                wick_hit = low <= lv
                if ok_close and (near or wick_hit):
                    touched_idxs.append(idx)

        uniq = sorted(set(touched_idxs))
        groups = 0
        prev = None
        for idx in uniq:
            if prev is None or idx != prev + 1:
                groups += 1
            prev = idx
        return groups

    def _is_better(self, cand: TriangleCandidate, best: TriangleCandidate) -> bool:
        if cand.score != best.score:
            return cand.score > best.score
        if cand.span != best.span:
            return cand.span > best.span
        if bool(cand.breakout_date) != bool(best.breakout_date):
            return bool(cand.breakout_date)
        return max(cand.top.second_idx, cand.bottom.second_idx) > max(best.top.second_idx, best.bottom.second_idx)


def _avg_turnover_10(df: pd.DataFrame) -> float:
    recent = df.sort_values("Date").tail(10)
    if recent.empty:
        return 0.0
    return float((recent["Close"] * recent["Volume"]).mean())


def _fmt(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:.2f}"


def run_triangle_search(search_value: str) -> pd.DataFrame:
    provider = IndexTickerProvider()
    detector = TriangleDetector()
    relaxed_detector = TriangleDetector(
        max_bars=365,
        anchor_step=1,
        max_candidates=500000,
        max_line_break_ratio=0.55,
        min_convergence_ratio=-0.25,
        enforce_swings=False,
    )
    scope_name, tickers = provider.resolve(search_value)
    print(f"[triangle-search] Zakres: {scope_name} | liczba tickerów: {len(tickers)}")
    rows = []
    for pos, ticker in enumerate(tickers, start=1):
        print(f"[triangle-search] ({pos}/{len(tickers)}) Analiza {ticker}...")
        try:
            df, _, _ = load_or_update_daily_data(f"{ticker}.WA", "stock", persist=True, data_source="stooq")
        except Exception:
            print(f"[triangle-search] {ticker}: pominięty (błąd pobierania danych).")
            continue
        if not {"Date", "High", "Low", "Close", "Volume"}.issubset(df.columns):
            print(f"[triangle-search] {ticker}: pominięty (brak kolumn OHLCV).")
            continue
        turnover = _avg_turnover_10(df)
        if turnover < 500_000:
            print(f"[triangle-search] {ticker}: pominięty (średni obrót 10 sesji < 500k PLN).")
            continue
        triangle = detector.find_best(df, ticker=ticker)
        if not triangle:
            triangle = relaxed_detector.find_best(df, ticker=ticker)
        if not triangle:
            print(f"[triangle-search] {ticker}: brak poprawnego trójkąta.")
            continue
        status = "Breakout" if triangle.breakout_date else "Active"
        print(f"[triangle-search] {ticker}: znaleziono {status} (touch góra={triangle.top_touches}, dół={triangle.bottom_touches}).")
        rows.append({
            "Ticker": ticker,
            "Status": status,
            "Liczba_touch_górą": triangle.top_touches,
            "Liczba_touch_dołem": triangle.bottom_touches,
            "An_top_1": triangle.top_anchor_dates[0],
            "An_top_2": triangle.top_anchor_dates[1],
            "An_btm_1": triangle.bottom_anchor_dates[0],
            "An_btm_2": triangle.bottom_anchor_dates[1],
            "Data_wybicia": triangle.breakout_date or "",
            "Line_cross_value": _fmt(triangle.line_cross_value),
            "TP": _fmt(triangle.target_price),
            "Średni_obrót_10_sesji": _fmt(turnover),
        })

    result = pd.DataFrame(rows)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    out_path = RESULT_DIR / f"{today}_{scope_name.upper()}.csv"
    result.to_csv(out_path, index=False)
    return result


def render_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "Brak wyników spełniających kryteria."
    return df.to_string(index=False)
