"""
Financial calculations module.
Provides functions for options pricing and risk calculations.
"""
import math
import logging
from typing import Optional
from datetime import datetime, timedelta
import pandas as pd
from app.exceptions import CalculationError

logger = logging.getLogger(__name__)


def calculate_chance_of_profit(
    stock_price: float,
    strike: float,
    implied_vol: float,
    days_to_expiry: int,
    risk_free_rate: float = 0.04
) -> float:
    """
    Calculate the probability of a short put expiring out-of-the-money.

    Uses Black-Scholes d2 formula: P(S_T > K) = N(d2)

    Args:
        stock_price: Current stock price
        strike: Put strike price
        implied_vol: Implied volatility (as decimal, e.g., 0.25 for 25%)
        days_to_expiry: Days until option expiration
        risk_free_rate: Risk-free rate (default 4%)

    Returns:
        Probability as float between 0.0 and 1.0

    Raises:
        CalculationError: If inputs are invalid
    """
    try:
        if stock_price <= 0 or strike <= 0 or implied_vol <= 0:
            return 0.5  # Default to neutral if inputs invalid

        # Time to expiration in years
        T = max(days_to_expiry, 0.5) / 365.0
        vol = max(implied_vol, 0.01)

        # Black-Scholes d2 calculation
        # d2 = [ln(S/K) + (r - v^2/2)T] / [v * sqrt(T)]
        d2 = (
            math.log(stock_price / strike) +
            (risk_free_rate - 0.5 * vol**2) * T
        ) / (vol * math.sqrt(T))

        # Cumulative normal distribution N(d2)
        prob_otm = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))

        # Clamp result between 0 and 1
        return min(max(prob_otm, 0.0), 1.0)

    except (ValueError, ZeroDivisionError) as e:
        logger.error(f"Error calculating chance of profit: {e}")
        raise CalculationError(f"Failed to calculate probability: {e}") from e


def get_next_friday_expiration() -> str:
    """
    Calculate the next Friday's date for options expiration.

    Returns:
        Date string in format 'YYYY-MM-DD'
    """
    today = datetime.now()
    # Friday is weekday 4 (0=Monday, 4=Friday)
    days_until_friday = (4 - today.weekday() + 7) % 7

    # If today is Friday, get next Friday
    if days_until_friday == 0:
        days_until_friday = 7

    next_friday = today + timedelta(days=days_until_friday)
    return next_friday.strftime('%Y-%m-%d')


def calculate_required_premium(strike_price: float, min_premium_percent: float) -> float:
    """
    Calculate the minimum required premium based on strike price.

    Args:
        strike_price: Strike price of the option
        min_premium_percent: Minimum premium as percentage (e.g., 0.5 for 0.5%)

    Returns:
        Required premium amount

    Raises:
        ValueError: If inputs are invalid
    """
    if strike_price <= 0:
        raise ValueError("Strike price must be positive")
    if min_premium_percent < 0:
        raise ValueError("Premium percentage cannot be negative")

    return strike_price * (min_premium_percent / 100)


def extract_option_price(
    bid: Optional[float],
    ask: Optional[float],
    last_price: Optional[float] = None
) -> float:
    """
    Extract the most reliable option price from bid/ask/last price.

    Priority:
    1. Midpoint of bid-ask spread (if both valid)
    2. Bid (if valid)
    3. Last price (if valid)
    4. Ask (if valid)
    5. 0 (if none valid)

    Args:
        bid: Bid price
        ask: Ask price
        last_price: Last traded price

    Returns:
        Best available price estimate
    """
    # Check for valid bid-ask spread
    if bid and ask and bid > 0 and ask > 0:
        return float((bid + ask) / 2.0)

    # Fall back to individual prices
    if bid and bid > 0:
        return float(bid)

    if last_price and last_price > 0:
        return float(last_price)

    if ask and ask > 0:
        return float(ask)

    return 0.0
