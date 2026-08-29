"""
Ticker processing service.
Handles batch processing and scanning of multiple tickers.
"""
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.config import get_config
from app.utils.data_fetching import (
    get_ticker_with_retry,
    get_stock_fundamentals
)
from app.services.options_service import (
    find_cash_secured_puts,
    validate_ticker_criteria
)
from app.exceptions import TickerDataError
from expected_move import calculate_expected_move

logger = logging.getLogger(__name__)
config = get_config()


def process_single_ticker(
    ticker_symbol: str,
    target_exp: str,
    extra_tickers: List[str],
    fav_tickers: List[str]
) -> Optional[Dict[str, Any]]:
    """
    Process a single ticker for options opportunities.

    Args:
        ticker_symbol: Ticker symbol to process
        target_exp: Target expiration date in format 'YYYY-MM-DD'
        extra_tickers: List of manually-specified tickers
        fav_tickers: List of favorite/preferred tickers

    Returns:
        Dictionary with ticker data and opportunities, or None if no opportunities found
    """
    try:
        is_manual = ticker_symbol in extra_tickers or ticker_symbol in fav_tickers

        # Fetch ticker data
        ticker_obj = get_ticker_with_retry(ticker_symbol)

        # Get fundamental data
        fundamentals = get_stock_fundamentals(ticker_obj)

        # Validate ticker meets criteria
        if not validate_ticker_criteria(fundamentals, is_manual):
            logger.debug(f"Ticker {ticker_symbol} does not meet criteria")
            return None

        # Find suitable put options
        puts = find_cash_secured_puts(
            ticker_obj,
            target_exp,
            fundamentals['current_price']
        )

        if not puts:
            logger.debug(f"No suitable puts found for {ticker_symbol}")
            return None

        # Calculate expected move
        em_data = calculate_expected_move(
            ticker_obj,
            target_expiry=target_exp,
            current_price=fundamentals['current_price']
        )

        if em_data:
            fundamentals['lower_band'] = em_data.get('lower_band')
            fundamentals['upper_band'] = em_data.get('upper_band')
            fundamentals['expected_move'] = em_data.get('expected_move')

        return {
            'ticker': ticker_symbol,
            'fundamentals': fundamentals,
            'puts': puts
        }

    except TickerDataError as e:
        logger.warning(f"Failed to process {ticker_symbol}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error processing {ticker_symbol}: {e}")
        return None


def process_tickers_parallel(
    tickers: List[str],
    target_exp: str,
    extra_tickers: List[str],
    fav_tickers: List[str],
    max_workers: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Process multiple tickers in parallel.

    Args:
        tickers: List of ticker symbols to process
        target_exp: Target expiration date
        extra_tickers: List of manually-specified tickers
        fav_tickers: List of favorite/preferred tickers
        max_workers: Maximum number of parallel workers (uses config if None)

    Returns:
        List of results from successful ticker processing
    """
    if max_workers is None:
        max_workers = config.MAX_WORKERS

    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_ticker = {
            executor.submit(
                process_single_ticker,
                ticker,
                target_exp,
                extra_tickers,
                fav_tickers
            ): ticker
            for ticker in tickers
        }

        # Process completed tasks
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")

    return results
