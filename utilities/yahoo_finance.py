import yfinance as yf


def get_avg_daily_turnover_yahoo(symbol: str) -> float:
    """
    Pobiera średni dzienny obrót (wartość) za ostatnie 10 sesji dla danego symbolu.

    Args:
        symbol (str): Symbol giełdowy (np. "CCC.WA").

    Returns:
        float: Średnia wartość dziennego obrotu.
    """
    stock = yf.Ticker(symbol)
    hist = stock.history(period="10d")  # Pobierz dane z ostatnich 10 dni
    if not hist.empty:
        # Oblicz średnią cenę dla każdego dnia
        hist["AveragePrice"] = (
            hist["Open"] + hist["Close"] + hist["High"] + hist["Low"]
        ) / 4
        # Oblicz dzienne obroty (wartość sprzedanych akcji)
        hist["DailyTurnover"] = hist["Volume"] * hist["AveragePrice"]
        # Oblicz średnią wartość dziennego obrotu za ostatnie 10 dni
        avg_daily_turnover = hist["DailyTurnover"].mean()
        return avg_daily_turnover
    else:
        raise ValueError(f"Brak danych dla symbolu {symbol}")
