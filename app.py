import yfinance as yf
from flask import Flask, render_template, jsonify, request
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import time
import logging
import json
import os
import requests
import io
import math
from html.parser import HTMLParser
from models import db, Scan, Opportunity
from expected_move import calculate_expected_move
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from functions import *

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///options_history.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'timeout': 30
    }
}


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


db.init_app(app)

with app.app_context():
    db.create_all()
    # Ensure any new columns exist in sqlite if table was created previously
    try:
        with db.engine.connect() as conn:
            res = conn.exec_driver_sql(
                "PRAGMA table_info(opportunities)").fetchall()
            cols = [r[1] for r in res]
            if 'current_price' not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE opportunities ADD COLUMN current_price FLOAT")
            if 'lower_band' not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE opportunities ADD COLUMN lower_band FLOAT")
            conn.commit()
    except Exception as e:
        logger.warning(f"DB schema migration check: {e}")

# --- Configuration ---
MIN_MARKET_CAP_BILLIONS = 10
MAX_MARKET_CAP_BILLIONS = 400
MAX_PEG_RATIO = 1.5
MAX_PE_RATIO = 25
MIN_PREMIUM_PERCENT_COLLATERAL = 0.5  # 0.5%
MIN_STOCK_PRICE = 50.0
MAX_STOCK_PRICE = 250.0
MIN_CHANCE_OF_PROFIT = 0.80  # 80%
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# --- Helper Functions ---
# ... (Helper functions remain the same) ...


def get_ticker_with_retry(ticker_symbol):
    """Attempts to get a Ticker object with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Accessing info often triggers the actual network request
            _ = ticker.info
            return ticker
        except Exception as e:
            logger.warning(
                f"Attempt {attempt + 1} failed for {ticker_symbol}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


def get_next_friday_expiration():
    """Calculates the next Friday's date for options expiration."""
    today = datetime.now()
    days_until_friday = (4 - today.weekday() + 7) % 7  # Friday is weekday 4
    if days_until_friday == 0:  # if today is Friday, get next Friday
        days_until_friday = 7
    next_friday = today + timedelta(days=days_until_friday)
    return int(next_friday.timestamp())  # yfinance expects timestamp


def calculate_chance_of_profit(stock_price, strike, implied_vol, days_to_expiry, risk_free_rate=0.04):
    """
    Calculates the chance of profit (probability of expiring OTM) for a short put option
    using the Black-Scholes d2 formula: P(S_T > K) = N(d2).
    """
    if stock_price <= 0 or strike <= 0 or implied_vol <= 0:
        return 0.5  # Default fallback

    # Time to expiration in years
    T = max(days_to_expiry, 0.5) / 365.0
    vol = max(implied_vol, 0.01)

    try:
        # d2 = [ln(S/K) + (r - v^2/2)T] / [v * sqrt(T)]
        d2 = (math.log(stock_price / strike) +
              (risk_free_rate - 0.5 * vol**2) * T) / (vol * math.sqrt(T))
        # Cumulative normal distribution N(d2)
        prob_otm = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))
        return min(max(prob_otm, 0.0), 1.0)  # Clamp between 0 and 1
    except Exception as e:
        logger.error(f"Error calculating chance of profit: {e}")
        return 0.5


def get_stock_fundamentals(ticker):
    """Fetches key fundamental data for a given ticker object."""
    try:
        info = ticker.info
        market_cap = info.get('marketCap', 0)
        trailing_pe = info.get('trailingPE')
        peg_ratio = info.get('pegRatio')
        current_price = info.get('currentPrice') or info.get(
            'regularMarketPrice') or info.get('previousClose') or 0

        # We return a dict even if some values are None
        return {
            'market_cap_billions': market_cap / 1_000_000_000 if market_cap else 0,
            'trailing_pe': trailing_pe,
            'peg_ratio': peg_ratio,
            'current_price': current_price
        }
    except Exception as e:
        logger.error(f"Error processing fundamentals: {e}")
        return None


