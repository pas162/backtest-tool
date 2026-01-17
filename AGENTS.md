# AI Trading Replay - Developer Guide

> Instructions for AI coding assistants (Copilot, Claude, Cursor, Windsurf, etc.)

## Architecture Overview

This is a **crypto trading backtesting platform** with ML-powered replay simulation:

```
Frontend (Vanilla JS) → FastAPI Backend → PostgreSQL/Redis
                              ↓
                    ReplayEngine (bar-by-bar simulation)
                              ↓
                    MLTradingAgent (XGBoost predictions)
```

### Core Data Flow
1. **Data Fetching**: `BinanceFetcher` pulls OHLCV via ccxt → cached in PostgreSQL
2. **Replay Simulation**: `ReplayEngine` processes bars sequentially, ensuring agents see only historical data (no look-ahead bias)
3. **Trading Decisions**: ML agent returns `Decision.BUY/SELL/HOLD/CLOSE` with reasoning
4. **ML Predictions**: XGBoost model trained on technical features predicts price direction

## Training the ML Model

### Via UI
Click the **🧠 Train Model** button in the frontend. It trains on the selected symbol with default settings.

### Via API (with custom arguments)
```bash
curl -X POST http://localhost:8000/api/replay/train \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "timeframe": "5m",
    "days": 90,
    "lookahead": 5,
    "threshold": 0.002
  }'
```

### Training Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `symbol` | XRPUSDT | Trading pair to train on |
| `timeframe` | 5m | Candle timeframe (1m, 5m, 15m, 1h) |
| `days` | 90 | Days of historical data to use |
| `lookahead` | 5 | Bars to look ahead for label creation |
| `threshold` | 0.002 | Min price change (0.2%) to label as UP/DOWN |

Model saved to `models/trading_model.pkl`

## Key Patterns

### Agent Interface Pattern
Trading agents inherit from `TradingAgent` ([backend/replay/agent.py](backend/replay/agent.py)):
```python
class TradingAgent(ABC):
    @abstractmethod
    def analyze(self, data: pd.DataFrame, order_flow: dict) -> Decision:
        """data contains ONLY historical bars up to current - no future data"""
```

### Feature Engineering
`FeatureEngineer` ([backend/ml/features.py](backend/ml/features.py)) creates standardized ML features:
- Column names auto-capitalized: `df['Close']` not `df['close']`
- Minimum 60 bars needed for full feature set (EMAs, RSI, MACD, Bollinger Bands)

## Development Commands

```bash
# Start all services (app, postgres, redis)
docker compose up

# View logs
docker compose logs -f app

# Access app: http://localhost:8000
```

## API Structure

Routes mounted at `/api` prefix:
- `/api/data/*` - Data fetching/caching
- `/api/backtest/*` - Strategy backtesting  
- `/api/replay/run` - Run ML replay simulation
- `/api/replay/train` - Train ML model

## Important Conventions

1. **Leverage handling**: `margin = 1/leverage` for backtesting.py compatibility
2. **Position sizing**: Default 95% of capital per trade (`settings.position_size_pct`)
3. **Commission**: 0.1% default for Binance Futures (`settings.default_commission`)
4. **Logging**: Use `loguru.logger`, not standard logging
5. **Date parsing**: API expects `YYYY-MM-DD` string format

## Frontend

Single-page app in [frontend/index.html](frontend/index.html):
- Uses Lightweight Charts library for TradingView-style charts
- **🧠 Train Model** button - trains XGBoost on selected symbol
- **📊 Load Data** button - runs replay simulation
