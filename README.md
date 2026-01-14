# Multi-Strategy Backtesting Platform

Nền tảng backtesting crypto trading strategies với khả năng chạy nhiều chiến lược song song.

## 🎯 Mục tiêu

- Backtest các chiến lược trading trên dữ liệu Binance Futures
- Hỗ trợ chạy nhiều strategies cùng lúc
- Lưu dữ liệu vào PostgreSQL để tái sử dụng
- Dashboard đơn giản để visualize kết quả

## 🚀 Quick Start

```bash
# Clone repo
git clone https://github.com/pas162/backtest-tool.git
cd backtest-tool

# Start với Docker
docker compose up -d

# Mở dashboard
open http://localhost:8000
```

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

- [Requirements Table](docs/REQUIREMENTS.md) - Source of truth cho tất cả features
- [Implementation Plan](docs/IMPLEMENTATION.md) - Chi tiết kỹ thuật
- [Progress Tracking](docs/TRACKING.md) - Task checklist

## 🔧 Tech Stack

- **Backend**: Python 3.11, FastAPI, backtesting.py
- **Database**: PostgreSQL 16, Redis
- **Frontend**: HTML, Vanilla JS, Plotly.js
- **Infrastructure**: Docker, Docker Compose

## 📄 License

MIT
