"""
Database models module.
Defines all SQLAlchemy ORM models.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Boolean, DateTime, Numeric, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.connection import Base


class Symbol(Base):
    """Tradeable symbol (e.g., SOLUSDT)."""
    
    __tablename__ = "symbols"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(20), default="binance")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    ohlcv_data: Mapped[list["OHLCVData"]] = relationship(back_populates="symbol")
    data_ranges: Mapped[list["DataRange"]] = relationship(back_populates="symbol")
    backtest_runs: Mapped[list["BacktestRun"]] = relationship(back_populates="symbol")


class OHLCVData(Base):
    """OHLCV candlestick data."""
    
    __tablename__ = "ohlcv_data"
    __table_args__ = (
        UniqueConstraint("symbol_id", "timeframe", "timestamp", name="uq_ohlcv_symbol_tf_ts"),
        Index("ix_ohlcv_symbol_tf_ts", "symbol_id", "timeframe", "timestamp"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id"), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    
    # Relationships
    symbol: Mapped["Symbol"] = relationship(back_populates="ohlcv_data")


class DataRange(Base):
    """Tracks fetched data ranges for gap detection."""
    
    __tablename__ = "data_ranges"
    __table_args__ = (
        Index("ix_data_ranges_symbol_tf", "symbol_id", "timeframe"),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id"), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    candle_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    symbol: Mapped["Symbol"] = relationship(back_populates="data_ranges")


class BacktestRun(Base):
    """History of backtest executions."""
    
    __tablename__ = "backtest_runs"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol_id: Mapped[int] = mapped_column(Integer, ForeignKey("symbols.id"), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    equity_curve: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    symbol: Mapped["Symbol"] = relationship(back_populates="backtest_runs")
    trades: Mapped[list["BacktestTrade"]] = relationship(back_populates="backtest_run")


class BacktestTrade(Base):
    """Individual trades from backtests."""
    
    __tablename__ = "backtest_trades"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    backtest_run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("backtest_runs.id"), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # 'long' or 'short'
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    pnl_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    signal_type: Mapped[Optional[str]] = mapped_column(String(50))  # 'pullback_buy', 'reversal_sell', etc.
    
    # Relationships
    backtest_run: Mapped["BacktestRun"] = relationship(back_populates="trades")
