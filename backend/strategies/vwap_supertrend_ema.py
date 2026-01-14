"""
VWAP + SuperTrend + EMA + Stoch RSI Strategy.
Converted from PineScript (TradingView).

Signal Types:
- Pullback Buy: Uptrend + touching support + bullish reversal + K < 20
- Pullback Sell: Downtrend + touching resistance + bearish reversal + K > 80
- Reversal Buy: SuperTrend flips bullish + price above all lines
- Reversal Sell: SuperTrend flips bearish + price below all lines
"""

import numpy as np
import pandas as pd
from backtesting.lib import crossover

from backend.strategies.base import BaseStrategy
from backend.strategies.indicators import (
    calculate_ema,
    calculate_supertrend,
    calculate_vwap_daily,
    calculate_stoch_rsi,
    rolling_lowest,
    rolling_highest
)


class VWAPSuperTrendEMA(BaseStrategy):
    """
    Combined Strategy: VWAP + SuperTrend + EMA + Stoch RSI
    
    This strategy combines multiple indicators to identify
    high-probability pullback and reversal entries.
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
    lookback = 4  # For finding recent candles
    
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
        
        # Rolling high/low for pullback detection
        self.lowest_recent = self.I(rolling_lowest, low, self.lookback)
        self.highest_recent = self.I(rolling_highest, high, self.lookback)
    
    def _is_uptrend_zone(self) -> bool:
        """Check if market is in uptrend zone (2 of 3 conditions met)."""
        score = 0
        
        # Condition 1: EMA1 > EMA2
        if self.ema1[-1] > self.ema2[-1]:
            score += 1
        
        # Condition 2: SuperTrend bullish (direction < 0)
        if self.st_dir[-1] < 0:
            score += 1
        
        # Condition 3: Both EMAs above VWAP
        if self.ema1[-1] > self.vwap[-1] and self.ema2[-1] > self.vwap[-1]:
            score += 1
        
        return score >= 2
    
    def _is_downtrend_zone(self) -> bool:
        """Check if market is in downtrend zone (2 of 3 conditions met)."""
        score = 0
        
        if self.ema1[-1] < self.ema2[-1]:
            score += 1
        
        if self.st_dir[-1] > 0:
            score += 1
        
        if self.ema1[-1] < self.vwap[-1] and self.ema2[-1] < self.vwap[-1]:
            score += 1
        
        return score >= 2
    
    def _is_touching_support(self) -> bool:
        """Check if recent low touched any support level."""
        lowest = self.lowest_recent[-1]
        return (
            lowest <= self.ema2[-1] or
            lowest <= self.vwap[-1] or
            lowest <= self.st_val[-1]
        )
    
    def _is_touching_resistance(self) -> bool:
        """Check if recent high touched any resistance level."""
        highest = self.highest_recent[-1]
        return (
            highest >= self.ema2[-1] or
            highest >= self.vwap[-1] or
            highest >= self.st_val[-1]
        )
    
    def _is_bullish_reversal_candle(self) -> bool:
        """Check for multi-candle bullish reversal pattern."""
        if len(self.data.Close) < 4:
            return False
        
        current_close = self.data.Close[-1]
        current_open = self.data.Open[-1]
        
        # Current candle must be green
        if current_close <= current_open:
            return False
        
        # Find recent red candle to beat
        open_to_beat = None
        for i in range(1, 4):
            if self.data.Close[-i-1] < self.data.Open[-i-1]:
                open_to_beat = self.data.Open[-i-1]
                break
        
        if open_to_beat is None:
            return False
        
        return current_close > open_to_beat
    
    def _is_bearish_reversal_candle(self) -> bool:
        """Check for multi-candle bearish reversal pattern."""
        if len(self.data.Close) < 4:
            return False
        
        current_close = self.data.Close[-1]
        current_open = self.data.Open[-1]
        
        # Current candle must be red
        if current_close >= current_open:
            return False
        
        # Find recent green candle to beat
        open_to_beat = None
        for i in range(1, 4):
            if self.data.Close[-i-1] > self.data.Open[-i-1]:
                open_to_beat = self.data.Open[-i-1]
                break
        
        if open_to_beat is None:
            return False
        
        return current_close < open_to_beat
    
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
        k_value = self.stoch_k[-1]
        
        # Skip if not enough data
        if len(self.data.Close) < self.lookback + 1:
            return
        
        # === PULLBACK SIGNALS ===
        
        # Pullback Buy
        if (
            self._is_uptrend_zone() and
            self._is_touching_support() and
            self._is_bullish_reversal_candle() and
            k_value < 20 and
            not self.position
        ):
            self.buy()
        
        # Pullback Sell
        elif (
            self._is_downtrend_zone() and
            self._is_touching_resistance() and
            self._is_bearish_reversal_candle() and
            k_value > 80 and
            not self.position
        ):
            self.sell()
        
        # === REVERSAL SIGNALS ===
        
        # Reversal Buy
        elif (
            self._supertrend_flipped_bullish() and
            price > self.ema1[-1] and
            price > self.ema2[-1] and
            price > self.vwap[-1] and
            not self.position
        ):
            self.buy()
        
        # Reversal Sell
        elif (
            self._supertrend_flipped_bearish() and
            price < self.ema1[-1] and
            price < self.ema2[-1] and
            price < self.vwap[-1] and
            not self.position
        ):
            self.sell()
        
        # === EXIT LOGIC ===
        # Close long if SuperTrend turns bearish
        elif self.position.is_long and self.st_dir[-1] > 0:
            self.position.close()
        
        # Close short if SuperTrend turns bullish
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
            {"name": "stoch_k", "type": "int", "default": 3, "min": 1, "max": 10},
            {"name": "stoch_d", "type": "int", "default": 3, "min": 1, "max": 10},
            {"name": "rsi_length", "type": "int", "default": 14, "min": 7, "max": 21},
            {"name": "stoch_length", "type": "int", "default": 14, "min": 7, "max": 21},
        ]
