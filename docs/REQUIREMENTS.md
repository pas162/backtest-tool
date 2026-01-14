# Requirements Table - Backtesting Platform

> [!CAUTION]
> **This document is the source of truth. All development must comply with these requirements.**

---

## Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | Fetch OHLCV data from Binance Futures API | Must | ⬜ |
| FR-02 | Store data in PostgreSQL for reuse | Must | ⬜ |
| FR-03 | Detect and fill data gaps automatically | Must | ⬜ |
| FR-04 | Allow custom time range selection for backtest | Must | ⬜ |
| FR-05 | Convert PineScript VWAP+ST+EMA to Python | Must | ⬜ |
| FR-06 | Run multiple strategies in parallel | Must | ⬜ |
| FR-07 | Display equity curve and trade history | Must | ⬜ |
| FR-08 | Support multiple symbols (start with SOLUSDT) | Must | ⬜ |
| FR-09 | Optimize strategy parameters (grid search) | Should | ⬜ |
| FR-10 | Export backtest results to CSV/JSON | Should | ⬜ |

---

## Non-Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NFR-01 | All services run in Docker containers | Must | ⬜ |
| NFR-02 | Use Docker Compose for orchestration | Must | ⬜ |
| NFR-03 | Backend response time < 500ms for API | Should | ⬜ |
| NFR-04 | Dashboard works without React knowledge | Must | ⬜ |
| NFR-05 | Database schema supports incremental data updates | Must | ⬜ |

---

## Technical Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.11 | Best ecosystem for backtesting |
| Backtesting Library | backtesting.py | Lightweight, fast, good visualization |
| Web Framework | FastAPI | Async, fast, auto-docs |
| Database | PostgreSQL 16 | Reliable, good for time-series |
| Message Queue | Redis | For future realtime trading |
| Data Fetcher | CCXT | Universal exchange support |
| TA Library | pandas-ta | Most complete indicators |
| Frontend | HTML + Vanilla JS + Plotly.js | No framework needed |
| Container | Docker + Docker Compose | Easy deployment |
| VWAP Type | Daily VWAP (reset UTC 00:00) | Standard for crypto |
| Position Sizing | 95% capital per trade | Simple, max exposure |

---

## Database Schema Requirements

| Table | Purpose |
|-------|---------|
| `symbols` | List of tradeable symbols |
| `ohlcv_data` | Historical OHLCV with unique (symbol, timeframe, timestamp) |
| `data_ranges` | Track fetched data ranges for gap detection |
| `strategies` | Registry of available strategies |
| `backtest_runs` | History of backtest executions |
| `backtest_trades` | Individual trades from backtests |

---

## API Endpoints Required

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/symbols` | List available symbols |
| GET | `/api/strategies` | List available strategies |
| POST | `/api/data/fetch` | Fetch & store new data |
| GET | `/api/data/status` | Check data availability for range |
| POST | `/api/backtest/run` | Execute backtest |
| GET | `/api/backtest/{id}` | Get backtest results |
| GET | `/api/backtest/{id}/trades` | Get trade list |
| GET | `/api/backtest/{id}/equity` | Get equity curve data |

---

## Constraints

1. **No hardcoded API keys** - Use environment variables
2. **Data must persist** - Use Docker volumes for PostgreSQL
3. **Idempotent data fetching** - Don't duplicate OHLCV rows
4. **Graceful error handling** - Never crash on API failures
