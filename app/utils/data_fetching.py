"""
Data fetching utilities for market data.
Handles ticker data retrieval, fundamental analysis, and options chains.
"""
import logging
import time
import io
import requests
import pandas as pd
from typing import Optional, List, Dict, Any
from html.parser import HTMLParser
import yfinance as yf
from app.exceptions import TickerDataError, OptionsChainError
from app.config import get_config

logger = logging.getLogger(__name__)
config = get_config()


def get_ticker_with_retry(
    ticker_symbol: str,
    max_retries: Optional[int] = None,
    retry_delay: Optional[int] = None
) -> Optional[yf.Ticker]:
    """
    Fetch a yfinance Ticker object with retry logic.

    Args:
        ticker_symbol: Stock ticker symbol
        max_retries: Maximum retry attempts (uses config if None)
        retry_delay: Delay between retries in seconds (uses config if None)

    Returns:
        yfinance Ticker object or None if all retries fail

    Raises:
        TickerDataError: If unable to fetch after all retries
    """
    if max_retries is None:
        max_retries = config.MAX_RETRIES
    if retry_delay is None:
        retry_delay = config.RETRY_DELAY

    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Trigger network request to validate
            _ = ticker.info
            return ticker
        except Exception as e:
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed for {ticker_symbol}: {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay)

    raise TickerDataError(
        f"Could not fetch ticker data for {ticker_symbol} after {max_retries} retries"
    )


def get_stock_fundamentals(ticker: yf.Ticker) -> Dict[str, Any]:
    """
    Extract fundamental stock data from a Ticker object.

    Args:
        ticker: yfinance Ticker object

    Returns:
        Dictionary with market_cap_billions, trailing_pe, peg_ratio, current_price

    Raises:
        TickerDataError: If unable to extract fundamental data
    """
    try:
        info = ticker.info

        market_cap = info.get('marketCap', 0)
        trailing_pe = info.get('trailingPE')
        peg_ratio = info.get('pegRatio')
        current_price = (
            info.get('currentPrice') or
            info.get('regularMarketPrice') or
            info.get('previousClose') or
            0
        )

        if not current_price:
            raise TickerDataError(
                f"No price data available for {ticker.ticker}")

        return {
            'market_cap_billions': market_cap / 1_000_000_000 if market_cap else 0,
            'trailing_pe': trailing_pe,
            'peg_ratio': peg_ratio,
            'current_price': float(current_price),
            'ticker': ticker.ticker
        }

    except Exception as e:
        logger.error(f"Error extracting fundamentals for {ticker.ticker}: {e}")
        raise TickerDataError(f"Failed to get fundamentals: {e}") from e


def get_sp500_tickers() -> List[str]:
    """
    Fetch current S&P 500 components from Wikipedia.

    Returns:
        List of ticker symbols
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Use io.StringIO to ensure pandas reads content as HTML
        tables = pd.read_html(
            io.StringIO(response.text),
            flavor='html5lib'
        )
        df = tables[0]
        tickers = df['Symbol'].tolist()

        # Clean up tickers (Wikipedia uses dots, yfinance uses hyphens)
        return [t.replace('.', '-') for t in tickers]

    except Exception as e:
        logger.warning(
            f"Error fetching S&P 500 tickers: {e}. Trying fallback parser.")
        return _get_tickers_via_parser(url)


def get_nasdaq100_tickers() -> List[str]:
    """
    Fetch current NASDAQ-100 components from Wikipedia.

    Returns:
        List of ticker symbols
    """
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        tables = pd.read_html(
            io.StringIO(response.text),
            flavor='html5lib'
        )

        # Search for table with 'Ticker' or 'Symbol' columns
        for table in tables:
            if 'Ticker' in table.columns:
                return table['Ticker'].tolist()
            if 'Symbol' in table.columns:
                return table['Symbol'].tolist()

        return []

    except Exception as e:
        logger.warning(
            f"Error fetching NASDAQ-100 tickers: {e}. Trying fallback parser.")
        return _get_tickers_via_parser(url)


class _WikipediaConstituentsParser(HTMLParser):
    """Parse Wikipedia tables to extract ticker symbols."""

    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_tr = False
        self.in_td = False
        self.td_count = 0
        self.tickers: List[str] = []
        self.current_data: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        attrs_dict = dict(attrs)
        if tag == 'table' and attrs_dict.get('id') == 'constituents':
            self.in_table = True
        elif self.in_table:
            if tag == 'tr':
                self.in_tr = True
                self.td_count = 0
            elif tag == 'td' and self.in_tr:
                self.in_td = True
                self.td_count += 1
                self.current_data = []

    def handle_endtag(self, tag: str) -> None:
        if tag == 'table':
            self.in_table = False
        elif self.in_table:
            if tag == 'tr':
                self.in_tr = False
            elif tag == 'td' and self.in_tr:
                self.in_td = False
                if self.td_count == 1:
                    symbol = "".join(self.current_data).strip()
                    if symbol:
                        symbol = symbol.replace('.', '-')
                        self.tickers.append(symbol)

    def handle_data(self, data: str) -> None:
        if self.in_table and self.in_tr and self.in_td and self.td_count == 1:
            self.current_data.append(data)


def _get_tickers_via_parser(url: str) -> List[str]:
    """Fallback parser for extracting tickers from Wikipedia."""
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        parser = _WikipediaConstituentsParser()
        parser.feed(response.text)
        return parser.tickers

    except Exception as e:
        logger.error(f"Error in Wikipedia parser: {e}")
        return []
