"""
FastAPI main application server.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
import sys

from backend.config import settings
from backend.database.connection import init_db, close_db
from backend.api.routes import data_router, backtest_router, replay_router


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Backtest Platform...")
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="Backtest Platform",
    description="Multi-Strategy Backtesting Platform for Crypto Trading",
    version="1.0.0",
    lifespan=lifespan
)

# Include API routers
app.include_router(data_router, prefix=settings.api_prefix)
app.include_router(backtest_router, prefix=settings.api_prefix)
app.include_router(replay_router, prefix=settings.api_prefix)

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def root():
    """Serve the AI Trading Replay dashboard."""
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get(f"{settings.api_prefix}/symbols")
async def list_symbols():
    """List available symbols."""
    # For now, return hardcoded list. Can be expanded later.
    return [
        {"name": "SOLUSDT", "exchange": "binance", "is_active": True},
        {"name": "BTCUSDT", "exchange": "binance", "is_active": True},
        {"name": "ETHUSDT", "exchange": "binance", "is_active": True},
    ]