def find_cash_secured_puts(ticker, target_date_str, current_price):
    """
    Finds suitable cash-secured put options for a given ticker, date string, and current price.
    Only evaluates options if the ticker has contracts expiring on the exact target Friday date.
    """
    suitable_options = []
    try:
        # Check if requested date exists in available option chains
        available_options = ticker.options
        if not available_options or target_date_str not in available_options:
            return []

        options_chain = ticker.option_chain(target_date_str)
        puts = options_chain.puts

        for index, put in puts.iterrows():
            strike = put['strike']
            bid = put.get('bid', 0)

            # Strike price must be strictly less than current stock price
            if strike >= current_price:
                continue

            # Calculate required premium based on collateral (strike price)
            required_premium = strike * (MIN_PREMIUM_PERCENT_COLLATERAL / 100)

            # Ensure 'bid' is not NaN and is positive; fall back to 'lastPrice' if bid is 0/NaN (e.g. when market is closed)
            if pd.isna(bid) or bid <= 0:
                bid = put.get('lastPrice', 0)

            if pd.isna(bid) or bid <= 0:
                continue

            # Check if BID meets the requirement
            if bid >= required_premium:
                implied_vol = put.get('impliedVolatility', 0)

                # Calculate days to expiry
                try:
                    exp_dt = datetime.strptime(target_date_str, '%Y-%m-%d')
                    days_to_expiry = (
                        exp_dt.date() - datetime.now().date()).days
                except Exception:
                    days_to_expiry = 7  # fallback to 1 week

                chance_of_profit = calculate_chance_of_profit(
                    current_price, strike, implied_vol, days_to_expiry)

                # Filter out high-risk trades
                if chance_of_profit < MIN_CHANCE_OF_PROFIT:
                    continue

                suitable_options.append({
                    'symbol': ticker.ticker,
                    'expiration': target_date_str,
                    'strike': strike,
                    'bid': bid,
                    'ask': put.get('ask', 0),
                    'last_price': put.get('lastPrice', 0),
                    'implied_volatility': implied_vol,
                    'required_premium': required_premium,
                    'chance_of_profit': chance_of_profit
                })
    except Exception as e:
        logger.error(f"Error finding options for {ticker.ticker}: {e}")
    return suitable_options


class WikipediaConstituentsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_tr = False
        self.in_td = False
        self.td_count = 0
        self.tickers = []
        self.current_data = []

    def handle_starttag(self, tag, attrs):
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

    def handle_endtag(self, tag):
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

    def handle_data(self, data):
        if self.in_table and self.in_tr and self.in_td and self.td_count == 1:
            self.current_data.append(data)


