"""
Technical indicators module.
Custom indicator calculations using pandas-ta and numpy.
"""

import numpy as np
import pandas as pd
import pandas_ta as ta


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
        # pandas-ta returns SUPERT_length_multiplier and SUPERTd_length_multiplier
        st_col = [c for c in result.columns if c.startswith('SUPERT_')][0]
        dir_col = [c for c in result.columns if c.startswith('SUPERTd_')][0]
        return result[st_col], result[dir_col]
    return pd.Series(index=close.index), pd.Series(index=close.index)


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
        (k_line, d_line)
    """
    result = ta.stochrsi(
        close,
        length=rsi_length,
        rsi_length=rsi_length,
        k=smooth_k,
        d=smooth_d
    )
    if result is not None and len(result.columns) >= 2:
        k_col = [c for c in result.columns if 'K' in c][0]
        d_col = [c for c in result.columns if 'D' in c][0]
        return result[k_col], result[d_col]
    return pd.Series(index=close.index), pd.Series(index=close.index)


def rolling_lowest(series: pd.Series, period: int) -> pd.Series:
    """Calculate rolling lowest value."""
    return series.rolling(window=period).min()


def rolling_highest(series: pd.Series, period: int) -> pd.Series:
    """Calculate rolling highest value."""
    return series.rolling(window=period).max()
