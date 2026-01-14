"""
Backtest API routes.
Endpoints for running and retrieving backtests.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from backend.database.connection import get_db
from backend.database.models import Symbol, BacktestRun, BacktestTrade
from backend.data.fetcher import DataService
from backend.engine.backtester import BacktestEngine
from backend.strategies import get_strategy_class, get_all_strategies
from backend.api.schemas import (
    BacktestRequest, BacktestResponse, BacktestMetrics,
    TradeRecord, StrategyInfo
)

router = APIRouter(prefix="/backtest", tags=["Backtest"])


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db)
):
    """Run a backtest with specified parameters."""
    try:
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")
    
    # Get strategy class
    strategy_class = get_strategy_class(request.strategy)
    if not strategy_class:
        raise HTTPException(400, f"Unknown strategy: {request.strategy}")
    
    # Get data
    data_service = DataService(db)
    try:
        df = await data_service.get_data(
            request.symbol,
            request.timeframe,
            start_dt,
            end_dt
        )
    finally:
        await data_service.close()
    
    if df.empty:
        raise HTTPException(400, "No data available for the specified range")
    
    # Run backtest
    engine = BacktestEngine()
    result = engine.run(
        strategy_class=strategy_class,
        data=df,
        **request.params
    )
    
    # Get symbol for DB
    sym_result = await db.execute(
        select(Symbol).where(Symbol.name == request.symbol)
    )
    sym = sym_result.scalar_one()
    
    # Save to database
    backtest_run = BacktestRun(
        strategy_name=request.strategy,
        symbol_id=sym.id,
        timeframe=request.timeframe,
        start_time=start_dt,
        end_time=end_dt,
        params=request.params,
        metrics=result['metrics'],
        equity_curve=result['equity_curve']
    )
    db.add(backtest_run)
    await db.commit()
    await db.refresh(backtest_run)
    
    # Save trades
    for trade in result['trades']:
        bt_trade = BacktestTrade(
            backtest_run_id=backtest_run.id,
            entry_time=trade['entry_time'],
            exit_time=trade['exit_time'],
            side=trade['side'],
            entry_price=trade['entry_price'],
            exit_price=trade['exit_price'],
            size=trade['size'],
            pnl=trade['pnl'],
            pnl_pct=trade['pnl_pct'],
            signal_type=trade.get('signal_type')
        )
        db.add(bt_trade)
    await db.commit()
    
    return BacktestResponse(
        id=backtest_run.id,
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy=request.strategy,
        start_date=request.start_date,
        end_date=request.end_date,
        params=request.params,
        metrics=BacktestMetrics(**result['metrics']),
        equity_curve=result['equity_curve'],
        trades=[TradeRecord(**t) for t in result['trades']]
    )


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest(
    backtest_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get backtest results by ID."""
    result = await db.execute(
        select(BacktestRun).where(BacktestRun.id == backtest_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(404, "Backtest not found")
    
    # Get trades
    trades_result = await db.execute(
        select(BacktestTrade).where(BacktestTrade.backtest_run_id == backtest_id)
    )
    trades = trades_result.scalars().all()
    
    # Get symbol name
    sym_result = await db.execute(
        select(Symbol).where(Symbol.id == run.symbol_id)
    )
    sym = sym_result.scalar_one()
    
    return BacktestResponse(
        id=run.id,
        symbol=sym.name,
        timeframe=run.timeframe,
        strategy=run.strategy_name,
        start_date=run.start_time.strftime("%Y-%m-%d"),
        end_date=run.end_time.strftime("%Y-%m-%d"),
        params=run.params or {},
        metrics=BacktestMetrics(**run.metrics),
        equity_curve=run.equity_curve or [],
        trades=[
            TradeRecord(
                entry_time=t.entry_time.isoformat(),
                exit_time=t.exit_time.isoformat(),
                side=t.side,
                entry_price=float(t.entry_price),
                exit_price=float(t.exit_price),
                size=float(t.size),
                pnl=float(t.pnl),
                pnl_pct=float(t.pnl_pct),
                signal_type=t.signal_type
            )
            for t in trades
        ]
    )


@router.get("/strategies/list", response_model=list[StrategyInfo])
async def list_strategies():
    """List all available strategies."""
    return get_all_strategies()
