from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Scan(db.Model):
    __tablename__ = 'scans'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    min_mcap = db.Column(db.Float)
    max_mcap = db.Column(db.Float)
    max_pe = db.Column(db.Float)
    max_peg = db.Column(db.Float)
    min_premium = db.Column(db.Float)
    min_price = db.Column(db.Float)
    max_price = db.Column(db.Float)
    min_chance_of_profit = db.Column(db.Float)
    expiration_date = db.Column(db.String(20))
    opportunities = db.relationship('Opportunity', backref='scan', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
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
                'min_chance_of_profit': self.min_chance_of_profit if self.min_chance_of_profit is not None else 0.80
            },
            'expiration': self.expiration_date,
            'opportunity_count': len(self.opportunities)
        }

class Opportunity(db.Model):
    __tablename__ = 'opportunities'
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scans.id'), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    market_cap = db.Column(db.Float)
    pe_ratio = db.Column(db.Float)
    peg_ratio = db.Column(db.Float)
    puts_json = db.Column(db.Text, nullable=False) # Store options list as JSON string

    def to_dict(self):
        return {
            'ticker': self.ticker,
            'fundamentals': {
                'market_cap_billions': self.market_cap,
                'trailing_pe': self.pe_ratio,
                'peg_ratio': self.peg_ratio
            },
            'puts': json.loads(self.puts_json)
        }
