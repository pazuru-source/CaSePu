"""
Test suite for CaSePu.
"""
import pytest
from app import create_app
from app.models import db


@pytest.fixture
def app():
    """Create and configure a test instance of the app."""
    app = create_app('testing')

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the app's Click commands."""
    return app.test_cli_runner()
