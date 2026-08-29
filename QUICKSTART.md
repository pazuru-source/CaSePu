# 🚀 Quick Start Guide

## For Developers Already Using CaSePu

If you have an existing installation, here's how to migrate:

### 1. **Backup Your Data**
```bash
# Save your database
cp instance/options_history.db instance/options_history.db.backup
```

### 2. **Update Code**
```bash
# Pull the latest refactored version
git pull origin main

# Create new virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate     # Windows
```

### 3. **Install New Dependencies**
```bash
pip install -r requirements.txt
```

### 4. **Configure Environment**
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your preferences (optional - defaults are usually fine)
```

### 5. **Verify Setup**
```bash
# Run tests
pytest

# Should see output like:
# test_calculations.py::TestCalculateChanceOfProfit::test_basic_calculation PASSED
# test_api.py::TestIndexRoute::test_index_returns_200 PASSED
# ... (multiple tests passing)
```

### 6. **Run Application**
```bash
python run.py
# Server starts at http://127.0.0.1:5001
```

---

## For New Users

1. **Clone repo**
   ```bash
   git clone https://github.com/your-username/CaSePu.git
   cd CaSePu
   ```

2. **Setup**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. **Run**
   ```bash
   python run.py
   ```

4. **Visit** http://127.0.0.1:5001

---

## Key Improvements You'll Notice

| Change | Benefit |
|--------|---------|
| Environment variables | Easier configuration per machine |
| Modular structure | Easier to understand and extend |
| Type hints | Better IDE support and autocomplete |
| Tests | Confidence that changes don't break things |
| Documentation | Easier onboarding and troubleshooting |

---

## Understanding the New Structure

```
app/
├── __init__.py       → Creates Flask app (app factory pattern)
├── config.py         → All configuration (reads from .env)
├── models.py         → Database models
├── exceptions.py     → Custom error types
├── routes/           → HTTP endpoints
│   └── api.py        → All route handlers
├── services/         → Business logic
│   ├── options_service.py   → Options analysis
│   └── ticker_service.py    → Ticker processing
└── utils/            → Utilities
    ├── calculations.py      → Math functions
    └── data_fetching.py     → API calls
```

**Old way:** Find logic scattered throughout app.py  
**New way:** Clear, organized structure

---

## Common Tasks

### Change a Setting
```env
# .env file
MIN_STOCK_PRICE=100      # Changed from 50
```

### Add a Custom Ticker
```env
# .env file
FAVORITE_TICKERS=AAPL,MSFT,GOOGL,AAPL
```

### Run Tests
```bash
pytest                          # All tests
pytest tests/test_api.py       # Specific file
pytest -k "test_basic"         # Matching pattern
pytest --cov=app               # With coverage
```

### Check Code Quality
```bash
flake8 app/                     # Find style issues
black app/                      # Auto-format
mypy app/                       # Type checking
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'app'"
```bash
# Make sure you're in the project root directory
cd CaSePu/
python run.py
```

### "No database found"
```bash
# Database is auto-created on first run
# If issues persist:
rm instance/options_history.db
python run.py  # Recreates it
```

### "PORT 5001 already in use"
```bash
# Change port in .env
FLASK_PORT=5002
python run.py
```

### Tests failing
```bash
# Ensure you're in virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
pytest
```

---

## Production Deployment

### Using Gunicorn

```bash
export FLASK_ENV=production
export SECRET_KEY=your-very-secure-key
export DATABASE_URL=/var/lib/casepu/options.db

gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

### Using Docker (Example)

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "wsgi:app"]
```

---

## Migration from Old Code

The refactored code is **100% backward compatible** with your data:
- All database queries still work
- All API endpoints are the same
- Configuration is just externalized (optional to use)

You can gradually adopt new patterns as you develop features.

---

## What's New?

### Better Error Messages
```
Before: "Error processing ticker"
After:  "TickerDataError: Failed to fetch AAPL data: 404 Not Found"
```

### Proper Separation
```
Before: Complex 600-line app.py
After:  Simple 50-line routes, complex logic in services
```

### Testing
```
Before: Manual testing only
After:  pytest suite with 20+ test cases
```

### Configuration
```
Before: Edit app.py, restart server
After:  Edit .env, takes effect immediately
```

---

## Next Steps

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the structure
2. Read [README.md](README.md) for detailed documentation
3. Run tests: `pytest --cov=app`
4. Explore the code - it's much cleaner now!
5. Extend with new features using the new patterns

---

## Questions?

- Check [ARCHITECTURE.md](ARCHITECTURE.md) for design details
- Check [README.md](README.md) for setup details
- Check [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) for what changed
- Review code comments - they're comprehensive

Happy coding! 🎉
