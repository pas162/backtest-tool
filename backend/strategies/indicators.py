"""
Technical indicators module.
Custom indicator calculations using pandas-ta and numpy.
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
from loguru import logger


def calculate_ema(series: pd.Series, length: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return ta.ema(series, length=length)


def calculate_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 12,
    multiplier: float = 3.0
) -> tuple[pd.Series, pd.Series]:
    """
    Calculate SuperTrend indicator.
    
    Returns:
        (supertrend_value, supertrend_direction)
        direction: -1 = bullish (price above), 1 = bearish (price below)
    """
    result = ta.supertrend(high, low, close, length=length, multiplier=multiplier)
    if result is not None and len(result.columns) >= 2:
        # pandas-ta returns columns with variable naming
        st_cols = [c for c in result.columns if 'SUPERT_' in c and 'd_' not in c.lower()]
        dir_cols = [c for c in result.columns if 'SUPERTd_' in c or 'd_' in c.lower()]
        
        if st_cols and dir_cols:
            return result[st_cols[0]], result[dir_cols[0]]
        else:
            # Fallback: use first two columns
            return result.iloc[:, 0], result.iloc[:, 1]
    
    return pd.Series(index=close.index, dtype=float), pd.Series(index=close.index, dtype=float)


def calculate_vwap_daily(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    timestamps: pd.DatetimeIndex
) -> pd.Series:
    """
    Calculate Daily VWAP (resets at UTC 00:00).
    """
    df = pd.DataFrame({
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=timestamps)
    
    # Typical price
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['tp_vol'] = df['tp'] * df['volume']
    
    # Group by date
    df['date'] = df.index.date
    
    # Cumulative sums within each day
    df['cum_tp_vol'] = df.groupby('date')['tp_vol'].cumsum()
    df['cum_vol'] = df.groupby('date')['volume'].cumsum()
    
    # VWAP
    df['vwap'] = df['cum_tp_vol'] / df['cum_vol']
    
    return df['vwap']


def calculate_stoch_rsi(
    close: pd.Series,
    rsi_length: int = 14,
    stoch_length: int = 14,
    smooth_k: int = 3,
    smooth_d: int = 3
) -> tuple[pd.Series, pd.Series]:
    """
    Calculate Stochastic RSI.
    
    Returns:
        (k_line, d_line) - values from 0 to 100
    """
    try:
        result = ta.stochrsi(
            close,
            length=rsi_length,
            rsi_length=rsi_length,
            k=smooth_k,
            d=smooth_d
        )
        
        if result is not None and not result.empty:
            logger.debug(f"StochRSI columns: {list(result.columns)}")
            
            # Try to find K and D columns with various naming patterns
            k_col = None
            d_col = None
            
            for col in result.columns:
                col_upper = col.upper()
                if k_col is None and ('_K_' in col_upper or col_upper.endswith('_K') or 'STOCHRSIk' in col):
                    k_col = col
                if d_col is None and ('_D_' in col_upper or col_upper.endswith('_D') or 'STOCHRSId' in col):
                    d_col = col
            
            # Fallback: use column indices if naming doesn't match
            if k_col is None and len(result.columns) >= 1:
                k_col = result.columns[0]
            if d_col is None and len(result.columns) >= 2:
                d_col = result.columns[1]
            
            if k_col and d_col:
                # Scale to 0-100 if needed (pandas-ta may return 0-1)
                k_series = result[k_col]
                d_series = result[d_col]
                
                # Check if values are 0-1 range and scale to 0-100
                if k_series.max() <= 1.0:
                    k_series = k_series * 100
                    d_series = d_series * 100
                
                return k_series, d_series
    except Exception as e:
        logger.error(f"StochRSI calculation error: {e}")
    
    # Return empty series on failure
    return pd.Series(index=close.index, dtype=float), pd.Series(index=close.index, dtype=float)


def rolling_lowest(series: pd.Series, period: int) -> pd.Series:
    """Calculate rolling lowest value."""
    return series.rolling(window=period).min()


def rolling_highest(series: pd.Series, period: int) -> pd.Series:
    """Calculate rolling highest value."""
    return series.rolling(window=period).max()
