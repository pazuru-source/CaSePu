"""
Options analysis service.
Core business logic for finding cash-secured put opportunities.
"""
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
import yfinance as yf
from app.exceptions import OptionsChainError, ValidationError
from app.config import get_config
from app.utils.calculations import (
    calculate_chance_of_profit,
    calculate_required_premium,
    extract_option_price
)

logger = logging.getLogger(__name__)
config = get_config()


def find_cash_secured_puts(
    ticker: yf.Ticker,
    target_date_str: str,
    current_price: float,
    min_premium_percent: Optional[float] = None,
    min_chance_of_profit: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Find suitable cash-secured put options for a given ticker and expiration date.

    Args:
        ticker: yfinance Ticker object
        target_date_str: Target expiration date in format 'YYYY-MM-DD'
        current_price: Current stock price
        min_premium_percent: Minimum premium percentage (uses config if None)
        min_chance_of_profit: Minimum probability threshold (uses config if None)

    Returns:
        List of suitable put options with pricing details

    Raises:
        OptionsChainError: If options chain data is unavailable
        ValidationError: If inputs are invalid
    """
    if min_premium_percent is None:
        min_premium_percent = config.MIN_PREMIUM_PERCENT_COLLATERAL
    if min_chance_of_profit is None:
        min_chance_of_profit = config.MIN_CHANCE_OF_PROFIT

    if current_price <= 0:
        raise ValidationError("Current price must be positive")

    suitable_options: List[Dict[str, Any]] = []

    try:
        # Check if requested date exists in available options
        available_options = ticker.options
        if not available_options or target_date_str not in available_options:
            logger.warning(
                f"No options available for {ticker.ticker} on {target_date_str}"
            )
            return []

        # Get options chain for the target expiration
        options_chain = ticker.option_chain(target_date_str)
        puts = options_chain.puts

        if puts.empty:
            logger.warning(f"No puts available for {ticker.ticker}")
            return []

        # Process each put option
        for _index, put in puts.iterrows():
            strike = put['strike']
            bid = put.get('bid', 0)

            # Skip strikes that are at or above current price (ITM puts)
            if strike >= current_price:
                continue

            # Calculate required premium
            required_premium = calculate_required_premium(
                strike, min_premium_percent)

            # Extract best available price
            bid_price = extract_option_price(
                bid if bid and bid > 0 else None,
                put.get('ask'),
                put.get('lastPrice')
            )

            if bid_price <= 0:
                continue

            # Verify premium meets requirement
            if bid_price < required_premium:
                continue

            # Calculate probability of expiring OTM
            implied_vol = put.get('impliedVolatility', 0)

            # Calculate days to expiry
            try:
                from datetime import datetime
                exp_dt = datetime.strptime(target_date_str, '%Y-%m-%d')
                days_to_expiry = (exp_dt.date() - datetime.now().date()).days
            except Exception:
                days_to_expiry = 7  # Fallback to 1 week

            chance_of_profit = calculate_chance_of_profit(
                current_price,
                strike,
                implied_vol,
                days_to_expiry,
                config.RISK_FREE_RATE
            )

            # Filter based on minimum chance of profit threshold
            if chance_of_profit < min_chance_of_profit:
                continue

            # Add to suitable options
            suitable_options.append({
                'symbol': ticker.ticker,
                'expiration': target_date_str,
                'strike': float(strike),
                'bid': float(bid_price),
                'ask': float(put.get('ask', 0) or 0),
                'last_price': float(put.get('lastPrice', 0) or 0),
                'implied_volatility': float(implied_vol or 0),
                'required_premium': float(required_premium),
                'chance_of_profit': float(chance_of_profit)
            })

        return suitable_options

    except Exception as e:
        logger.error(f"Error finding options for {ticker.ticker}: {e}")
        raise OptionsChainError(
            f"Failed to find options for {ticker.ticker}: {e}"
        ) from e


def validate_ticker_criteria(
    fundamentals: Dict[str, Any],
    is_manual: bool = False
) -> bool:
    """
    Validate if ticker meets fundamental screening criteria.

    Args:
        fundamentals: Dictionary with market_cap_billions, trailing_pe, peg_ratio
        is_manual: Whether this is a user-specified ticker (bypasses some filters)

    Returns:
        True if ticker meets criteria, False otherwise
    """
    if not fundamentals:
        return False

    mcap = fundamentals.get('market_cap_billions', 0)
    pe = fundamentals.get('trailing_pe')
    peg = fundamentals.get('peg_ratio')
    price = fundamentals.get('current_price', 0)

    # Price must be in acceptable range
    price_ok = (
        price >= config.MIN_STOCK_PRICE and
        price <= config.MAX_STOCK_PRICE
    )

    if not price_ok:
        return False

    # Manual tickers bypass fundamental filters
    if is_manual:
        return True

    # Check fundamental criteria
    meets_criteria = (
        mcap >= config.MIN_MARKET_CAP_BILLIONS and
        mcap <= config.MAX_MARKET_CAP_BILLIONS and
        (pe is None or pe <= config.MAX_PE_RATIO) and
        (peg is None or peg <= config.MAX_PEG_RATIO)
    )

    return meets_criteria
