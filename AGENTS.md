# AI Trading Replay - Developer Guide

> Instructions for AI coding assistants (Copilot, Claude, Cursor, Windsurf, etc.)

## Architecture Overview

This is a **crypto trading backtesting platform** with ML-powered replay simulation:

```
Frontend (Vanilla JS) → FastAPI Backend → PostgreSQL/Redis
                              ↓
                    ReplayEngine (bar-by-bar simulation)
                              ↓
                    FastMLAgent (XGBoost predictions - pre-calculated)
```

### Core Data Flow
1. **Data Fetching**: `BinanceFetcher` pulls OHLCV via ccxt → cached in PostgreSQL
2. **Replay Simulation**: `ReplayEngine` processes bars sequentially, ensuring agents see only historical data (no look-ahead bias)
3. **Trading Decisions**: ML agent returns `Decision.BUY/SELL/HOLD/CLOSE` with reasoning
4. **ML Predictions**: XGBoost model trained on Volume & Auction features predicts price direction

### Key Components
| Component | File | Description |
|-----------|------|-------------|
| `ReplayEngine` | `backend/replay/engine.py` | Bar-by-bar simulation with no look-ahead |
| `FastMLAgent` | `backend/ml/fast_agent.py` | Optimized agent - pre-calculates ALL predictions |
| `FeatureEngineer` | `backend/ml/features.py` | Creates 25 Volume & Auction features |
| `ModelTrainer` | `backend/ml/trainer.py` | XGBoost/RandomForest training pipeline |
| `ModelRegistry` | `backend/ml/model_registry.py` | Manages multiple trained models |
| `DataService` | `backend/data/fetcher.py` | Fetches & caches data from Binance |

## Training the ML Model

### Via UI
Click the **🧠 Train Model** button in the frontend to open settings modal.

### Via API (with custom arguments)
```bash
curl -X POST http://localhost:8000/api/replay/train \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "timeframe": "5m",
    "days": 90,
    "lookahead": 10,
    "threshold": 0.008,
    "use_multi_class": true
  }'
```

### Training Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `symbol` | XRPUSDT | Trading pair to train on |
| `timeframe` | 5m | Candle timeframe (1m, 5m, 15m, 1h) |
| `days` | 90 | Days of historical data to use |
| `lookahead` | 10 | Bars to look ahead for label creation |
| `threshold` | 0.008 | Min price change (0.8%) for binary labels |
| `use_multi_class` | true | Use 3-class labels (HOLD/LONG/SHORT) |

### Model Types
- **Binary (legacy)**: 2 classes - UP(1) / DOWN(0)
- **Multi-class (current)**: 3 classes - HOLD(0) / LONG(1) / SHORT(2)

Models saved to `models/` directory and registered in `models/registry.json`

## ML Features (Volume & Auction Theory)

The model uses **25 features** based on Volume and Auction Market Theory:

### Volume Analysis
- `volume_ratio` - Activity level vs 20-bar average
- `volume_trend` - Volume momentum (increasing/decreasing)
- `cvd_normalized` - Cumulative Volume Delta (buyer vs seller control)
- `cvd_momentum_norm` - Change in buying/selling pressure

### Price Action
- `body_ratio` - Candle body/range ratio (conviction)
- `upper_wick_ratio` - Rejection from above
- `lower_wick_ratio` - Rejection from below
- `wick_imbalance` - Net rejection direction
- `close_position` - Where price closed in range (0=low, 1=high)
- `bullish_streak` / `bearish_streak` - Consecutive candles

### Auction/Market Structure
- `va_position` - Price position in Value Area
- `poc_distance` - Distance from Point of Control (fair value)
- `atr_ratio` - Balance vs Imbalance (consolidation vs trending)
- `range_ratio` - Range expansion/contraction

### Support/Resistance
- `dist_to_high` / `dist_to_low` - Distance to recent S/R levels
- `near_high` / `near_low` - At potential S/R zone
- `breakout_up` / `breakout_down` - Breaking levels with volume

### Volume-Price Relationship
- `vol_price_confirm` - Volume confirms price direction
- `effort_result` - Absorption detection (high volume, small move)

## Project Structure

```
backtest-tool/
├── backend/
│   ├── api/routes/          # FastAPI endpoints
│   │   ├── data.py          # /api/data/* - Data fetching
│   │   ├── backtest.py      # /api/backtest/* - Backtesting
│   │   └── replay.py        # /api/replay/* - ML replay
│   ├── ml/                  # ML module
│   │   ├── features.py      # 25 features creation
│   │   ├── trainer.py       # Model training
│   │   ├── fast_agent.py    # Optimized ML agent
│   │   └── model_registry.py # Multi-model management
│   ├── replay/              # Replay engine
│   │   ├── engine.py        # Bar-by-bar simulation
│   │   └── agent.py         # Base TradingAgent class
│   └── data/fetcher.py      # Binance data fetcher
├── frontend/index.html      # Single-page app (2400+ lines)
├── models/                  # Trained ML models (.pkl)
└── docker-compose.yml       # Docker services
```

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
- `/api/replay/models` - List registered models
- `/api/replay/models/{name}/activate` - Set active model
- `/api/symbols` - List available symbols

## Important Conventions

1. **Leverage handling**: `margin = 1/leverage` for backtesting.py compatibility
2. **Position sizing**: Default 95% of capital per trade (`settings.position_size_pct`)
3. **Commission**: 0.1% default for Binance Futures (`settings.default_commission`)
4. **Logging**: Use `loguru.logger`, not standard logging
5. **Date parsing**: API expects `YYYY-MM-DD` string format
6. **Warmup period**: Min 500 bars before trading starts (for indicators)
7. **Feature NaN handling**: ffill → bfill → fill 0
8. **Model format**: `.pkl` file containing `{model, feature_names, model_type}`

## Frontend

Single-page app in [frontend/index.html](frontend/index.html):
- Uses Lightweight Charts library for TradingView-style charts
- **🧠 Train Model** button - opens modal with training settings
- **📊 Load Data** button - runs replay simulation

## Database Schema (PostgreSQL)

| Table | Description |
|-------|-------------|
| `symbols` | Trading pairs (BTCUSDT, XRPUSDT, etc.) |
| `ohlcv_data` | Cached OHLCV candles |
| `data_ranges` | Tracks fetched ranges for gap detection |
| `backtest_runs` | Backtest execution history |
| `backtest_trades` | Individual trade records |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "ML model not trained" | Click 🧠 Train Model button |
| No trades generated | Check min_confidence threshold in FastMLAgent |
| Slow replay | FastMLAgent pre-calculates all predictions |
| Data fetch fails | Check Binance API connectivity, rate limits |
| Database errors | Run `docker compose down -v` to reset volumes |
