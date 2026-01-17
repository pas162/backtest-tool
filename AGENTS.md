# AI Trading Replay - Developer Guide

> Instructions for AI coding assistants (Copilot, Claude, Cursor, Windsurf, etc.)

## Architecture Overview

This is a **crypto trading backtesting platform** with ML-powered replay simulation. The system follows a clear separation:

```
Frontend (Vanilla JS) → FastAPI Backend → PostgreSQL/Redis
                              ↓
                    ReplayEngine (bar-by-bar simulation)
                              ↓
                    TradingAgents (ML/OrderFlow/Momentum)
```

### Core Data Flow
1. **Data Fetching**: `BinanceFetcher` pulls OHLCV via ccxt → cached in PostgreSQL
2. **Replay Simulation**: `ReplayEngine` processes bars sequentially, ensuring agents see only historical data (no look-ahead bias)
3. **Trading Decisions**: Agents return `Decision.BUY/SELL/HOLD/CLOSE` with reasoning
4. **ML Predictions**: XGBoost model trained on technical features predicts price direction

## Key Patterns

### Agent Interface Pattern
All trading agents must inherit from `TradingAgent` ([backend/replay/agent.py](backend/replay/agent.py)):
```python
class TradingAgent(ABC):
    @abstractmethod
    def analyze(self, data: pd.DataFrame, order_flow: dict) -> Decision:
        """data contains ONLY historical bars up to current - no future data"""
```

### Strategy Pattern (for backtesting.py integration)
Strategies extend `BaseStrategy` ([backend/strategies/base.py](backend/strategies/base.py)) which wraps `backtesting.Strategy`:
- `init()`: Define indicators using `self.I()`
- `next()`: Trading logic per bar
- `get_parameters()`: Return optimizable params with min/max

### Feature Engineering
`FeatureEngineer` ([backend/ml/features.py](backend/ml/features.py)) creates standardized ML features:
- Column names auto-capitalized: `df['Close']` not `df['close']`
- Minimum 60 bars needed for full feature set (EMAs, RSI, MACD)

## Development Commands

```bash
# Start all services (app, postgres, redis)
docker compose up

# View logs
docker compose logs -f app

# Access app: http://localhost:8000
# PostgreSQL: localhost:5432 (backtest/backtest)
# Redis: localhost:6379
```

### Training ML Model
```bash
# Via API (fetches 90 days of data, trains XGBoost)
curl -X POST http://localhost:8000/api/replay/train \
  -H "Content-Type: application/json" \
  -d '{"symbol": "XRPUSDT", "days": 90}'
```
Model saved to `models/trading_model.pkl`

## API Structure

Routes mounted at `/api` prefix ([backend/config.py](backend/config.py)):
- `/api/data/*` - Data fetching/caching
- `/api/backtest/*` - Strategy backtesting
- `/api/replay/*` - ML replay simulation

Request/response schemas in [backend/api/schemas.py](backend/api/schemas.py) use Pydantic v2.

## Database Models

All models in [backend/database/models.py](backend/database/models.py):
- `Symbol` - Trading pairs (BTCUSDT, etc.)
- `OHLCVData` - Cached candle data with unique constraint on (symbol, timeframe, timestamp)
- `DataRange` - Tracks fetched ranges for gap detection
- `BacktestRun/BacktestTrade` - Historical backtest results

Use async SQLAlchemy sessions:
```python
async with async_session_factory() as db:
    # Use db session
```

## Important Conventions

1. **Leverage handling**: `margin = 1/leverage` for backtesting.py compatibility
2. **Position sizing**: Default 95% of capital per trade (`settings.position_size_pct`)
3. **Commission**: 0.1% default for Binance Futures (`settings.default_commission`)
4. **Logging**: Use `loguru.logger`, not standard logging
5. **Date parsing**: API expects `YYYY-MM-DD` string format

## Frontend

Single-page app in [frontend/index.html](frontend/index.html):
- Uses Lightweight Charts library for TradingView-style charts
- Served as static files via FastAPI `StaticFiles` mount
- Communicates with backend via fetch to `/api/*` endpoints

## Adding New Agents

1. Create class inheriting `TradingAgent` in `backend/replay/` or `backend/ml/`
2. Implement `analyze(data, order_flow) → Decision`
3. Register in [backend/api/routes/replay.py](backend/api/routes/replay.py) `run_replay()` function
