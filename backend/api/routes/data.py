"""
Data API routes.
Endpoints for fetching and checking OHLCV data.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from loguru import logger

from backend.database.connection import get_db
from backend.database.models import Symbol, OHLCVData, DataRange
from backend.data.fetcher import DataService
from backend.api.schemas import FetchDataRequest, DataStatusResponse

router = APIRouter(prefix="/data", tags=["Data"])


@router.post("/fetch", response_model=dict)
async def fetch_data(
    request: FetchDataRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch OHLCV data from Binance and store in database.
    Automatically fills gaps in existing data.
    """
    try:
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")
    
    service = DataService(db)
    try:
        df = await service.get_data(
            request.symbol,
            request.timeframe,
            start_dt,
            end_dt
        )
        return {
            "status": "success",
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "candles_count": len(df),
            "start": df.index[0].isoformat() if len(df) > 0 else None,
            "end": df.index[-1].isoformat() if len(df) > 0 else None
        }
    finally:
        await service.close()


@router.get("/status", response_model=DataStatusResponse)
async def check_data_status(
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    db: AsyncSession = Depends(get_db)
):
    """Check data availability for a given range."""
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD")
    
    # Get symbol
    result = await db.execute(
        select(Symbol).where(Symbol.name == symbol)
    )
    sym = result.scalar_one_or_none()
    
    if not sym:
        return DataStatusResponse(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            total_candles=0,
            has_gaps=True,
            gaps=[{"start": start_date, "end": end_date}]
        )
    
    # Count candles
    count_result = await db.execute(
        select(func.count(OHLCVData.id))
        .where(
            and_(
                OHLCVData.symbol_id == sym.id,
                OHLCVData.timeframe == timeframe,
                OHLCVData.timestamp >= start_dt,
                OHLCVData.timestamp <= end_dt
            )
        )
    )
    total_candles = count_result.scalar() or 0
    
    # Find gaps
    service = DataService(db)
    gaps = await service.find_gaps(sym.id, timeframe, start_dt, end_dt)
    await service.close()
    
    return DataStatusResponse(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        total_candles=total_candles,
        has_gaps=len(gaps) > 0,
        gaps=[
            {"start": g[0].isoformat(), "end": g[1].isoformat()}
            for g in gaps
        ]
    )
