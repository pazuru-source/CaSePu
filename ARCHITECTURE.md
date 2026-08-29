# Architecture & Design Guide

## Overview

CaSePu follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│          Web Interface (UI)             │
│      (HTML, CSS, JavaScript)            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Flask Routes (Blueprint)        │
│      (app/routes/api.py)                │
│  - Request validation                   │
│  - Response formatting                  │
│  - Error handling                       │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│        Service Layer                    │
│  - Business Logic                       │
│  - Orchestration                        │
│  - Parallel Processing                  │
│  (app/services/*.py)                    │
└──────────────┬──────────────────────────┘
               │
      ┌────────┴────────┬────────────┐
      │                 │            │
┌─────▼──────┐  ┌──────▼────┐  ┌───▼─────┐
│  Utilities │  │  Database │  │  Config │
│  (Calcs,  │  │  (Models) │  │  (.env) │
│   Data)   │  │           │  │         │
└────────────┘  └───────────┘  └─────────┘
```

## Layer Details

### 1. Routes Layer (`app/routes/api.py`)
**Responsibility:** Handle HTTP requests/responses

- Parse query/request parameters
- Validate inputs
- Call services
- Format JSON responses
- Handle HTTP errors (400, 404, 500, etc.)

Example:
```python
@api_bp.route('/analyze')
def analyze():
    # 1. Parse request
    targets, extra_tickers = _validate_and_parse_request_targets()
    
    # 2. Call service layer
    results = process_tickers_parallel(...)
    
    # 3. Format response
    return jsonify({'status': 'success', 'data': results})
```

### 2. Service Layer (`app/services/`)

#### `options_service.py`
Implements core business logic for options analysis:
- `find_cash_secured_puts()` - Find suitable options for a ticker
- `validate_ticker_criteria()` - Check if ticker meets screening criteria

#### `ticker_service.py`
Orchestrates ticker processing:
- `process_single_ticker()` - Process one ticker end-to-end
- `process_tickers_parallel()` - Process many tickers concurrently

### 3. Utilities Layer (`app/utils/`)

#### `calculations.py`
Financial and mathematical calculations:
- `calculate_chance_of_profit()` - Black-Scholes probability
- `calculate_required_premium()` - Premium requirement
- `extract_option_price()` - Price extraction logic
- `get_next_friday_expiration()` - Expiration date calculation

#### `data_fetching.py`
External data retrieval:
- `get_ticker_with_retry()` - Fetch yfinance ticker with retry logic
- `get_stock_fundamentals()` - Extract fundamental data
- `get_sp500_tickers()` - Fetch S&P 500 constituents
- `get_nasdaq100_tickers()` - Fetch NASDAQ-100 constituents

### 4. Data Layer (`app/models.py`)
SQLAlchemy ORM models:
- `Scan` - Represents a scan session
- `Opportunity` - Represents a discovered opportunity

### 5. Configuration (`app/config.py`)
Centralized configuration management:
- `Config` - Base configuration
- `DevelopmentConfig` - Development-specific
- `TestingConfig` - Testing-specific
- `ProductionConfig` - Production-specific

All configuration loads from environment variables.

## Data Flow Example: Analyzing Tickers

```
1. User accesses /analyze?targets=sp500&extra_tickers=AAPL

2. Route Handler (api.py):
   ├─ Parse parameters
   ├─ Validate inputs
   └─ Call service layer

3. Service Layer (ticker_service.py):
   ├─ Get all tickers from all sources
   └─ Process in parallel using ThreadPoolExecutor

4. Parallel Processing (services/ticker_service.py):
   For each ticker:
   ├─ Service calls data_fetching for ticker info
   ├─ Service calls options_service to validate criteria
   ├─ If valid, calls options_service to find puts
   ├─ Service calls calculations for probabilities
   └─ Returns result

5. Database (models.py):
   ├─ Save Scan record
   └─ Save Opportunity records

6. Route returns formatted JSON response
```

## Exception Handling

Custom exceptions in `app/exceptions.py`:

```python
try:
    # Route logic
except ValidationError:
    return jsonify({'error': '...'}), 400  # Client error
except TickerDataError:
    return jsonify({'error': '...'}), 500  # Server error
except Exception:
    logger.error(...)  # Log unexpected errors
    return jsonify({'error': '...'}), 500
```

## Type Hints

All functions have type hints for clarity and IDE support:

```python
def find_cash_secured_puts(
    ticker: yf.Ticker,
    target_date_str: str,
    current_price: float,
    min_premium_percent: Optional[float] = None,
    min_chance_of_profit: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Find suitable cash-secured put options."""
    ...
```

## Configuration Precedence

1. Environment variables (highest priority)
2. `.env` file
3. Hardcoded defaults (lowest priority)

```python
# From config.py
MIN_MARKET_CAP_BILLIONS = float(
    os.getenv('MIN_MARKET_CAP_BILLIONS', 10)  # Default: 10
)
```

## Testing Architecture

Tests are organized by layer:

- `test_calculations.py` - Unit tests for utility functions
- `test_api.py` - Integration tests for routes
- `conftest.py` - pytest fixtures and configuration

Example test:
```python
def test_calculate_chance_of_profit(self):
    prob = calculate_chance_of_profit(
        stock_price=100.0,
        strike=100.0,
        implied_vol=0.20,
        days_to_expiry=30
    )
    assert 0.45 <= prob <= 0.55
```

## Concurrency Model

Parallel processing uses Python's `ThreadPoolExecutor`:

```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(process_single_ticker, ticker): ticker
        for ticker in tickers
    }
    for future in as_completed(futures):
        result = future.result()
        # Process result
```

Benefits:
- I/O-bound operations (network calls) run concurrently
- No GIL issues since yfinance releases the GIL
- Configurable worker count via `MAX_WORKERS` env var

## Adding New Features

### Example: Add new screening criterion

1. **Update Config** (`app/config.py`):
   ```python
   NEW_CRITERION = float(os.getenv('NEW_CRITERION', 1.0))
   ```

2. **Add to Service** (`app/services/options_service.py`):
   ```python
   def validate_ticker_criteria(...):
       # Add new check
       if new_criterion > config.NEW_CRITERION:
           return False
   ```

3. **Add Tests** (`tests/test_api.py`):
   ```python
   def test_new_criterion(self):
       # Test new behavior
   ```

4. **Update Routes** if needed (`app/routes/api.py`)

5. **Update Config Template** (`.env.example`)

## Performance Considerations

1. **Parallel Processing**: ThreadPoolExecutor for I/O operations
2. **Database**: SQLite WAL mode for concurrent access
3. **Caching**: Consider implementing caching for ticker fundamentals
4. **Logging**: Async logging in production to avoid blocking

## Deployment Checklist

- [ ] Set `FLASK_ENV=production`
- [ ] Set strong `SECRET_KEY`
- [ ] Set `DEBUG=False`
- [ ] Configure `DATABASE_URL` to persistent location
- [ ] Use Gunicorn with multiple workers
- [ ] Set up reverse proxy (nginx/Apache)
- [ ] Enable HTTPS
- [ ] Configure logging
- [ ] Set resource limits (memory, connections)
