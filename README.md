# AI Trading Replay 🚀

A real-time AI-powered trading replay simulator for Binance Futures. Watch machine learning models execute trades on historical data with adjustable leverage.

## Features

- **ML Trading Agent**: XGBoost model predicts UP/DOWN trends
- **Futures Trading**: Long & Short positions with 1x-100x leverage
- **Real-time Animation**: Step-by-step candle replay with trade markers
- **TradingView-style UI**: Professional candlestick charts using Lightweight Charts

## Quick Start

```bash
# Start with Docker
docker compose up

# Open browser
http://localhost:8000
```

## Usage

1. Select **Symbol** (XRPUSDT, BTCUSDT, etc.)
2. Set **Date Range**
3. Choose **Leverage** (default 20x)
4. Click **Load Data**
5. Press **Play** and watch the AI trade!

## Tech Stack

- **Backend**: FastAPI, Python, XGBoost
- **Frontend**: Vanilla JS, Lightweight Charts
- **Database**: PostgreSQL, Redis
- **Container**: Docker Compose

## Project Structure

```
backtest-tool/
├── backend/
│   ├── api/          # FastAPI routes
│   ├── ml/           # ML model & features
│   ├── replay/       # Replay engine
│   └── strategies/   # Trading strategies
├── frontend/
│   └── index.html    # Main UI
├── models/           # Trained ML models
└── docker-compose.yml
```

## Training the ML Model

```bash
# Via API
curl -X POST http://localhost:8000/api/replay/train \
  -H "Content-Type: application/json" \
  -d '{"symbol": "XRPUSDT", "days": 90}'
```

## License

MIT
