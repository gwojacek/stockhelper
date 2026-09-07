from journal import html_document


def test_compressed_journal_keeps_available_screenshots_visible():
    markup = html_document(
        [
            {
                "id": "example",
                "symbol": "AL.F",
                "screenshot_path": "journal/screenshots/open.png",
                "close_screenshot_path": "journal/screenshots/close.png",
            }
        ]
    )

    assert "class='screen-block open-screen'" in markup
    assert "class='screen-block close-screen'" in markup
    assert "body.compressed .screens .open-screen" not in markup
    assert "body.compressed .screens .screen-empty" not in markup
