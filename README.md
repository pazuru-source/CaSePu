# Options Scanner & Cash-Secured Put Finder

A modern, high-performance Flask-based web application designed to scan the stock market (S&P 500, NASDAQ-100, favorites, and custom watchlists) and discover high-probability **Cash-Secured Put (CSP)** options opportunities.

The scanner applies rigorous fundamental filters first (Market Cap, P/E, PEG, Stock Price) and then computes option metrics (Premium/Collateral, Implied Volatility, and Chance of Profit using Black-Scholes probability of expiring OTM) to surface low-risk, high-yield trades.

---

## 🚀 Key Features

* **Multi-Index Scanner:** Scan S&P 500, NASDAQ-100 (QQQ), hardcoded Favorites, or input your own Custom Watchlist.
* **Smart Filtering System:**
  * **Price Range:** filter stocks between customized boundaries (Default: `$50` - `$250`).
  * **Market Cap:** filter out micro/mega-caps (Default: `$10B` - `$400B`).
  * **Valuation & Growth:** filter by P/E ratio and PEG ratio.
  * **Safety Margin:** enforce a minimum Chance of Profit (Default: `80%` probability of expiring OTM).
* **Chunked & Parallel Execution:** Scans hundreds of stocks incrementally in batch chunks via backend multi-threading (`ThreadPoolExecutor`), eliminating HTTP timeout errors and providing real-time progress updates.
* **Persistent History:** Automatically saves scan criteria and discovered opportunities in a local SQLite database (`options_history.db`) utilizing SQLite WAL mode for fast concurrent transactions.
* **Interactive TUI CLI & TUI Web App:** Fully compatible with both web interface and terminal commands.
* **PDF Export:** Export any live scan or historical scan results into a clean, presentation-ready PDF report.

---

## 🛠️ Tech Stack

* **Backend:** Python, Flask, Flask-SQLAlchemy (SQLite)
* **API Integration:** `yfinance` (Yahoo Finance API)
* **Frontend:** HTML5, CSS3, JS, Bootstrap 5, Bootstrap Icons, jsPDF
* **Concurrency:** `concurrent.futures.ThreadPoolExecutor`

---

## 📦 Installation & Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/options-scanner.git
   cd options-scanner
   ```

2. **Set up a Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application:**
   ```bash
   python app.py
   ```
   The Flask development server will start at `http://127.0.0.1:5001/`.

---

## 📈 Configuration

You can customize the filtering criteria directly at the top of [app.py](file:///C:/Users/adhru/Desktop/gemini-projects/options/app.py):

```python
MIN_MARKET_CAP_BILLIONS = 10
MAX_MARKET_CAP_BILLIONS = 400
MAX_PEG_RATIO = 1.5
MAX_PE_RATIO = 25
MIN_PREMIUM_PERCENT_COLLATERAL = 0.5  # 0.5% premium yield
MIN_STOCK_PRICE = 50.0
MAX_STOCK_PRICE = 250.0
MIN_CHANCE_OF_PROFIT = 0.80           # 80% OTM probability
```

---

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.
