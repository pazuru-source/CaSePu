"""
Tests for calculation utilities.
"""
import pytest
from app.utils.calculations import (
    calculate_chance_of_profit,
    calculate_required_premium,
    extract_option_price,
    get_next_friday_expiration
)
from app.exceptions import CalculationError
from datetime import datetime, timedelta


class TestCalculateChanceOfProfit:
    """Test Black-Scholes probability calculations."""

    def test_basic_calculation(self):
        """Test basic chance of profit calculation."""
        # Current price = strike price should give ~50% probability
        prob = calculate_chance_of_profit(
            stock_price=100.0,
            strike=100.0,
            implied_vol=0.20,
            days_to_expiry=30
        )
        assert 0.45 <= prob <= 0.55, f"Expected ~50%, got {prob:.2%}"

    def test_otm_put_high_probability(self):
        """Out-of-the-money puts should have high probability."""
        # Stock price well above strike should give high probability
        prob = calculate_chance_of_profit(
            stock_price=150.0,
            strike=100.0,
            implied_vol=0.20,
            days_to_expiry=30
        )
        assert prob > 0.90, f"Expected >90%, got {prob:.2%}"

    def test_itm_put_low_probability(self):
        """In-the-money puts should have low probability."""
        # Strike price well above stock price should give low probability
        prob = calculate_chance_of_profit(
            stock_price=100.0,
            strike=150.0,
            implied_vol=0.20,
            days_to_expiry=30
        )
        assert prob < 0.10, f"Expected <10%, got {prob:.2%}"

    def test_invalid_inputs_return_default(self):
        """Invalid inputs should return 0.5 (neutral)."""
        assert calculate_chance_of_profit(0, 100, 0.2, 30) == 0.5
        assert calculate_chance_of_profit(100, 0, 0.2, 30) == 0.5
        assert calculate_chance_of_profit(100, 100, 0, 30) == 0.5

    def test_probability_bounds(self):
        """Probability should always be between 0 and 1."""
        prob = calculate_chance_of_profit(
            stock_price=100.0,
            strike=100.0,
            implied_vol=0.20,
            days_to_expiry=30
        )
        assert 0.0 <= prob <= 1.0


class TestCalculateRequiredPremium:
    """Test premium calculation."""

    def test_basic_premium_calculation(self):
        """Test basic premium calculation."""
        premium = calculate_required_premium(
            strike_price=100.0,
            min_premium_percent=0.5
        )
        assert premium == pytest.approx(0.5, rel=0.01)

    def test_premium_scales_with_strike(self):
        """Premium should scale proportionally with strike price."""
        premium1 = calculate_required_premium(100.0, 0.5)
        premium2 = calculate_required_premium(200.0, 0.5)
        assert premium2 == pytest.approx(premium1 * 2, rel=0.01)

    def test_invalid_strike_raises_error(self):
        """Negative strike should raise error."""
        with pytest.raises(ValueError):
            calculate_required_premium(-100.0, 0.5)

        with pytest.raises(ValueError):
            calculate_required_premium(0, 0.5)

    def test_negative_premium_percent_raises_error(self):
        """Negative premium percent should raise error."""
        with pytest.raises(ValueError):
            calculate_required_premium(100.0, -0.5)


class TestExtractOptionPrice:
    """Test option price extraction logic."""

    def test_midpoint_preferred(self):
        """Should use midpoint of bid-ask spread when both valid."""
        price = extract_option_price(bid=1.0, ask=3.0)
        assert price == 2.0

    def test_bid_fallback(self):
        """Should fall back to bid if ask missing."""
        price = extract_option_price(bid=1.5, ask=None)
        assert price == 1.5

    def test_last_price_fallback(self):
        """Should fall back to last price if bid-ask missing."""
        price = extract_option_price(bid=None, ask=None, last_price=1.2)
        assert price == 1.2

    def test_ask_last_resort(self):
        """Should use ask as last resort."""
        price = extract_option_price(bid=0, ask=2.5)
        assert price == 2.5

    def test_all_invalid_returns_zero(self):
        """Should return 0 if no valid prices."""
        price = extract_option_price(bid=0, ask=0, last_price=None)
        assert price == 0.0


class TestGetNextFridayExpiration:
    """Test Friday expiration date calculation."""

    def test_returns_string(self):
        """Should return string in YYYY-MM-DD format."""
        result = get_next_friday_expiration()
        assert isinstance(result, str)
        assert len(result) == 10
        assert result[4] == '-' and result[7] == '-'

    def test_is_friday(self):
        """Returned date should be a Friday."""
        date_str = get_next_friday_expiration()
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        assert date_obj.weekday() == 4  # Friday is weekday 4

    def test_is_future(self):
        """Returned date should be in the future."""
        date_str = get_next_friday_expiration()
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        assert date_obj.date() >= datetime.now().date()
