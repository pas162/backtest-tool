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
4. **ML Predictions**: XGBoost model trained on Volume & Auction features predicts price direction

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
- **🧠 Train Model** button - opens modal with training settings
- **📊 Load Data** button - runs replay simulation
