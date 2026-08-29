"""CaSePu Flask application factory."""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import get_config
from app.models import db
import logging
import sqlite3
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def create_app(config_name: str = 'development') -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_name: Configuration environment ('development', 'testing', 'production')

    Returns:
        Configured Flask application
    """
    app = Flask(__name__)

    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)

    # Initialize database
    db.init_app(app)

    # Set up SQLite WAL mode for better concurrency
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    # Create database tables and migrate schema
    with app.app_context():
        db.create_all()
        _migrate_database_schema()

    # Register blueprints
    from app.routes import api_bp
    app.register_blueprint(api_bp)

    # Configure logging
    _configure_logging(app)

    return app


def _migrate_database_schema() -> None:
    """Handle database schema migrations for SQLite."""
    try:
        with db.engine.connect() as conn:
            res = conn.exec_driver_sql(
                "PRAGMA table_info(opportunities)"
            ).fetchall()
            cols = [r[1] for r in res]

            # Add missing columns
            if 'current_price' not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE opportunities ADD COLUMN current_price FLOAT"
                )
                logger.info(
                    "Added current_price column to opportunities table")

            if 'lower_band' not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE opportunities ADD COLUMN lower_band FLOAT"
                )
                logger.info("Added lower_band column to opportunities table")

            if 'upper_band' not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE opportunities ADD COLUMN upper_band FLOAT"
                )
                logger.info("Added upper_band column to opportunities table")

            if 'expected_move' not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE opportunities ADD COLUMN expected_move FLOAT"
                )
                logger.info(
                    "Added expected_move column to opportunities table")

            conn.commit()
    except Exception as e:
        logger.warning(f"Database schema migration: {e}")


def _configure_logging(app: Flask) -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=app.config.get('LOG_LEVEL', 'INFO'),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
