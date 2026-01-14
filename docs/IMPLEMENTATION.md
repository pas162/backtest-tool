# Multi-Strategy Backtesting Platform - Implementation Plan

Build a backtesting platform that runs entirely in Docker, with PostgreSQL for data caching and automatic gap-filling support.

---

## Component 1: Docker Infrastructure

### [NEW] docker-compose.yml
```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    environment:
      - DATABASE_URL=postgresql+asyncpg://backtest:backtest@postgres:5432/backtest_db
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./backend:/app/backend

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: backtest_db
      POSTGRES_USER: backtest
      POSTGRES_PASSWORD: backtest
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  postgres_data:
```

### [NEW] Dockerfile
Python 3.11 with all dependencies

---

## Component 2: Database Schema

### [NEW] backend/database/models.py

```sql
-- symbols: List of coins
CREATE TABLE symbols (
    id SERIAL PRIMARY KEY,
    name VARCHAR(20) UNIQUE NOT NULL,
    exchange VARCHAR(20) DEFAULT 'binance',
    is_active BOOLEAN DEFAULT true
);

-- ohlcv_data: Candlestick data
CREATE TABLE ohlcv_data (
    id BIGSERIAL PRIMARY KEY,
    symbol_id INTEGER REFERENCES symbols(id),
    timeframe VARCHAR(5) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(20,8),
    high DECIMAL(20,8),
    low DECIMAL(20,8),
    close DECIMAL(20,8),
    volume DECIMAL(20,8),
    UNIQUE(symbol_id, timeframe, timestamp)
);

-- data_ranges: Track fetched ranges
CREATE TABLE data_ranges (
    id SERIAL PRIMARY KEY,
    symbol_id INTEGER REFERENCES symbols(id),
    timeframe VARCHAR(5) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    candle_count INTEGER,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- backtest_runs: Backtest history
CREATE TABLE backtest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100),
    symbol_id INTEGER REFERENCES symbols(id),
    timeframe VARCHAR(5),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    params JSONB,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Gap-Filling Logic:**
```
User requests: 2024-01-01 → 2024-06-30

data_ranges has:
  - 2024-01-01 → 2024-02-28 ✓
  - 2024-04-01 → 2024-06-30 ✓

Gaps detected:
  - 2024-03-01 → 2024-03-31 ← needs fetch
```

---

## Component 3: Data Fetcher

### [NEW] backend/data/fetcher.py

```python
class DataFetcher:
    async def get_data(self, symbol: str, timeframe: str, 
                       start: datetime, end: datetime) -> pd.DataFrame:
        """
        1. Query data_ranges to find gaps
        2. Fetch only missing ranges from Binance
        3. Insert new data into ohlcv_data
        4. Update data_ranges
        5. Return full DataFrame from database
        """
```

---

## Component 4: Strategy Engine

### [NEW] backend/strategies/base.py
Abstract base class with standardized interface

### [NEW] backend/strategies/vwap_supertrend_ema.py

| Indicator | Implementation |
|-----------|---------------|
| EMA 21/50 | `pandas_ta.ema()` |
| SuperTrend | `pandas_ta.supertrend()` |
| VWAP (Daily) | Custom: reset at UTC 00:00 |
| Stoch RSI | `pandas_ta.stochrsi()` |

Signals: `signal_pullback_buy`, `signal_pullback_sell`, `signal_reversal_buy`, `signal_reversal_sell`

---

## Component 5: Backtesting Engine

### [NEW] backend/engine/backtester.py
- Wrapper for backtesting.py
- Commission: 0.1% (Binance Futures)
- Position size: 95% capital

### [NEW] backend/engine/parallel.py
- `ProcessPoolExecutor` to run multiple strategies

---

## Component 6: FastAPI Backend

### [NEW] backend/api/server.py

| Endpoint | Purpose |
|----------|---------|
| `GET /api/symbols` | List symbols |
| `GET /api/strategies` | List strategies |
| `POST /api/data/fetch` | Fetch data for range |
| `GET /api/data/status` | Check data availability |
| `POST /api/backtest/run` | Run backtest |
| `GET /api/backtest/{id}` | Get results |

---

## Component 7: Dashboard (HTML + Plotly.js)

### [NEW] frontend/
- `index.html` - Main dashboard
- `js/app.js` - API calls & chart rendering
- `css/styles.css` - Dark theme

Features:
- Symbol dropdown (SOLUSDT, expandable)
- Date range picker (start/end date)
- Strategy selector
- Results: Metrics table + Equity curve + Trades table

---

## Project Structure

```
backtest-tool/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── docs/
│   ├── REQUIREMENTS.md
│   ├── IMPLEMENTATION.md
│   └── TRACKING.md
├── backend/
│   ├── config.py
│   ├── database/
│   ├── data/
│   ├── strategies/
│   ├── engine/
│   └── api/
├── frontend/
│   ├── index.html
│   ├── js/app.js
│   └── css/styles.css
└── tests/
```

---

## Verification Plan

### Automated
```bash
docker compose up -d
docker compose exec app pytest tests/ -v
docker compose exec postgres psql -U backtest -d backtest_db -c "SELECT COUNT(*) FROM ohlcv_data;"
```

### Manual
1. Open http://localhost:8000
2. Select SOLUSDT, 1h, 2024-01-01 to 2024-06-30
3. Click "Fetch Data" → verify gap-filling works
4. Select strategy, click "Run Backtest"
5. Verify equity curve and metrics display
