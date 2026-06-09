from __future__ import annotations

import hashlib

from utilities import stooq_http


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = text.encode("utf-8")
        self.encoding = "utf-8"

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, responses: list[str] | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.responses = responses or ["Date,Open,High,Low,Close\n2026-06-09,1,2,0.5,1.5\n"]

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return _FakeResponse(self.responses[index])


class _FakeRequests:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    def Session(self) -> _FakeSession:
        return self.session


def _install_fake_curl(monkeypatch, session: _FakeSession) -> _FakeSession:
    monkeypatch.setattr(stooq_http, "_CURL_SESSION", None)
    monkeypatch.setattr(stooq_http, "_BROWSER_CLEARANCE_HEADERS", None)
    monkeypatch.setattr(stooq_http, "_curl_cffi_requests_module", lambda: _FakeRequests(session))
    return session


def test_download_stooq_text_uses_curl_cffi_impersonation(monkeypatch):
    fake_session = _install_fake_curl(monkeypatch, _FakeSession())
    monkeypatch.setenv("STOOQ_CURL_IMPERSONATE", "chrome146")

    text = stooq_http.download_stooq_text("https://stooq.pl/q/d/l/?s=zal.de&i=d")

    assert text.startswith("Date,Open,High,Low,Close")
    expected_headers = dict(stooq_http.STOOQ_BROWSER_HEADERS)
    expected_headers["Referer"] = "https://stooq.pl/q/d/?s=zal.de"
    assert fake_session.calls == [
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
        lambda url, timeout, headers=None: f"{url}|{timeout}|{headers['Referer']}",
    )

    assert (
        stooq_http.download_stooq_text("https://stooq.com/q/d/l/?s=^jci&i=d", timeout=15)
        == "https://stooq.com/q/d/l/?s=^jci&i=d|15|https://stooq.com/q/d/?s=%5Ejci"
    )


def test_download_stooq_text_retries_after_js_challenge(monkeypatch):
    challenge = "abc"
    nonce = 0
    while not hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest().startswith("0"):
        nonce += 1
    challenge_html = f'''
        <!DOCTYPE html><noscript>This site requires JavaScript to verify your browser.</noscript>
        <script>(async()=>{{const c="{challenge}",d=1,t="0".repeat(d),e=new TextEncoder;
        let n=0;while(1){{const h=await crypto.subtle.digest("SHA-256",e.encode(c+n));
        if(true)break;}}document.cookie=`auth=${{c}}${{n}}; path=/`;location.reload();}})();</script>
    '''
    fake_session = _install_fake_curl(
        monkeypatch,
        _FakeSession([challenge_html, "Date,Open,High,Low,Close\n2026-06-09,1,2,0.5,1.5\n"]),
    )

    text = stooq_http.download_stooq_text("https://stooq.pl/q/d/l/?s=zal.de&i=d")

    assert text.startswith("Date,Open,High,Low,Close")
    assert fake_session.calls[1]["headers"]["Cookie"] == f"auth={challenge}{nonce}"


def test_debug_logging_shows_method_and_redacts_api_key(monkeypatch, capsys):
    _install_fake_curl(monkeypatch, _FakeSession())
    monkeypatch.setenv("STOOQ_HTTP_DEBUG", "1")

    stooq_http.download_stooq_text("https://stooq.pl/q/d/l/?s=zal.de&i=d&apikey=SECRET")

    captured = capsys.readouterr()
    assert "curl_cffi=available" in captured.err
    assert "curl_cffi GET" in captured.err
    assert "apikey=" in captured.err
    assert "SECRET" not in captured.err


def test_download_stooq_text_uses_playwright_after_unsolved_challenge(monkeypatch):
    challenge_html = '''
        <!DOCTYPE html><noscript>This site requires JavaScript to verify your browser.</noscript>
        <script>(async()=>{const c="abc",d=1,t="0".repeat(d),e=new TextEncoder;
        let n=0;while(1){const h=await crypto.subtle.digest("SHA-256",e.encode(c+n));}})();</script>
    '''
    fake_session = _install_fake_curl(monkeypatch, _FakeSession([challenge_html]))
    monkeypatch.setattr(
        stooq_http,
        "_download_with_playwright",
        lambda url, timeout: "Date,Open,High,Low,Close\n2026-06-09,1,2,0.5,1.5\n",
    )

    text = stooq_http.download_stooq_text("https://stooq.pl/q/d/l/?s=zal.de&i=d")

    assert text.startswith("Date,Open,High,Low,Close")
    assert len(fake_session.calls) > 1


def test_apply_playwright_stealth_uses_stealth_sync(monkeypatch):
    calls = []

    class FakeStealth:
        @staticmethod
        def stealth_sync(page):
            calls.append(page)

    monkeypatch.setattr(stooq_http, "_playwright_stealth_module", lambda: FakeStealth)

    assert stooq_http._apply_playwright_stealth("page", "context") is True
    assert calls == ["page"]


def test_headers_with_browser_clearance_merges_cookie(monkeypatch):
    monkeypatch.setattr(
        stooq_http,
        "_BROWSER_CLEARANCE_HEADERS",
        {"User-Agent": "Browser UA", "Cookie": "cf_clearance=ok; uid=abc"},
    )

    headers = stooq_http._headers_with_browser_clearance({"User-Agent": "Old UA", "Cookie": "old=1"})

    assert headers["User-Agent"] == "Browser UA"
    assert headers["Cookie"] == "old=1; cf_clearance=ok; uid=abc"
