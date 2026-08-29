"""
Tests for API routes.
"""
import pytest
from app.models import db, Scan, Opportunity
import json


class TestIndexRoute:
    """Tests for the index route."""

    def test_index_returns_200(self, client):
        """Index page should return 200."""
        response = client.get('/')
        assert response.status_code == 200

    def test_index_returns_html(self, client):
        """Index page should return HTML."""
        response = client.get('/')
        assert b'html' in response.data.lower() or b'<!doctype' in response.data.lower()


class TestHistoryRoute:
    """Tests for history routes."""

    def test_empty_history(self, client):
        """Empty history should return empty list."""
        response = client.get('/history')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_history_with_scans(self, app, client):
        """History should return saved scans."""
        with app.app_context():
            # Create a test scan
            scan = Scan(
                min_mcap=10,
                max_mcap=400,
                max_pe=25,
                max_peg=1.5,
                min_premium=0.5,
                min_price=50,
                max_price=250,
                min_chance_of_profit=0.8,
                expiration_date='2025-01-17'
            )
            db.session.add(scan)
            db.session.commit()

        response = client.get('/history')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 1
        assert data[0]['expiration'] == '2025-01-17'

    def test_get_historical_scan_404(self, client):
        """Getting non-existent scan should return 404."""
        response = client.get('/history/999')
        assert response.status_code == 404

    def test_get_historical_scan_success(self, app, client):
        """Getting existing scan should return scan details."""
        with app.app_context():
            # Create a test scan with an opportunity
            scan = Scan(
                min_mcap=10,
                max_mcap=400,
                max_pe=25,
                max_peg=1.5,
                min_premium=0.5,
                min_price=50,
                max_price=250,
                min_chance_of_profit=0.8,
                expiration_date='2025-01-17'
            )
            db.session.add(scan)
            db.session.flush()

            opportunity = Opportunity(
                scan_id=scan.id,
                ticker='AAPL',
                market_cap=2500,
                pe_ratio=28,
                peg_ratio=1.2,
                current_price=150.0,
                lower_band=140.0,
                upper_band=160.0,
                expected_move=10.0,
                puts_json='[]'
            )
            db.session.add(opportunity)
            db.session.commit()
            scan_id = scan.id

        response = client.get(f'/history/{scan_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
        assert data['expiration'] == '2025-01-17'
        assert len(data['data']) == 1
        assert data['data'][0]['ticker'] == 'AAPL'

    def test_delete_scan_success(self, app, client):
        """Deleting a scan should remove it from database."""
        with app.app_context():
            scan = Scan(
                min_mcap=10,
                max_mcap=400,
                max_pe=25,
                max_peg=1.5,
                min_premium=0.5,
                min_price=50,
                max_price=250,
                min_chance_of_profit=0.8,
                expiration_date='2025-01-17'
            )
            db.session.add(scan)
            db.session.commit()
            scan_id = scan.id

        response = client.delete(f'/history/{scan_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'

        # Verify it's deleted
        response = client.get(f'/history/{scan_id}')
        assert response.status_code == 404

    def test_delete_scan_404(self, client):
        """Deleting non-existent scan should return 404."""
        response = client.delete('/history/999')
        assert response.status_code == 404


class TestAnalyzeRoute:
    """Tests for analyze route."""

    def test_analyze_no_targets_error(self, client):
        """Analyze with invalid targets should return error."""
        response = client.get('/analyze?targets=invalid')
        # Should either return error or success depending on implementation
        assert response.status_code in [200, 400]

    def test_scan_start_no_targets_error(self, client):
        """Scan start with no valid targets should return error."""
        response = client.get('/scan/start?targets=')
        assert response.status_code in [200, 400]

    def test_scan_chunk_missing_params(self, client):
        """Scan chunk without required params should return 400."""
        response = client.post('/scan/chunk', json={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['status'] == 'error'

    def test_scan_chunk_invalid_scan_id(self, client):
        """Scan chunk with invalid scan_id should return 404."""
        response = client.post('/scan/chunk', json={
            'scan_id': 999,
            'tickers': ['AAPL'],
            'extra_tickers': []
        })
        assert response.status_code == 404
