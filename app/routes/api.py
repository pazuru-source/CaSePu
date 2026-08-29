"""
API routes for CaSePu application.
Handles HTTP endpoints for scanning, history, and data retrieval.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, List
from flask import render_template, jsonify, request
from app.routes import api_bp
from app.models import db, Scan, Opportunity
from app.config import get_config
from app.exceptions import ValidationError, TickerDataError, OptionsChainError
from app.utils import get_next_friday_expiration
from app.utils.data_fetching import (
    get_sp500_tickers,
    get_nasdaq100_tickers
)
from app.services import process_tickers_parallel
from expected_move import calculate_expected_move

logger = logging.getLogger(__name__)
config = get_config()


# ============================================================================
# Helper Functions
# ============================================================================

def _validate_and_parse_request_targets() -> Tuple[List[str], List[str]]:
    """
    Validate and parse targets and extra_tickers from request arguments.

    Returns:
        Tuple of (targets list, extra_tickers list)

    Raises:
        ValidationError: If inputs are invalid
    """
    targets = request.args.get('targets', 'favorites,custom').split(',')
    targets = [t.strip().lower() for t in targets if t.strip()]

    if not targets:
        raise ValidationError("No targets specified")

    extra_tickers_raw = request.args.get('extra_tickers', '')
    extra_tickers = [
        t.strip().upper() for t in extra_tickers_raw.split(',') if t.strip()
    ]

    return targets, extra_tickers


def _get_tickers_for_targets(targets: List[str], extra_tickers: List[str]) -> List[str]:
    """
    Gather all tickers based on requested targets.

    Args:
        targets: List of target sources ('sp500', 'nasdaq100', 'favorites', 'custom')
        extra_tickers: User-provided custom tickers

    Returns:
        Deduplicated list of all tickers
    """
    all_tickers: List[str] = []

    if 'sp500' in targets:
        sp500_tickers = get_sp500_tickers()
        all_tickers.extend(sp500_tickers)
        logger.info(f"Added {len(sp500_tickers)} S&P 500 tickers")

    if 'nasdaq100' in targets:
        nasdaq_tickers = get_nasdaq100_tickers()
        all_tickers.extend(nasdaq_tickers)
        logger.info(f"Added {len(nasdaq_tickers)} NASDAQ-100 tickers")

    if 'favorites' in targets:
        all_tickers.extend(config.FAVORITE_TICKERS)
        logger.info(f"Added {len(config.FAVORITE_TICKERS)} favorite tickers")

    if 'custom' in targets:
        all_tickers.extend(extra_tickers)
        logger.info(f"Added {len(extra_tickers)} custom tickers")

    # Remove duplicates and sort for consistency
    return sorted(list(set(all_tickers)))


def _save_opportunities_to_db(
    scan_id: int,
    opportunities: List[Dict[str, Any]]
) -> None:
    """
    Save discovered opportunities to database.

    Args:
        scan_id: ID of the scan session
        opportunities: List of opportunity dictionaries

    Raises:
        Exception: If database operation fails
    """
    try:
        for opp_data in opportunities:
            opp = Opportunity(
                scan_id=scan_id,
                ticker=opp_data['ticker'],
                market_cap=opp_data.get('market_cap', 0),
                pe_ratio=opp_data.get('pe_ratio'),
                peg_ratio=opp_data.get('peg_ratio'),
                current_price=opp_data.get('current_price'),
                lower_band=opp_data.get('lower_band'),
                upper_band=opp_data.get('upper_band'),
                expected_move=opp_data.get('expected_move'),
                puts_json=opp_data['puts_json']
            )
            db.session.add(opp)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving opportunities to database: {e}")
        raise


# ============================================================================
# Routes
# ============================================================================

@api_bp.route('/')
def index():
    """Render the main index page with configuration."""
    configs = {
        'MIN_MCAP': config.MIN_MARKET_CAP_BILLIONS,
        'MAX_MCAP': config.MAX_MARKET_CAP_BILLIONS,
        'MAX_PE': config.MAX_PE_RATIO,
        'MAX_PEG': config.MAX_PEG_RATIO,
        'MIN_PREM': config.MIN_PREMIUM_PERCENT_COLLATERAL,
        'MIN_PRICE': config.MIN_STOCK_PRICE,
        'MAX_PRICE': config.MAX_STOCK_PRICE,
        'MIN_PROB': config.MIN_CHANCE_OF_PROFIT
    }
    return render_template('index.html', configs=configs)


@api_bp.route('/analyze')
def analyze():
    """
    Perform a complete analysis in a single request.

    Query Parameters:
        - targets: Comma-separated list of targets (sp500, nasdaq100, favorites, custom)
        - extra_tickers: Comma-separated list of custom tickers

    Returns:
        JSON with analysis results and scan ID
    """
    try:
        analysis_start_time = datetime.now()

        # Parse and validate request
        targets, extra_tickers = _validate_and_parse_request_targets()
        all_tickers = _get_tickers_for_targets(targets, extra_tickers)

        if not all_tickers:
            return jsonify({
                'status': 'error',
                'message': 'No tickers selected for analysis'
            }), 400

        logger.info(
            f"Analysis started | Targets: {targets} | "
            f"Total tickers: {len(all_tickers)}"
        )

        # Create scan record
        target_exp = get_next_friday_expiration()
        new_scan = Scan(
            min_mcap=config.MIN_MARKET_CAP_BILLIONS,
            max_mcap=config.MAX_MARKET_CAP_BILLIONS,
            max_pe=config.MAX_PE_RATIO,
            max_peg=config.MAX_PEG_RATIO,
            min_premium=config.MIN_PREMIUM_PERCENT_COLLATERAL,
            min_price=config.MIN_STOCK_PRICE,
            max_price=config.MAX_STOCK_PRICE,
            min_chance_of_profit=config.MIN_CHANCE_OF_PROFIT,
            expiration_date=target_exp
        )
        db.session.add(new_scan)
        db.session.flush()
        scan_id = new_scan.id

        # Process all tickers in parallel
        results = process_tickers_parallel(
            all_tickers,
            target_exp,
            extra_tickers,
            config.FAVORITE_TICKERS,
            max_workers=config.MAX_WORKERS
        )

        # Prepare opportunities for saving
        opportunities_to_save = []
        for result in results:
            opportunities_to_save.append({
                'ticker': result['ticker'],
                'market_cap': result['fundamentals'].get('market_cap_billions', 0),
                'pe_ratio': result['fundamentals'].get('trailing_pe'),
                'peg_ratio': result['fundamentals'].get('peg_ratio'),
                'current_price': result['fundamentals'].get('current_price'),
                'lower_band': result['fundamentals'].get('lower_band'),
                'upper_band': result['fundamentals'].get('upper_band'),
                'expected_move': result['fundamentals'].get('expected_move'),
                'puts_json': json.dumps(result['puts'])
            })

        # Save to database
        _save_opportunities_to_db(scan_id, opportunities_to_save)
        db.session.commit()

        analysis_end_time = datetime.now()
        duration = analysis_end_time - analysis_start_time

        logger.info(
            f"Analysis completed | Found {len(results)} opportunities | "
            f"Duration: {duration}"
        )

        return jsonify({
            'status': 'success',
            'data': results,
            'expiration': target_exp,
            'scan_id': scan_id,
            'duration_seconds': duration.total_seconds()
        })

    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Analysis error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Analysis failed: {str(e)}'
        }), 500


@api_bp.route('/scan/start')
def scan_start():
    """
    Initialize a new scan session for chunked processing.

    Query Parameters:
        - targets: Comma-separated list of targets
        - extra_tickers: Comma-separated list of custom tickers

    Returns:
        JSON with scan_id and list of tickers to process
    """
    try:
        targets, extra_tickers = _validate_and_parse_request_targets()
        all_tickers = _get_tickers_for_targets(targets, extra_tickers)

        if not all_tickers:
            return jsonify({
                'status': 'error',
                'message': 'No tickers selected for scanning'
            }), 400

        # Create scan record
        target_exp = get_next_friday_expiration()
        new_scan = Scan(
            min_mcap=config.MIN_MARKET_CAP_BILLIONS,
            max_mcap=config.MAX_MARKET_CAP_BILLIONS,
            max_pe=config.MAX_PE_RATIO,
            max_peg=config.MAX_PEG_RATIO,
            min_premium=config.MIN_PREMIUM_PERCENT_COLLATERAL,
            min_price=config.MIN_STOCK_PRICE,
            max_price=config.MAX_STOCK_PRICE,
            min_chance_of_profit=config.MIN_CHANCE_OF_PROFIT,
            expiration_date=target_exp
        )
        db.session.add(new_scan)
        db.session.commit()

        logger.info(
            f"Scan started | ID: {new_scan.id} | "
            f"Targets: {targets} | Total tickers: {len(all_tickers)}"
        )

        return jsonify({
            'status': 'success',
            'scan_id': new_scan.id,
            'tickers': all_tickers,
            'expiration': target_exp
        })

    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Scan start error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Failed to start scan: {str(e)}'
        }), 500


@api_bp.route('/scan/chunk', methods=['POST'])
def scan_chunk():
    """
    Process a chunk of tickers for an active scan.

    Request JSON:
        - scan_id: ID of active scan session
        - tickers: List of ticker symbols to process
        - extra_tickers: List of custom tickers

    Returns:
        JSON with results from processing this chunk
    """
    try:
        data = request.get_json() or {}
        scan_id = data.get('scan_id')
        tickers = data.get('tickers', [])
        extra_tickers = data.get('extra_tickers', [])

        if not scan_id or not tickers:
            return jsonify({
                'status': 'error',
                'message': 'Missing scan_id or tickers'
            }), 400

        # Verify scan exists
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return jsonify({
                'status': 'error',
                'message': f'Scan {scan_id} not found'
            }), 404

        # Process chunk
        results = process_tickers_parallel(
            tickers,
            scan.expiration_date,
            extra_tickers,
            config.FAVORITE_TICKERS,
            max_workers=config.MAX_WORKERS
        )

        # Save results
        opportunities_to_save = []
        for result in results:
            opportunities_to_save.append({
                'ticker': result['ticker'],
                'market_cap': result['fundamentals'].get('market_cap_billions', 0),
                'pe_ratio': result['fundamentals'].get('trailing_pe'),
                'peg_ratio': result['fundamentals'].get('peg_ratio'),
                'current_price': result['fundamentals'].get('current_price'),
                'lower_band': result['fundamentals'].get('lower_band'),
                'upper_band': result['fundamentals'].get('upper_band'),
                'expected_move': result['fundamentals'].get('expected_move'),
                'puts_json': json.dumps(result['puts'])
            })

        if opportunities_to_save:
            _save_opportunities_to_db(scan_id, opportunities_to_save)

        logger.info(
            f"Chunk processed | Scan: {scan_id} | "
            f"Tickers: {len(tickers)} | Found: {len(results)}"
        )

        return jsonify({
            'status': 'success',
            'data': results
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Scan chunk error: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Chunk processing failed: {str(e)}'
        }), 500


@api_bp.route('/history')
def history():
    """
    Retrieve list of all historical scans.

    Returns:
        JSON array of scan records
    """
    try:
        scans = Scan.query.order_by(Scan.timestamp.desc()).all()
        return jsonify([s.to_dict() for s in scans])
    except Exception as e:
        logger.error(f"History retrieval error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to retrieve history'
        }), 500


@api_bp.route('/history/<int:scan_id>')
def get_historical_scan(scan_id: int):
    """
    Retrieve details and opportunities for a specific historical scan.

    Args:
        scan_id: ID of the scan to retrieve

    Returns:
        JSON with scan details and opportunities
    """
    try:
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return jsonify({
                'status': 'error',
                'message': f'Scan {scan_id} not found'
            }), 404

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
                'min_price': scan.min_price or 50.0,
                'max_price': scan.max_price or 250.0,
                'min_chance_of_profit': scan.min_chance_of_profit or 0.80
            }
        })
    except Exception as e:
        logger.error(f"Historical scan retrieval error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve scan: {str(e)}'
        }), 500


@api_bp.route('/history/<int:scan_id>', methods=['DELETE'])
def delete_scan(scan_id: int):
    """
    Delete a historical scan and its associated opportunities.

    Args:
        scan_id: ID of the scan to delete

    Returns:
        JSON with status
    """
    try:
        scan = db.session.get(Scan, scan_id)
        if not scan:
            return jsonify({
                'status': 'error',
                'message': f'Scan {scan_id} not found'
            }), 404

        db.session.delete(scan)
        db.session.commit()

        logger.info(f"Scan {scan_id} deleted successfully")

        return jsonify({
            'status': 'success',
            'message': f'Scan {scan_id} deleted successfully'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Scan deletion error: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to delete scan: {str(e)}'
        }), 500
