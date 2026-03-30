import yfinance as yf
from urllib.error import HTTPError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


RETRY_EXCEPTIONS = (HTTPError, ValueError, ConnectionError, TimeoutError, Exception)


def _before_sleep_log(retry_state):
    """Loguje informację o ponowieniu próby pobrania danych."""
    print(
        f"Retry {retry_state.attempt_number} for {retry_state.fn.__name__} "
        f"after error: {retry_state.outcome.exception()}"
    )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(RETRY_EXCEPTIONS),
    reraise=True,
    before_sleep=_before_sleep_log,
)
def get_daily_turnovers_yahoo(symbol: str, period: str = "20d") -> list[float]:
    """Pobiera listę dziennych obrotów (wartości) dla podanego okresu."""
    stock = yf.Ticker(symbol)
    hist = stock.history(period=period)

    if hist.empty:
        raise ValueError(f"Brak danych dla symbolu {symbol}")

    hist["AveragePrice"] = (hist["Open"] + hist["Close"] + hist["High"] + hist["Low"]) / 4
    hist["DailyTurnover"] = hist["Volume"] * hist["AveragePrice"]
    return hist["DailyTurnover"].tolist()


def get_avg_daily_turnover_yahoo(symbol: str, period: str = "10d") -> float:
    """Pobiera średni dzienny obrót (wartość) dla danego symbolu."""
    daily_turnovers = get_daily_turnovers_yahoo(symbol, period=period)
    return float(sum(daily_turnovers) / len(daily_turnovers))


def get_symbol_currency_yahoo(symbol: str) -> str:
    """Zwraca walutę notowania symbolu (np. PLN, USD)."""
    stock = yf.Ticker(symbol)
    currency = ""
    try:
        currency = (stock.fast_info.get("currency") or "").upper()
    except Exception:
        currency = ""

    if not currency:
        info = stock.info or {}
        currency = (info.get("currency") or "").upper()

    return currency or "USD"


def get_fx_to_pln_rate_yahoo(currency: str) -> tuple[str, float]:
    """Zwraca parę FX i kurs do przeliczenia danej waluty na PLN."""
    currency = currency.upper()
    if currency == "PLN":
        return "PLNPLN=X", 1.0

    for pair in [f"{currency}PLN=X", f"PLN{currency}=X"]:
        hist = yf.Ticker(pair).history(period="5d")
        if not hist.empty:
            rate = float(hist["Close"].iloc[-1])
            if pair.startswith("PLN") and rate > 0:
                rate = 1 / rate
            return pair, rate

    raise ValueError(f"Brak kursu FX dla waluty {currency} do PLN")
