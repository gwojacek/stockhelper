import pandas as pd

from utilities.stooq_playwright import _parse_stooq_ui_csv


def test_parse_polish_stooq_ui_csv():
    payload = (
        "Data,Otwarcie,Najwyzszy,Najnizszy,Zamkniecie\n"
        "1971-01-04,357.73,357.73,357.73,357.73\n"
    ).encode("cp1250")

    frame = _parse_stooq_ui_csv(payload)

    assert list(frame.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
    assert frame.iloc[0]["Date"] == pd.Timestamp("1971-01-04")
    assert frame.iloc[0]["Close"] == 357.73
    assert frame.iloc[0]["Volume"] == 0