def get_tickers_via_parser(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        parser = WikipediaConstituentsParser()
        parser.feed(response.text)
        return parser.tickers
    except Exception as e:
        logger.error(f"Error in WikipediaConstituentsParser: {e}")
        return []


def get_sp500_tickers():
    """Fetches the current S&P 500 components from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        # Use io.StringIO to ensure read_html treats content as HTML, not a filename
        tables = pd.read_html(io.StringIO(response.text), flavor='html5lib')
        df = tables[0]
        tickers = df['Symbol'].tolist()
        # Clean up tickers (Wikipedia uses dots, yfinance uses hyphens)
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        logger.warning(
            f"Error fetching S&P 500 tickers with pandas: {e}. Trying fallback parser.")
        return get_tickers_via_parser(url)


def get_nasdaq100_tickers():
    """Fetches the current NASDAQ-100 components from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        # Use io.StringIO to ensure read_html treats content as HTML, not a filename
        tables = pd.read_html(io.StringIO(response.text), flavor='html5lib')
        # The NASDAQ-100 table is usually the 4th or 5th table on the page
        # We search for the table that has 'Ticker' or 'Symbol' columns
        for table in tables:
            if 'Ticker' in table.columns:
                return table['Ticker'].tolist()
            if 'Symbol' in table.columns:
                return table['Symbol'].tolist()
        return []
    except Exception as e:
        logger.warning(
            f"Error fetching NASDAQ-100 tickers with pandas: {e}. Trying fallback parser.")
        return get_tickers_via_parser(url)


def process_single_ticker(ticker_symbol, target_exp, extra_tickers, fav_tickers):
    """Processes a single ticker: checks fundamentals criteria and finds puts."""
    try:
        is_manual = ticker_symbol in extra_tickers or ticker_symbol in fav_tickers
        ticker_obj = get_ticker_with_retry(ticker_symbol)

        if not ticker_obj:
            logger.warning(
                f"Could not initialize ticker object for {ticker_symbol}")
            return None

        fundamentals = get_stock_fundamentals(ticker_obj)

        meets_criteria = False
        price_ok = False
        if fundamentals:
            mcap = fundamentals['market_cap_billions']
            pe = fundamentals['trailing_pe']
            peg = fundamentals['peg_ratio']
            price = fundamentals['current_price']

            price_ok = (price >= MIN_STOCK_PRICE and price <= MAX_STOCK_PRICE)

            meets_criteria = (
                mcap >= MIN_MARKET_CAP_BILLIONS and mcap <= MAX_MARKET_CAP_BILLIONS and
                (pe is None or pe <= MAX_PE_RATIO) and
                (peg is None or peg <= MAX_PEG_RATIO)
            )

        if price_ok and (meets_criteria or is_manual):
            puts = find_cash_secured_puts(
                ticker_obj, target_exp, fundamentals['current_price'])
            if puts:
                em_data = calculate_expected_move(
                    ticker_obj, target_expiry=target_exp, current_price=fundamentals['current_price'])
                fundamentals['lower_band'] = em_data['lower_band'] if em_data else None
                fundamentals['upper_band'] = em_data['upper_band'] if em_data else None
                fundamentals['expected_move'] = em_data['expected_move'] if em_data else None

                return {
                    'ticker': ticker_symbol,
                    'fundamentals': fundamentals or {},
                    'puts': puts
                }
    except Exception as e:
        logger.error(f"Error processing single ticker {ticker_symbol}: {e}")
    return None

# --- Flask Routes ---


@app.route('/')
def index():
    configs = {
        'MIN_MCAP': MIN_MARKET_CAP_BILLIONS,
        'MAX_MCAP': MAX_MARKET_CAP_BILLIONS,
        'MAX_PE': MAX_PE_RATIO,
        'MAX_PEG': MAX_PEG_RATIO,
        'MIN_PREM': MIN_PREMIUM_PERCENT_COLLATERAL,
        'MIN_PRICE': MIN_STOCK_PRICE,
        'MAX_PRICE': MAX_STOCK_PRICE,
        'MIN_PROB': MIN_CHANCE_OF_PROFIT
    }
    return render_template('index.html', configs=configs)


@app.route('/analyze')
def analyze():
    analysis_start_time = datetime.now()
    # Get targets from query parameters (defaults to 'favorites,custom' if not provided)
    targets = request.args.get('targets', 'favorites,custom').split(',')

    # Get extra tickers from query parameters
    extra_tickers_raw = request.args.get('extra_tickers', '')
    extra_tickers = [t.strip().upper()
                     for t in extra_tickers_raw.split(',') if t.strip()]

    # User-requested specific tickers (hardcoded favorites)
    fav_tickers = ['IREN', 'CRWV', 'GLW', 'RKLB', 'ASTS', 'FLY']

    all_tickers = []

    if 'sp500' in targets:
        all_tickers.extend(get_sp500_tickers())
    if 'nasdaq100' in targets:
        all_tickers.extend(get_nasdaq100_tickers())
    if 'favorites' in targets:
        all_tickers.extend(fav_tickers)
    if 'custom' in targets:
        all_tickers.extend(extra_tickers)

    # Remove duplicates
    all_tickers = list(set(all_tickers))

    logger.info(
        f"Targets: {targets} | Total tickers to analyze: {len(all_tickers)}")

    if not all_tickers:
        return jsonify({'status': 'error', 'message': 'No tickers selected for analysis.'}), 400

    expiration_date_ts = get_next_friday_expiration()
    target_exp = datetime.fromtimestamp(
        expiration_date_ts).strftime('%Y-%m-%d')

    suitable_stocks_for_csp = []
    opportunities_to_save = []

    for ticker_symbol in all_tickers:
        is_manual = ticker_symbol in extra_tickers or ticker_symbol in fav_tickers
        ticker_obj = get_ticker_with_retry(ticker_symbol)

        if not ticker_obj:
            logger.warning(
                f"Could not initialize ticker object for {ticker_symbol}")
            continue

        fundamentals = get_stock_fundamentals(ticker_obj)

        # Filtering Logic
        meets_criteria = False
        price_ok = False
        if fundamentals:
            mcap = fundamentals['market_cap_billions']
            pe = fundamentals['trailing_pe']
            peg = fundamentals['peg_ratio']
            price = fundamentals['current_price']

            price_ok = (price >= MIN_STOCK_PRICE and price <= MAX_STOCK_PRICE)

            # Growth stocks often have no PE/PEG. We allow them if manually added,
            # but for the index scan, we still apply the range.
            meets_criteria = (
                mcap >= MIN_MARKET_CAP_BILLIONS and mcap <= MAX_MARKET_CAP_BILLIONS and
                (pe is None or pe <= MAX_PE_RATIO) and
                (peg is None or peg <= MAX_PEG_RATIO)
            )

        if price_ok and (meets_criteria or is_manual):
            # target_exp is defined as a string 'YYYY-MM-DD'
            puts = find_cash_secured_puts(
                ticker_obj, target_exp, fundamentals['current_price'])
            if puts:
                em_data = calculate_expected_move(
                    ticker_obj, target_expiry=target_exp, current_price=fundamentals['current_price'])
                fundamentals['lower_band'] = em_data['lower_band'] if em_data else None
                fundamentals['upper_band'] = em_data['upper_band'] if em_data else None
                fundamentals['expected_move'] = em_data['expected_move'] if em_data else None

                stock_data = {'ticker': ticker_symbol,
                              'fundamentals': fundamentals or {}, 'puts': puts}
                suitable_stocks_for_csp.append(stock_data)

                opportunities_to_save.append({
                    'ticker': ticker_symbol,
                    'market_cap': fundamentals['market_cap_billions'] if fundamentals else 0,
                    'pe_ratio': fundamentals['trailing_pe'] if fundamentals and fundamentals['trailing_pe'] else 0,
                    'peg_ratio': fundamentals['peg_ratio'] if fundamentals and fundamentals['peg_ratio'] else 0,
                    'current_price': fundamentals['current_price'] if fundamentals else 0,
                    'lower_band': fundamentals.get('lower_band'),
                    'puts_json': json.dumps(puts)
                })

        time.sleep(0.5)

    # Save to database in a single quick transaction
    try:
        new_scan = Scan(
            min_mcap=MIN_MARKET_CAP_BILLIONS,
            max_mcap=MAX_MARKET_CAP_BILLIONS,
            max_pe=MAX_PE_RATIO,
            max_peg=MAX_PEG_RATIO,
            min_premium=MIN_PREMIUM_PERCENT_COLLATERAL,
            min_price=MIN_STOCK_PRICE,
            max_price=MAX_STOCK_PRICE,
            min_chance_of_profit=MIN_CHANCE_OF_PROFIT,
            expiration_date=target_exp
        )
        db.session.add(new_scan)
        db.session.flush()  # Get the scan ID

        for opp_data in opportunities_to_save:
            opp = Opportunity(
                scan_id=new_scan.id,
                ticker=opp_data['ticker'],
                market_cap=opp_data['market_cap'],
                pe_ratio=opp_data['pe_ratio'],
                peg_ratio=opp_data['peg_ratio'],
                current_price=opp_data.get('current_price'),
                lower_band=opp_data.get('lower_band'),
                puts_json=opp_data['puts_json']
            )
            db.session.add(opp)

        db.session.commit()
        scan_id = new_scan.id
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving scan to database: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to save scan to database due to a concurrent write or lock.'}), 500

    analysis_end_time = datetime.now()
    logger.info(
        f"Analysis finished. Found {len(suitable_stocks_for_csp)} stocks. Duration: {analysis_end_time - analysis_start_time}")

    return jsonify({
        'status': 'success',
        'data': suitable_stocks_for_csp,
        'expiration': target_exp,
        'scan_id': scan_id
    })


@app.route('/scan/start')
def scan_start():
    # Get targets from query parameters (defaults to 'favorites,custom' if not provided)
    targets = request.args.get('targets', 'favorites,custom').split(',')

    # Get extra tickers from query parameters
    extra_tickers_raw = request.args.get('extra_tickers', '')
    extra_tickers = [t.strip().upper()
                     for t in extra_tickers_raw.split(',') if t.strip()]

    # User-requested specific tickers (hardcoded favorites)
    fav_tickers = ['IREN', 'CRWV', 'GLW', 'RKLB', 'ASTS', 'FLY']

    all_tickers = []

    if 'sp500' in targets:
        all_tickers.extend(get_sp500_tickers())
    if 'nasdaq100' in targets:
        all_tickers.extend(get_nasdaq100_tickers())
    if 'favorites' in targets:
        all_tickers.extend(fav_tickers)
    if 'custom' in targets:
        all_tickers.extend(extra_tickers)

    # Remove duplicates and sort deterministically
    all_tickers = sorted(list(set(all_tickers)))

    logger.info(
        f"Scan Session Start | Targets: {targets} | Total tickers to scan: {len(all_tickers)}")

    expiration_date_ts = get_next_friday_expiration()
    target_exp = datetime.fromtimestamp(
        expiration_date_ts).strftime('%Y-%m-%d')

    try:
        new_scan = Scan(
            min_mcap=MIN_MARKET_CAP_BILLIONS,
            max_mcap=MAX_MARKET_CAP_BILLIONS,
            max_pe=MAX_PE_RATIO,
            max_peg=MAX_PEG_RATIO,
            min_premium=MIN_PREMIUM_PERCENT_COLLATERAL,
            min_price=MIN_STOCK_PRICE,
            max_price=MAX_STOCK_PRICE,
            min_chance_of_profit=MIN_CHANCE_OF_PROFIT,
            expiration_date=target_exp
        )
        db.session.add(new_scan)
        db.session.commit()
        scan_id = new_scan.id
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error starting scan session: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to initialize scan session in database.'}), 500

    return jsonify({
        'status': 'success',
        'scan_id': scan_id,
        'tickers': all_tickers,
        'expiration': target_exp
    })


@app.route('/scan/chunk', methods=['POST'])
def scan_chunk():
    data = request.get_json() or {}
    scan_id = data.get('scan_id')
    tickers = data.get('tickers', [])
    extra_tickers = data.get('extra_tickers', [])

    if not scan_id or not tickers:
        return jsonify({'status': 'error', 'message': 'Missing scan_id or tickers.'}), 400

    scan = db.session.get(Scan, scan_id)
    if not scan:
        return jsonify({'status': 'error', 'message': 'Scan session not found.'}), 404

    target_exp = scan.expiration_date
    fav_tickers = ['IREN', 'CRWV', 'GLW', 'RKLB', 'ASTS', 'FLY']

    suitable_stocks_for_csp = []
    opportunities_to_save = []

    # Process tickers in this chunk in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_single_ticker, symbol, target_exp, extra_tickers, fav_tickers): symbol
            for symbol in tickers
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                if result:
                    suitable_stocks_for_csp.append(result)
                    opportunities_to_save.append({
                        'ticker': result['ticker'],
                        'market_cap': result['fundamentals'].get('market_cap_billions', 0),
                        'pe_ratio': result['fundamentals'].get('trailing_pe') or 0,
                        'peg_ratio': result['fundamentals'].get('peg_ratio') or 0,
                        'current_price': result['fundamentals'].get('current_price') or 0,
                        'lower_band': result['fundamentals'].get('lower_band'),
                        'puts_json': json.dumps(result['puts'])
                    })
            except Exception as e:
                logger.error(
                    f"Error processing {symbol} in parallel scan: {e}")

    # Save to database in a single transaction
    if opportunities_to_save:
        try:
            for opp_data in opportunities_to_save:
                opp = Opportunity(
                    scan_id=scan.id,
                    ticker=opp_data['ticker'],
                    market_cap=opp_data['market_cap'],
                    pe_ratio=opp_data['pe_ratio'],
                    peg_ratio=opp_data['peg_ratio'],
                    current_price=opp_data.get('current_price'),
                    lower_band=opp_data.get('lower_band'),
                    puts_json=opp_data['puts_json']
                )
                db.session.add(opp)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving chunk to database: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to save opportunities for this chunk.'}), 500

    return jsonify({
        'status': 'success',
        'data': suitable_stocks_for_csp
    })


@app.route('/history')
def history():
    scans = Scan.query.order_by(Scan.timestamp.desc()).all()
    return jsonify([s.to_dict() for s in scans])


@app.route('/history/<int:scan_id>')
def get_historical_scan(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    opportunities = [o.to_dict() for o in scan.opportunities]
    return jsonify({
        'status': 'success',
        'data': opportunities,
        'timestamp': scan.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'expiration': scan.expiration_date,
        'criteria': {
            'min_mcap': scan.min_mcap,
            'max_mcap': scan.max_mcap,
            'max_pe': scan.max_pe,
            'max_peg': scan.max_peg,
            'min_premium': scan.min_premium,
            'min_price': scan.min_price if scan.min_price is not None else 50.0,
            'max_price': scan.max_price if scan.max_price is not None else 250.0,
            'min_chance_of_profit': scan.min_chance_of_profit if scan.min_chance_of_profit is not None else 0.80
        }
    })


@app.route('/history/<int:scan_id>', methods=['DELETE'])
def delete_scan(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    try:
        db.session.delete(scan)
        db.session.commit()
        return jsonify({'status': 'success', 'message': f'Scan {scan_id} deleted successfully.'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting scan {scan_id}: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to delete scan.'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)
