"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============ Data Schemas ============

class FetchDataRequest(BaseModel):
    """Request to fetch OHLCV data."""
    symbol: str = Field(..., example="SOLUSDT")
    timeframe: str = Field(..., example="1h")
    start_date: str = Field(..., example="2024-01-01")
    end_date: str = Field(..., example="2024-06-30")


class DataStatusResponse(BaseModel):
    """Response for data availability check."""
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    total_candles: int
    has_gaps: bool
    gaps: list[dict] = []


# ============ Backtest Schemas ============

class BacktestRequest(BaseModel):
    """Request to run a backtest."""
    symbol: str = Field(..., example="SOLUSDT")
    timeframe: str = Field(..., example="1h")
    start_date: str = Field(..., example="2024-01-01")
    end_date: str = Field(..., example="2024-06-30")
    strategy: str = Field(..., example="vwap_supertrend_ema")
    params: Optional[dict] = Field(default={}, example={
        "ema1_length": 21,
        "ema2_length": 50,
        "st_length": 12,
        "st_multiplier": 3.0
    })


class BacktestMetrics(BaseModel):
    """Backtest performance metrics."""
    return_pct: float
    buy_hold_return_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    total_trades: int
    avg_trade_pct: float
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None


class TradeRecord(BaseModel):
    """Single trade record."""
    entry_time: str
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    signal_type: Optional[str] = None


class BacktestResponse(BaseModel):
    """Full backtest result response."""
    id: str
    symbol: str
    timeframe: str
    strategy: str
    start_date: str
    end_date: str
    params: dict
    metrics: BacktestMetrics
    equity_curve: list[dict]  # [{timestamp, equity}, ...]
    trades: list[TradeRecord]


# ============ Strategy Schemas ============

class StrategyInfo(BaseModel):
    """Strategy metadata."""
    name: str
    display_name: str
    description: str
    parameters: list[dict]  # [{name, type, default, min, max}, ...]


class SymbolInfo(BaseModel):
    """Symbol metadata."""
    name: str
    exchange: str
    is_active: bool
