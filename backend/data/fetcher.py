"""
Data fetcher module.
Fetches OHLCV data from Binance with smart caching and gap detection.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import ccxt.async_support as ccxt
from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from backend.database.models import Symbol, OHLCVData, DataRange


class BinanceFetcher:
    """Fetches data from Binance Futures API."""
    
    # Timeframe to milliseconds mapping
    TIMEFRAME_MS = {
        "1m": 60 * 1000,
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
    }
    
    def __init__(self):
        self.exchange = ccxt.binanceusdm({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
    
    async def close(self):
        """Close exchange connection."""
        await self.exchange.close()
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> list[dict]:
        """
        Fetch OHLCV data from Binance.
        
        Args:
            symbol: Trading pair (e.g., 'SOLUSDT')
            timeframe: Candle timeframe (e.g., '1h')
            start_time: Start datetime
            end_time: End datetime
            limit: Max candles per request
            
        Returns:
            List of OHLCV dictionaries
        """
        all_candles = []
        current_start = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        tf_ms = self.TIMEFRAME_MS.get(timeframe, 60 * 60 * 1000)
        
        while current_start < end_ms:
            try:
                candles = await self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe,
                    since=current_start,
                    limit=limit
                )
                
                if not candles:
                    break
                
                for candle in candles:
                    if candle[0] <= end_ms:
                        all_candles.append({
                            'timestamp': datetime.utcfromtimestamp(candle[0] / 1000),
                            'open': candle[1],
                            'high': candle[2],
                            'low': candle[3],
                            'close': candle[4],
                            'volume': candle[5]
                        })
                
                # Move to next batch
                last_ts = candles[-1][0]
                current_start = last_ts + tf_ms
                
                # Rate limiting pause
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error fetching {symbol} {timeframe}: {e}")
                break
        
        logger.info(f"Fetched {len(all_candles)} candles for {symbol} {timeframe}")
        return all_candles


class DataService:
    """Service for managing OHLCV data with caching."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.fetcher = BinanceFetcher()
    
    async def close(self):
        """Cleanup resources."""
        await self.fetcher.close()
    
    async def get_or_create_symbol(self, name: str) -> Symbol:
        """Get existing symbol or create new one."""
        result = await self.db.execute(
            select(Symbol).where(Symbol.name == name)
        )
        symbol = result.scalar_one_or_none()
        
        if not symbol:
            symbol = Symbol(name=name, exchange="binance")
            self.db.add(symbol)
            await self.db.commit()
            await self.db.refresh(symbol)
            logger.info(f"Created new symbol: {name}")
        
        return symbol
    
    async def find_gaps(
        self,
        symbol_id: int,
        timeframe: str,
        start_time: datetime,
        end_time: datetime
    ) -> list[tuple[datetime, datetime]]:
        """
        Find missing data gaps in the requested time range.
        
        Returns:
            List of (gap_start, gap_end) tuples
        """
        result = await self.db.execute(
            select(DataRange)
            .where(
                and_(
                    DataRange.symbol_id == symbol_id,
                    DataRange.timeframe == timeframe,
                    DataRange.end_time >= start_time,
                    DataRange.start_time <= end_time
                )
            )
            .order_by(DataRange.start_time)
        )
        existing_ranges = result.scalars().all()
        
        if not existing_ranges:
            return [(start_time, end_time)]
        
        gaps = []
        current_start = start_time
        
        for dr in existing_ranges:
            if dr.start_time > current_start:
                gaps.append((current_start, dr.start_time))
            current_start = max(current_start, dr.end_time)
        
        if current_start < end_time:
            gaps.append((current_start, end_time))
        
        return gaps
    
    async def save_candles(
        self,
        symbol_id: int,
        timeframe: str,
        candles: list[dict]
    ):
        """Save candles to database with upsert."""
        if not candles:
            return
        
        # Prepare insert statement with ON CONFLICT DO NOTHING
        stmt = insert(OHLCVData).values([
            {
                'symbol_id': symbol_id,
                'timeframe': timeframe,
                **candle
            }
            for candle in candles
        ]).on_conflict_do_nothing(
            index_elements=['symbol_id', 'timeframe', 'timestamp']
        )
        
        await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"Saved {len(candles)} candles")
    
    async def update_data_range(
        self,
        symbol_id: int,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
        candle_count: int
    ):
        """Update data_ranges table after fetching."""
        data_range = DataRange(
            symbol_id=symbol_id,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            candle_count=candle_count
        )
        self.db.add(data_range)
        await self.db.commit()
    
    async def get_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime
    ) -> pd.DataFrame:
        """
        Get OHLCV data with automatic gap filling.
        
        1. Find gaps in existing data
        2. Fetch missing data from Binance
        3. Save to database
        4. Return full DataFrame
        """
        # Get or create symbol
        sym = await self.get_or_create_symbol(symbol)
        
        # Find gaps
        gaps = await self.find_gaps(sym.id, timeframe, start_time, end_time)
        
        # Fetch and save missing data
        for gap_start, gap_end in gaps:
            logger.info(f"Filling gap: {gap_start} to {gap_end}")
            candles = await self.fetcher.fetch_ohlcv(
                symbol, timeframe, gap_start, gap_end
            )
            if candles:
                await self.save_candles(sym.id, timeframe, candles)
                await self.update_data_range(
                    sym.id, timeframe, gap_start, gap_end, len(candles)
                )
        
        # Query all data in range
        result = await self.db.execute(
            select(OHLCVData)
            .where(
                and_(
                    OHLCVData.symbol_id == sym.id,
                    OHLCVData.timeframe == timeframe,
                    OHLCVData.timestamp >= start_time,
                    OHLCVData.timestamp <= end_time
                )
            )
            .order_by(OHLCVData.timestamp)
        )
        rows = result.scalars().all()
        
        if not rows:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'Open': float(r.open),
                'High': float(r.high),
                'Low': float(r.low),
                'Close': float(r.close),
                'Volume': float(r.volume)
            }
            for r in rows
        ], index=pd.DatetimeIndex([r.timestamp for r in rows]))
        
        return df
