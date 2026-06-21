import builtins
import sys
import types

import pytest

import utilities.stooq_playwright as stooq_playwright


class _FakePage:
    pass


class _FakeBrowser:
    def __init__(self):
        self.pages = []

    def new_page(self):
        page = _FakePage()
        self.pages.append(page)
        return page


class _FakeChromium:
    def __init__(self):
        self.launch_kwargs = None

    def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return _FakeBrowser()


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeChromium()


def test_open_page_uses_playwright_by_default(monkeypatch):
    monkeypatch.delenv("STOCKHELPER_STOOQ_BROWSER", raising=False)
    playwright = _FakePlaywright()

    browser, page = stooq_playwright._open_page(playwright, interactive=True)

    assert browser.pages == [page]
    assert playwright.chromium.launch_kwargs == {"headless": False, "slow_mo": 150}


def test_open_page_uses_cloak_browser_when_enabled(monkeypatch):
    calls = []
    fake_module = types.ModuleType("cloakbrowser")

    def fake_launch(**kwargs):
        calls.append(kwargs)
        return _FakeBrowser()

    fake_module.launch = fake_launch
    monkeypatch.setitem(sys.modules, "cloakbrowser", fake_module)
    monkeypatch.setenv("STOCKHELPER_STOOQ_BROWSER", "cloak")
    playwright = _FakePlaywright()

    browser, page = stooq_playwright._open_page(playwright, interactive=False)

    assert browser.pages == [page]
    assert calls == [{"headless": True, "slow_mo": 0}]
    assert playwright.chromium.launch_kwargs is None


def test_open_page_explains_missing_cloak_browser(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cloakbrowser":
            raise ImportError("missing cloakbrowser")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setenv("STOCKHELPER_STOOQ_BROWSER", "cloak")

    with pytest.raises(RuntimeError, match="pip install cloakbrowser"):
        stooq_playwright._open_page(_FakePlaywright())


def test_open_page_rejects_unknown_browser_backend(monkeypatch):
    monkeypatch.setenv("STOCKHELPER_STOOQ_BROWSER", "firefox")

    with pytest.raises(ValueError, match="Unsupported STOCKHELPER_STOOQ_BROWSER"):
        stooq_playwright._open_page(_FakePlaywright())
