"""
Database models for CaSePu application.
Defines SQLAlchemy ORM models for Scans and Opportunities.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from typing import Dict, List, Any

db = SQLAlchemy()


class Scan(db.Model):
    """Model representing a single scan operation with filtering criteria."""

    __tablename__ = 'scans'

    id: int = db.Column(db.Integer, primary_key=True)
    timestamp: datetime = db.Column(db.DateTime, default=datetime.utcnow)
    min_mcap: float = db.Column(db.Float)
    max_mcap: float = db.Column(db.Float)
    max_pe: float = db.Column(db.Float)
    max_peg: float = db.Column(db.Float)
    min_premium: float = db.Column(db.Float)
    min_price: float = db.Column(db.Float)
    max_price: float = db.Column(db.Float)
    min_chance_of_profit: float = db.Column(db.Float)
    expiration_date: str = db.Column(db.String(20))
    opportunities: List['Opportunity'] = db.relationship(
        'Opportunity',
        backref='scan',
        lazy=True,
        cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Scan model to dictionary."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'criteria': {
                'min_mcap': self.min_mcap,
                'max_mcap': self.max_mcap,
                'max_pe': self.max_pe,
                'max_peg': self.max_peg,
                'min_premium': self.min_premium,
                'min_price': self.min_price if self.min_price is not None else 50.0,
                'max_price': self.max_price if self.max_price is not None else 250.0,
                'min_chance_of_profit': (
                    self.min_chance_of_profit
                    if self.min_chance_of_profit is not None else 0.80
                )
            },
            'expiration': self.expiration_date,
            'opportunity_count': len(self.opportunities)
        }


class Opportunity(db.Model):
    """Model representing a discovered options opportunity."""

    __tablename__ = 'opportunities'

    id: int = db.Column(db.Integer, primary_key=True)
    scan_id: int = db.Column(
        db.Integer, db.ForeignKey('scans.id'), nullable=False)
    ticker: str = db.Column(db.String(10), nullable=False)
    market_cap: float = db.Column(db.Float)
    pe_ratio: float = db.Column(db.Float)
    peg_ratio: float = db.Column(db.Float)
    current_price: float = db.Column(db.Float)
    lower_band: float = db.Column(db.Float)
    upper_band: float = db.Column(db.Float)
    expected_move: float = db.Column(db.Float)
    puts_json: str = db.Column(db.Text, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert Opportunity model to dictionary."""
        return {
            'ticker': self.ticker,
            'fundamentals': {
                'market_cap_billions': self.market_cap,
                'trailing_pe': self.pe_ratio,
                'peg_ratio': self.peg_ratio,
                'current_price': self.current_price,
                'lower_band': self.lower_band,
                'upper_band': self.upper_band,
                'expected_move': self.expected_move
            },
            'puts': json.loads(self.puts_json)
        }
