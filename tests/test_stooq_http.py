from __future__ import annotations

from utilities import stooq_http


class _FakeResponse:
    content = b"Date,Open,High,Low,Close\n2026-06-09,1,2,0.5,1.5\n"
    encoding = "utf-8"

    def raise_for_status(self) -> None:
        return None


class _FakeRequests:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return _FakeResponse()


def test_download_stooq_text_uses_curl_cffi_impersonation(monkeypatch):
    fake_requests = _FakeRequests()
    monkeypatch.setattr(stooq_http, "_curl_cffi_requests_module", lambda: fake_requests)
    monkeypatch.setenv("STOOQ_CURL_IMPERSONATE", "chrome146")

    text = stooq_http.download_stooq_text("https://stooq.pl/q/d/l/?s=zal.de&i=d")

    assert text.startswith("Date,Open,High,Low,Close")
    expected_headers = dict(stooq_http.STOOQ_BROWSER_HEADERS)
    expected_headers["Referer"] = "https://stooq.pl/q/d/?s=zal.de"
    assert fake_requests.calls == [
        {
            "url": "https://stooq.pl/q/d/l/?s=zal.de&i=d",
            "headers": expected_headers,
            "impersonate": "chrome146",
            "timeout": 20,
        }
    ]


def test_download_stooq_text_falls_back_to_browser_headers_without_curl(monkeypatch):
    monkeypatch.setattr(stooq_http, "_curl_cffi_requests_module", lambda: None)
    monkeypatch.setattr(
        stooq_http,
        "_download_with_urllib",
        lambda url, timeout: f"{url}|{timeout}",
    )

    assert (
        stooq_http.download_stooq_text("https://stooq.com/q/d/l/?s=^jci&i=d", timeout=15)
        == "https://stooq.com/q/d/l/?s=^jci&i=d|15"
    )
