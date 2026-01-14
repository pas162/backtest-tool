# Multi-Strategy Backtesting Platform

A high-performance backtesting platform for crypto trading strategies with support for running multiple strategies in parallel.

## 🎯 Features

- Backtest trading strategies on Binance Futures data
- Run multiple strategies simultaneously
- Store data in PostgreSQL for reuse
- Simple dashboard for visualizing results
- Automatic data gap detection and filling

## 🚀 Quick Start

### Prerequisites
- **Docker Desktop** must be installed and running
- Git

### Installation

```bash
# Clone repo
git clone https://github.com/pas162/backtest-tool.git
cd backtest-tool

# Start with Docker (make sure Docker Desktop is running!)
docker compose up -d

# Open dashboard
# http://localhost:8000
```

### Troubleshooting

If you see this error:
```
unable to get image 'postgres:16-alpine': open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

**Solution**: Open Docker Desktop from Start Menu and wait until it shows "Docker is running", then retry `docker compose up`.

## 📁 Project Structure

```
backtest-tool/
├── docs/
│   ├── REQUIREMENTS.md      # Requirements table (source of truth)
│   ├── IMPLEMENTATION.md    # Implementation plan
│   └── TRACKING.md          # Progress tracking
├── backend/
│   ├── database/            # PostgreSQL models & migrations
│   ├── data/                # Data fetcher from Binance
│   ├── strategies/          # Trading strategies
│   ├── engine/              # Backtesting engine
│   └── api/                 # FastAPI endpoints
├── frontend/                # HTML + JS dashboard
├── docker-compose.yml
└── Dockerfile
```

## 📖 Documentation

- [Requirements Table](docs/REQUIREMENTS.md) - Source of truth for all features
- [Implementation Plan](docs/IMPLEMENTATION.md) - Technical details
- [Progress Tracking](docs/TRACKING.md) - Task checklist

## 🔧 Tech Stack

- **Backend**: Python 3.11, FastAPI, backtesting.py
- **Database**: PostgreSQL 16, Redis
- **Frontend**: HTML, Vanilla JS, Plotly.js
- **Infrastructure**: Docker, Docker Compose

## 📊 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/symbols` | List available symbols |
| POST | `/api/data/fetch` | Fetch data from Binance |
| GET | `/api/data/status` | Check data availability |
| POST | `/api/backtest/run` | Run a backtest |
| GET | `/api/backtest/{id}` | Get backtest results |

## 🎮 Usage

1. Open http://localhost:8000
2. Select a symbol (e.g., SOLUSDT)
3. Choose timeframe and date range
4. Click "Fetch Data" to download from Binance
5. Click "Run Backtest" to execute strategy
6. View results: equity curve, metrics, trade history

## 📄 License

MIT
