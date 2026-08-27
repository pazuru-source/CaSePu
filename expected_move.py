import pandas as pd
import yfinance as yf
import logging

logger = logging.getLogger(__name__)


def calculate_expected_move(ticker_symbol_or_obj, target_expiry=None, current_price=None):
    """
    Calculates the expected move and upper/lower bands using the 85% ATM Straddle rule.
    Accepts either a ticker symbol string or a yfinance Ticker object.
    """
    try:
        # 1. Initialize ticker
        if isinstance(ticker_symbol_or_obj, str):
            tk = yf.Ticker(ticker_symbol_or_obj)
            symbol = ticker_symbol_or_obj
        else:
            tk = ticker_symbol_or_obj
            symbol = getattr(tk, 'ticker', str(ticker_symbol_or_obj))

        # Get current stock price
        stock_price = current_price
        if not stock_price or stock_price <= 0:
            hist = tk.history(period="1d")
            if not hist.empty and "Close" in hist:
                stock_price = float(hist["Close"].iloc[-1])
            else:
                stock_price = getattr(tk, 'fast_info', {}).get('lastPrice', 0)

        if not stock_price or stock_price <= 0:
            logger.warning(f"Could not fetch stock price for {symbol}")
            return None

        # 2. Get expiration dates
        expirations = tk.options
        if not expirations:
            logger.warning(f"No options data available for {symbol}")
            return None

        if target_expiry and target_expiry in expirations:
            expiry = target_expiry
        else:
            expiry = expirations[0]

        # 3. Pull option chain for that expiration
        opt_chain = tk.option_chain(expiry)
        calls = opt_chain.calls
        puts = opt_chain.puts

        if calls.empty or puts.empty:
            return None

        # 4. Find ATM Strike (prefer common strike between calls and puts)
        common_strikes = set(calls["strike"]).intersection(set(puts["strike"]))
        if common_strikes:
            atm_strike = float(min(common_strikes, key=lambda s: abs(s - stock_price)))
            call_row = calls[calls["strike"] == atm_strike].iloc[0]
            put_row = puts[puts["strike"] == atm_strike].iloc[0]
        else:
            call_atm_idx = (calls["strike"] - stock_price).abs().idxmin()
            put_atm_idx = (puts["strike"] - stock_price).abs().idxmin()
            call_row = calls.loc[call_atm_idx]
            put_row = puts.loc[put_atm_idx]
            atm_strike = float(call_row["strike"])

        # 5. Extract prices
        def extract_price(row):
            bid = row.get("bid", 0)
            ask = row.get("ask", 0)
            last = row.get("lastPrice", 0)
            if pd.notna(bid) and pd.notna(ask) and bid > 0 and ask > 0:
                return float((bid + ask) / 2.0)
            if pd.notna(bid) and bid > 0:
                return float(bid)
            if pd.notna(last) and last > 0:
                return float(last)
            if pd.notna(ask) and ask > 0:
                return float(ask)
            return 0.0

        call_price = extract_price(call_row)
        put_price = extract_price(put_row)

        # 6. Calculate ATM Straddle and Expected Move (85% rule)
        atm_straddle = call_price + put_price
        if atm_straddle > 0:
            expected_move = atm_straddle * 0.85
        else:
            # Fallback using Implied Volatility: EM = S * IV * sqrt(T) * 0.85
            import math
            from datetime import datetime
            iv = max(call_row.get("impliedVolatility", 0) or 0, put_row.get("impliedVolatility", 0) or 0)
            if iv > 0:
                try:
                    exp_dt = datetime.strptime(expiry, '%Y-%m-%d').date()
                    days = max((exp_dt - datetime.now().date()).days, 1)
                except Exception:
                    days = 7
                expected_move = stock_price * (iv * math.sqrt(days / 365.0)) * 0.85
            else:
                expected_move = 0.0

        # 7. Compute Upper and Lower Bands
        upper_band = stock_price + expected_move
        lower_band = stock_price - expected_move

        return {
            "symbol": symbol,
            "stock_price": stock_price,
            "expiry": expiry,
            "atm_strike": atm_strike,
            "call_price": call_price,
            "put_price": put_price,
            "atm_straddle": atm_straddle,
            "expected_move": expected_move,
            "upper_band": upper_band,
            "lower_band": lower_band,
        }
    except Exception as e:
        logger.error(f"Error calculating expected move for {ticker_symbol_or_obj}: {e}")
        return None


# Example usage:
if __name__ == "__main__":
    res = calculate_expected_move("SPY")
    if res:
        print(f"Current Price for {res['symbol']}: ${res['stock_price']:.2f}")
        print(f"Using Expiry Date: {res['expiry']}")
        print(f"At-The-Money (ATM) Strike Found: ${res['atm_strike']:.2f}")
        print("-" * 40)
        print(f"ATM Call Price: ${res['call_price']:.2f}")
        print(f"ATM Put Price:  ${res['put_price']:.2f}")
        print(f"ATM Straddle:   ${res['atm_straddle']:.2f}")
        print(f"Expected Move:  +/-${res['expected_move']:.2f}")
        print("-" * 40)
        print(f"Upper Band:     ${res['upper_band']:.2f}")
        print(f"Lower Band:     ${res['lower_band']:.2f}")
        print("-" * 40)
