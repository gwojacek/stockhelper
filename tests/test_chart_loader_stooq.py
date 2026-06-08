from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pandas as pd

from chart_program import chart_loader


STOOQ_CSV = "Date,Open,High,Low,Close,Volume\n2026-06-04,10,11,9,10.8,1000\n2026-06-05,10.5,11.5,10,11.2,1500\n"
STOOQ_HTML_CHALLENGE = "<html><body><noscript>This site requires JavaScript to verify your browser.</noscript></body></html>"


def test_stooq_download_retries_without_date_range_when_bounded_query_returns_html(monkeypatch):
    requested_urls: list[str] = []

    def fake_download_text(url: str) -> str:
        requested_urls.append(url)
        query = parse_qs(urlparse(url).query)
        if "d1" in query or "d2" in query:
            return STOOQ_HTML_CHALLENGE
        return STOOQ_CSV

    monkeypatch.setattr(chart_loader, "_download_text", fake_download_text)
    monkeypatch.setattr(chart_loader, "_merge_stooq_current_quote", lambda df, symbol: df)

    df, candidate = chart_loader._stooq_download("PEO.WA", "stock", api_key="test-api-key")

    assert candidate == "peo.wa"
    assert df["Close"].iloc[-1] == 11.2
    assert len(requested_urls) == 2
    first_query = parse_qs(urlparse(requested_urls[0]).query)
    second_query = parse_qs(urlparse(requested_urls[1]).query)
    assert first_query["s"] == ["peo.wa"]
    assert "d1" in first_query
    assert "d2" in first_query
    assert first_query["apikey"] == ["test-api-key"]
    assert second_query["s"] == ["peo.wa"]
    assert "d1" not in second_query
    assert "d2" not in second_query
    assert second_query["apikey"] == ["test-api-key"]


def test_stooq_download_uses_env_api_key(monkeypatch):
    requested_urls: list[str] = []

    def fake_download_text(url: str) -> str:
        requested_urls.append(url)
        return STOOQ_CSV

    monkeypatch.setenv(chart_loader.STOOQ_API_KEY_ENV, "env-api-key")
    monkeypatch.setattr(chart_loader, "_download_text", fake_download_text)
    monkeypatch.setattr(chart_loader, "_merge_stooq_current_quote", lambda df, symbol: df)

    chart_loader._stooq_download("^jci", "commodity", api_key=None)

    query = parse_qs(urlparse(requested_urls[0]).query)
    assert query["apikey"] == ["env-api-key"]


def test_download_text_sends_browser_like_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return STOOQ_CSV.encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        return FakeResponse()

    monkeypatch.setattr(chart_loader, "urlopen", fake_urlopen)

    text = chart_loader._download_text("https://stooq.pl/q/d/l/?s=peo.wa&i=d")

    assert text == STOOQ_CSV
    assert captured["url"] == "https://stooq.pl/q/d/l/?s=peo.wa&i=d"
    assert captured["timeout"] == 20
    assert "Mozilla/5.0" in captured["headers"]["User-agent"]
    assert captured["headers"]["Referer"] == "https://stooq.pl/"
    assert "pl-PL" in captured["headers"]["Accept-language"]
