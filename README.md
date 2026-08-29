# 📊 CaSePu - Cash-Secured Put Finder

A production-grade, high-performance Flask-based web application designed to scan the stock market (S&P 500, NASDAQ-100, favorites, and custom watchlists) and discover high-probability **Cash-Secured Put (CSP)** options opportunities.

The scanner applies rigorous fundamental filters first (Market Cap, P/E, PEG, Stock Price) and then computes options metrics (Premium/Collateral, Implied Volatility, and Chance of Profit using Black-Scholes probability of expiring OTM) to surface low-risk, high-yield trades.

---

## 🚀 Key Features

* **Multi-Index Scanner:** Scan S&P 500, NASDAQ-100, hardcoded Favorites, or custom watchlists
* **Smart Filtering System:**
  * Price range filtering (Default: $50 - $250)
  * Market cap filters (Default: $10B - $400B)
  * Valuation filters (P/E, PEG ratios)
  * Safety margin enforcement (Default: 80% probability of expiring OTM)
* **Parallel Processing:** ThreadPoolExecutor-based concurrent scanning eliminating HTTP timeouts
* **Persistent History:** SQLite database with WAL mode for fast concurrent access
* **PDF Export:** Generate presentation-ready reports
* **Production-Ready Architecture:** Modular design with proper separation of concerns
* **Comprehensive Testing:** Pytest-based test suite with multiple test cases
* **Environment Configuration:** Externalized configuration via .env files

---

## 🛠️ Tech Stack

* **Backend:** Python 3.8+, Flask 3.0, Flask-SQLAlchemy 3.1
* **Database:** SQLite with WAL mode
* **Data Source:** yfinance (Yahoo Finance API)
* **Frontend:** HTML5, CSS3, Bootstrap 5, jsPDF
* **Testing:** pytest, pytest-cov
* **Production:** Gunicorn WSGI server

---

## 📁 Project Structure

```
CaSePu-main/
├── app/                          # Application package
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration management
│   ├── models.py                # SQLAlchemy models
│   ├── exceptions.py            # Custom exceptions
│   ├── routes/
│   │   ├── __init__.py
│   │   └── api.py               # API endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── options_service.py   # Options analysis logic
│   │   └── ticker_service.py    # Ticker processing
│   └── utils/
│       ├── __init__.py
│       ├── calculations.py      # Financial calculations
│       └── data_fetching.py     # Market data retrieval
├── tests/                       # Test suite
│   ├── conftest.py             # pytest configuration
│   ├── test_calculations.py    # Calculation tests
│   └── test_api.py             # API tests
├── templates/                   # HTML templates
│   └── index.html
├── instance/                    # Instance-specific files
├── run.py                      # Development server entry point
├── wsgi.py                     # Production WSGI entry point
├── requirements.txt            # Python dependencies (pinned versions)
├── .env.example               # Environment configuration template
├── .gitignore
└── README.md
```

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Virtual environment (recommended)

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/CaSePu.git
cd CaSePu
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your preferred settings
# (defaults are usually fine for development)
```

### 5. Run the Application

**Development:**
```bash
python run.py
```
Access at `http://127.0.0.1:5001`

**Production:**
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

---

## ⚙️ Configuration

Configuration is managed through environment variables in `.env` file (copy from `.env.example`):

### Market Filtering
```env
MIN_MARKET_CAP_BILLIONS=10
MAX_MARKET_CAP_BILLIONS=400
MAX_PE_RATIO=25
MAX_PEG_RATIO=1.5
MIN_STOCK_PRICE=50.0
MAX_STOCK_PRICE=250.0
MIN_PREMIUM_PERCENT_COLLATERAL=0.5
MIN_CHANCE_OF_PROFIT=0.80
```

### Flask
```env
FLASK_ENV=development
FLASK_DEBUG=False
FLASK_HOST=127.0.0.1
FLASK_PORT=5001
SECRET_KEY=your-secret-key
```

### Database
```env
DATABASE_URL=sqlite:///instance/options_history.db
```

### API & Data Fetching
```env
MAX_RETRIES=3
RETRY_DELAY=2
RISK_FREE_RATE=0.04
MAX_WORKERS=5
```

---

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app tests/

# Run specific test file
pytest tests/test_calculations.py

# Run specific test
pytest tests/test_calculations.py::TestCalculateChanceOfProfit::test_basic_calculation
```

Test coverage report will be generated in `htmlcov/` directory.

---

## 📚 API Endpoints

### Web Interface
- `GET /` - Main dashboard

### Scanning
- `GET /analyze` - Single-request full analysis
- `GET /scan/start` - Initialize chunked scan session
- `POST /scan/chunk` - Process a batch of tickers

### History
- `GET /history` - List all historical scans
- `GET /history/<scan_id>` - Get details of a specific scan
- `DELETE /history/<scan_id>` - Delete a scan

---

## 🏗️ Architecture

### Application Factory Pattern
Flask app is created using the factory pattern in `app/__init__.py`, allowing for:
- Multiple configuration environments
- Easier testing
- Better separation of concerns

### Blueprints
API routes are organized using Flask Blueprints in `app/routes/api.py`

### Service Layer
Business logic is isolated in `app/services/`:
- `options_service.py` - Options analysis
- `ticker_service.py` - Ticker processing and parallel execution

### Utilities
Reusable functions in `app/utils/`:
- `calculations.py` - Financial calculations (Black-Scholes, etc.)
- `data_fetching.py` - Market data retrieval

### Models
ORM models in `app/models.py` with type hints

### Exceptions
Custom exceptions in `app/exceptions.py` for better error handling

---

## 🔐 Security Notes

1. Change `SECRET_KEY` in production
2. Use environment variables for sensitive data
3. Enable HTTPS in production
4. Validate user inputs (already done in routes)
5. Use Gunicorn with reverse proxy (nginx/Apache) in production

---

## 📊 Code Quality

The codebase includes:
- ✅ Type hints on all functions
- ✅ Comprehensive docstrings
- ✅ Custom exception classes
- ✅ Pytest test suite
- ✅ Proper logging throughout
- ✅ Configuration management
- ✅ Modular architecture
- ✅ Error handling

Suggested tools for code quality:
```bash
# Format code
black app/ tests/

# Lint
flake8 app/ tests/

# Type checking
mypy app/
```

---

## 🤝 Contributing

1. Create a feature branch
2. Add tests for new functionality
3. Ensure all tests pass
4. Follow code style guidelines

---

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.
