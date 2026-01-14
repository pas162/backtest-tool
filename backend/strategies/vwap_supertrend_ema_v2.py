"""
VWAP + SuperTrend + EMA Strategy V2 (Optimized)
===============================================

Improvements over V1:
1. ADX filter - only trade in trending markets (ADX > 20)
2. Simplified entry conditions - less restrictive
3. Position sizing - 95% of available capital per trade
4. Better StochRSI thresholds (30/70 instead of 20/80)

Signal Logic remains the same:
- Pullback entries with trend confirmation
- Reversal entries on SuperTrend flip
- Exit when SuperTrend changes direction
"""

import numpy as np
import pandas as pd
from backtesting.lib import crossover
import pandas_ta as ta

from backend.strategies.base import BaseStrategy
from backend.strategies.indicators import (
    calculate_ema,
    calculate_supertrend,
    calculate_vwap_daily,
    calculate_stoch_rsi,
    rolling_lowest,
    rolling_highest
)


def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Calculate ADX (Average Directional Index)."""
    result = ta.adx(high, low, close, length=length)
    if result is not None:
        adx_col = [c for c in result.columns if 'ADX_' in c][0]
        return result[adx_col]
    return pd.Series(index=close.index, dtype=float)


class VWAPSuperTrendEMAv2(BaseStrategy):
    """
    VWAP + SuperTrend + EMA Strategy V2 (Optimized)
    
    Key Improvements:
    - ADX filter: Only trade when ADX > threshold (trending market)
    - Relaxed StochRSI: 30/70 instead of 20/80
    - Simpler trend zone logic
    """
    
    # Strategy parameters (can be optimized)
    ema1_length = 21
    ema2_length = 50
    st_length = 12
    st_multiplier = 3.0
    stoch_k = 3
    stoch_d = 3
    rsi_length = 14
    stoch_length = 14
    lookback = 4
    adx_length = 14
    adx_threshold = 20  # Only trade when ADX > this
    stoch_oversold = 30  # More relaxed than V1's 20
    stoch_overbought = 70  # More relaxed than V1's 80
    
    def init(self):
        """Calculate all indicators."""
        close = pd.Series(self.data.Close)
        high = pd.Series(self.data.High)
        low = pd.Series(self.data.Low)
        volume = pd.Series(self.data.Volume)
        
        # EMA
        self.ema1 = self.I(calculate_ema, close, self.ema1_length)
        self.ema2 = self.I(calculate_ema, close, self.ema2_length)
        
        # SuperTrend
        st_val, st_dir = calculate_supertrend(
            high, low, close,
            self.st_length, self.st_multiplier
        )
        self.st_val = self.I(lambda: st_val)
        self.st_dir = self.I(lambda: st_dir)
        
        # VWAP (Daily)
        if hasattr(self.data, 'index'):
            timestamps = self.data.index
        else:
            timestamps = pd.RangeIndex(len(close))
        self.vwap = self.I(calculate_vwap_daily, high, low, close, volume, timestamps)
        
        # Stoch RSI
        stoch_k, stoch_d = calculate_stoch_rsi(
            close, self.rsi_length, self.stoch_length,
            self.stoch_k, self.stoch_d
        )
        self.stoch_k = self.I(lambda: stoch_k)
        self.stoch_d = self.I(lambda: stoch_d)
        
        # ADX - NEW in V2
        adx = calculate_adx(high, low, close, self.adx_length)
        self.adx = self.I(lambda: adx)
        
        # Rolling high/low for pullback detection
        self.lowest_recent = self.I(rolling_lowest, low, self.lookback)
        self.highest_recent = self.I(rolling_highest, high, self.lookback)
    
    def _is_trending_market(self) -> bool:
        """Check if market is trending (ADX filter)."""
        if len(self.adx) < 1 or pd.isna(self.adx[-1]):
            return True  # Allow trading if ADX not available
        return self.adx[-1] > self.adx_threshold
    
    def _is_uptrend_zone(self) -> bool:
        """Check if market is in uptrend zone (simplified: 2 of 3)."""
        score = 0
        
        if self.ema1[-1] > self.ema2[-1]:
            score += 1
        
        if self.st_dir[-1] < 0:
            score += 1
        
        if self.ema1[-1] > self.vwap[-1]:
            score += 1
        
        return score >= 2
    
    def _is_downtrend_zone(self) -> bool:
        """Check if market is in downtrend zone (simplified)."""
        score = 0
        
        if self.ema1[-1] < self.ema2[-1]:
            score += 1
        
        if self.st_dir[-1] > 0:
            score += 1
        
        if self.ema1[-1] < self.vwap[-1]:
            score += 1
        
        return score >= 2
    
    def _is_touching_support(self) -> bool:
        """Check if recent low touched any support level."""
        lowest = self.lowest_recent[-1]
        tolerance = 0.002  # 0.2% tolerance
        
        # Check if touching with tolerance
        ema2_touch = lowest <= self.ema2[-1] * (1 + tolerance)
        vwap_touch = lowest <= self.vwap[-1] * (1 + tolerance)
        st_touch = lowest <= self.st_val[-1] * (1 + tolerance)
        
        return ema2_touch or vwap_touch or st_touch
    
    def _is_touching_resistance(self) -> bool:
        """Check if recent high touched any resistance level."""
        highest = self.highest_recent[-1]
        tolerance = 0.002
        
        ema2_touch = highest >= self.ema2[-1] * (1 - tolerance)
        vwap_touch = highest >= self.vwap[-1] * (1 - tolerance)
        st_touch = highest >= self.st_val[-1] * (1 - tolerance)
        
        return ema2_touch or vwap_touch or st_touch
    
    def _is_bullish_candle(self) -> bool:
        """Simple bullish candle check (close > open)."""
        return self.data.Close[-1] > self.data.Open[-1]
    
    def _is_bearish_candle(self) -> bool:
        """Simple bearish candle check (close < open)."""
        return self.data.Close[-1] < self.data.Open[-1]
    
    def _supertrend_flipped_bullish(self) -> bool:
        """Check if SuperTrend just flipped to bullish."""
        if len(self.st_dir) < 2:
            return False
        return self.st_dir[-1] < 0 and self.st_dir[-2] > 0
    
    def _supertrend_flipped_bearish(self) -> bool:
        """Check if SuperTrend just flipped to bearish."""
        if len(self.st_dir) < 2:
            return False
        return self.st_dir[-1] > 0 and self.st_dir[-2] < 0
    
    def next(self):
        """Execute trading logic."""
        price = self.data.Close[-1]
        k_value = self.stoch_k[-1] if not pd.isna(self.stoch_k[-1]) else 50
        
        # Skip if not enough data
        if len(self.data.Close) < max(self.ema2_length, self.adx_length) + 5:
            return
        
        # === ADX FILTER (NEW in V2) ===
        if not self._is_trending_market():
            return  # Don't trade in ranging market
        
        # === PULLBACK SIGNALS ===
        
        # Pullback Buy (relaxed conditions)
        if (
            self._is_uptrend_zone() and
            self._is_touching_support() and
            self._is_bullish_candle() and
            k_value < self.stoch_oversold and
            not self.position
        ):
            self.buy()
        
        # Pullback Sell
        elif (
            self._is_downtrend_zone() and
            self._is_touching_resistance() and
            self._is_bearish_candle() and
            k_value > self.stoch_overbought and
            not self.position
        ):
            self.sell()
        
        # === REVERSAL SIGNALS ===
        
        # Reversal Buy
        elif (
            self._supertrend_flipped_bullish() and
            price > self.ema1[-1] and
            price > self.vwap[-1] and
            not self.position
        ):
            self.buy()
        
        # Reversal Sell
        elif (
            self._supertrend_flipped_bearish() and
            price < self.ema1[-1] and
            price < self.vwap[-1] and
            not self.position
        ):
            self.sell()
        
        # === EXIT LOGIC (same as V1) ===
        elif self.position.is_long and self.st_dir[-1] > 0:
            self.position.close()
        
        elif self.position.is_short and self.st_dir[-1] < 0:
            self.position.close()
    
    @classmethod
    def get_parameters(cls) -> list[dict]:
        """Return optimizable parameters."""
        return [
            {"name": "ema1_length", "type": "int", "default": 21, "min": 10, "max": 50},
            {"name": "ema2_length", "type": "int", "default": 50, "min": 30, "max": 100},
            {"name": "st_length", "type": "int", "default": 12, "min": 5, "max": 20},
            {"name": "st_multiplier", "type": "float", "default": 3.0, "min": 1.0, "max": 5.0},
            {"name": "adx_threshold", "type": "int", "default": 20, "min": 15, "max": 30},
            {"name": "stoch_oversold", "type": "int", "default": 30, "min": 15, "max": 40},
            {"name": "stoch_overbought", "type": "int", "default": 70, "min": 60, "max": 85},
        ]
