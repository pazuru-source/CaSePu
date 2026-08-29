"""
Configuration module for CaSePu application.
Loads configuration from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / '.env')


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR / "instance" / "options_history.db"}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'timeout': 30
        }
    }

    # Market filters (default values)
    MIN_MARKET_CAP_BILLIONS = float(os.getenv('MIN_MARKET_CAP_BILLIONS', 10))
    MAX_MARKET_CAP_BILLIONS = float(os.getenv('MAX_MARKET_CAP_BILLIONS', 400))
    MAX_PEG_RATIO = float(os.getenv('MAX_PEG_RATIO', 1.5))
    MAX_PE_RATIO = float(os.getenv('MAX_PE_RATIO', 25))
    MIN_PREMIUM_PERCENT_COLLATERAL = float(
        os.getenv('MIN_PREMIUM_PERCENT_COLLATERAL', 0.5))
    MIN_STOCK_PRICE = float(os.getenv('MIN_STOCK_PRICE', 50.0))
    MAX_STOCK_PRICE = float(os.getenv('MAX_STOCK_PRICE', 250.0))
    MIN_CHANCE_OF_PROFIT = float(os.getenv('MIN_CHANCE_OF_PROFIT', 0.80))

    # API/Data fetching
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
    RETRY_DELAY = int(os.getenv('RETRY_DELAY', 2))
    RISK_FREE_RATE = float(os.getenv('RISK_FREE_RATE', 0.04))

    # Concurrency
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', 5))

    # Favorites
    FAVORITE_TICKERS = os.getenv(
        'FAVORITE_TICKERS', 'IREN,CRWV,GLW,RKLB,ASTS,FLY').split(',')
    FAVORITE_TICKERS = [t.strip().upper() for t in FAVORITE_TICKERS]

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # Ensure SECRET_KEY is set in production
    if not os.getenv('SECRET_KEY'):
        raise ValueError(
            "SECRET_KEY environment variable must be set in production")


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(env: str | None = None) -> type:
    """Get configuration class based on environment."""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, DevelopmentConfig)
