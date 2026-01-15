"""
Backtest API routes.
Endpoints for running and retrieving backtests.
"""

import traceback
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
    logger.info(f"=== BACKTEST START ===")
    logger.info(f"Request: {request.symbol} {request.timeframe} {request.start_date} to {request.end_date}")
    logger.info(f"Strategy: {request.strategy}, Params: {request.params}")
    
    try:
        # Parse dates
        try:
            start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
            logger.info(f"Dates parsed: {start_dt} to {end_dt}")
        except ValueError as e:
            logger.error(f"Date parsing error: {e}")
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")
        
        # Get strategy class
        strategy_class = get_strategy_class(request.strategy)
        if not strategy_class:
            logger.error(f"Unknown strategy: {request.strategy}")
            raise HTTPException(400, f"Unknown strategy: {request.strategy}")
        logger.info(f"Strategy class loaded: {strategy_class.__name__}")
        
        # Get data
        logger.info("Fetching data...")
        data_service = DataService(db)
        try:
            df = await data_service.get_data(
                request.symbol,
                request.timeframe,
                start_dt,
                end_dt
            )
            logger.info(f"Data fetched: {len(df)} rows")
        except Exception as e:
            logger.error(f"Data fetch error: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(500, f"Failed to fetch data: {str(e)}")
        finally:
            await data_service.close()
        
        if df.empty:
            logger.warning("No data available")
            raise HTTPException(400, "No data available for the specified range")
        
        # Run backtest
        logger.info("Running backtest...")
        try:
            engine = BacktestEngine(
                cash=request.initial_capital,
                commission=request.commission,
                leverage=request.leverage,
                position_size=request.position_size
            )
            
            # Calculate position size as percentage of capital
            # position_size / initial_capital = fraction of capital per trade
            position_size_pct = (request.position_size / request.initial_capital) * 100
            
            # Add position sizing to strategy params (only for V2)
            strategy_params = dict(request.params)
            if request.strategy == 'vwap_supertrend_ema_v2':
                strategy_params['position_size_pct'] = position_size_pct
            
            result = engine.run(
                strategy_class=strategy_class,
                data=df,
                **strategy_params
            )
            logger.info(f"Backtest complete: {result['metrics']}")
            
            # === TRADE ANALYSIS LOG ===
            trades = result['trades']
            if trades:
                winning_trades = [t for t in trades if t['pnl'] > 0]
                losing_trades = [t for t in trades if t['pnl'] < 0]
                long_trades = [t for t in trades if t['side'] == 'long']
                short_trades = [t for t in trades if t['side'] == 'short']
                
                avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
                avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
                
                long_pnl = sum(t['pnl'] for t in long_trades)
                short_pnl = sum(t['pnl'] for t in short_trades)
                long_wins = len([t for t in long_trades if t['pnl'] > 0])
                short_wins = len([t for t in short_trades if t['pnl'] > 0])
                
                logger.info("=" * 50)
                logger.info("📊 TRADE ANALYSIS")
                logger.info("=" * 50)
                logger.info(f"Total Trades: {len(trades)} | Wins: {len(winning_trades)} | Losses: {len(losing_trades)}")
                logger.info(f"Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}")
                logger.info(f"LONG trades: {len(long_trades)} (wins: {long_wins}) | PnL: ${long_pnl:.2f}")
                logger.info(f"SHORT trades: {len(short_trades)} (wins: {short_wins}) | PnL: ${short_pnl:.2f}")
                
                # Show worst 3 trades
                sorted_by_pnl = sorted(trades, key=lambda x: x['pnl'])
                logger.info("--- WORST 3 TRADES ---")
                for t in sorted_by_pnl[:3]:
                    logger.info(f"  {t['side'].upper()} | Entry: ${t['entry_price']:.2f} -> Exit: ${t['exit_price']:.2f} | PnL: ${t['pnl']:.2f}")
                
                # Show best 3 trades
                logger.info("--- BEST 3 TRADES ---")
                for t in sorted_by_pnl[-3:]:
                    logger.info(f"  {t['side'].upper()} | Entry: ${t['entry_price']:.2f} -> Exit: ${t['exit_price']:.2f} | PnL: ${t['pnl']:.2f}")
                logger.info("=" * 50)
                
        except Exception as e:
            logger.error(f"Backtest engine error: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(500, f"Backtest failed: {str(e)}")
        
        # Get symbol for DB
        logger.info("Saving to database...")
        try:
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
            logger.info(f"Backtest run saved: {backtest_run.id}")
            
            # Save trades
            for trade in result['trades']:
                # Parse timestamps - they may be ISO strings or datetime objects
                entry_time = trade['entry_time']
                exit_time = trade['exit_time']
                
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                if isinstance(exit_time, str):
                    exit_time = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                
                bt_trade = BacktestTrade(
                    backtest_run_id=backtest_run.id,
                    entry_time=entry_time,
                    exit_time=exit_time,
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
            logger.info(f"Saved {len(result['trades'])} trades")
        except Exception as e:
            logger.error(f"Database save error: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(500, f"Failed to save results: {str(e)}")
        
        logger.info("=== BACKTEST SUCCESS ===")
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"=== UNEXPECTED ERROR ===")
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(500, f"Unexpected error: {str(e)}")


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
