"""
Feature Engineering for ML Trading Agent.

Volume & Auction Market Theory based features.
Focus on: Volume analysis, Price action, Market structure
"""

import pandas as pd
import numpy as np
from typing import Optional


class FeatureEngineer:
    """
    Generates features from OHLCV data for ML model.
    
    Based on Volume & Auction Market Theory:
    - Volume Delta (buyer vs seller aggression)
    - Price Action (candle structure, wicks = rejection)
    - Market Structure (value area, support/resistance)
    - Volume-Price Relationship (confirmation/divergence)
    """
    
    def __init__(self):
        self.feature_names = []
    
    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create Volume & Auction based features from OHLCV data.
        
        Args:
            data: DataFrame with OHLCV columns
        
        Returns:
            DataFrame with feature columns
        """
        df = data.copy()
        
        # Ensure column names are correct
        df.columns = [c.capitalize() for c in df.columns]
        
        close = df['Close']
        high = df['High']
        low = df['Low']
        open_ = df['Open']
        volume = df['Volume']
        
        # === VOLUME ANALYSIS ===
        
        # Volume relative to average (activity level)
        df['volume_sma_20'] = volume.rolling(20).mean()
        df['volume_ratio'] = volume / df['volume_sma_20'].replace(0, 1)
        
        # Volume trend (is volume increasing or decreasing)
        df['volume_sma_5'] = volume.rolling(5).mean()
        df['volume_trend'] = df['volume_sma_5'] / df['volume_sma_20'].replace(0, 1)
        
        # Volume Delta approximation (buyer vs seller)
        # Based on candle close position within range
        candle_range = (high - low).replace(0, np.nan)
        close_position = (close - low) / candle_range  # 0 = closed at low, 1 = closed at high
        
        # Delta = Volume * (2 * close_position - 1)
        # If close at high: delta = +volume (buyers won)
        # If close at low: delta = -volume (sellers won)
        df['volume_delta'] = volume * (2 * close_position - 1)
        
        # Cumulative Volume Delta (who's in control over time)
        df['cvd_5'] = df['volume_delta'].rolling(5).sum()
        df['cvd_10'] = df['volume_delta'].rolling(10).sum()
        df['cvd_20'] = df['volume_delta'].rolling(20).sum()
        
        # Normalized CVD (for comparison across different volume levels)
        df['cvd_normalized'] = df['cvd_10'] / (df['volume_sma_20'] * 10).replace(0, 1)
        
        # CVD momentum (is buying/selling pressure increasing)
        df['cvd_momentum'] = df['cvd_5'] - df['cvd_5'].shift(5)
        df['cvd_momentum_norm'] = df['cvd_momentum'] / df['volume_sma_20'].replace(0, 1)
        
        # === PRICE ACTION (Candle Analysis) ===
        
        # Body ratio (conviction - large body = strong conviction)
        candle_body = abs(close - open_)
        df['body_ratio'] = candle_body / candle_range
        
        # Wick ratios (rejection signals)
        upper_wick = high - np.maximum(close, open_)
        lower_wick = np.minimum(close, open_) - low
        
        df['upper_wick_ratio'] = upper_wick / candle_range  # Rejection from above
        df['lower_wick_ratio'] = lower_wick / candle_range  # Rejection from below
        
        # Wick imbalance (which side has more rejection)
        df['wick_imbalance'] = df['lower_wick_ratio'] - df['upper_wick_ratio']
        
        # Close position in range (0-1, where 1 = closed at high)
        df['close_position'] = close_position
        
        # Candle direction
        df['is_bullish'] = (close > open_).astype(int)
        
        # Consecutive direction (momentum)
        df['bullish_streak'] = self._count_streak(df['is_bullish'], 1)
        df['bearish_streak'] = self._count_streak(df['is_bullish'], 0)
        
        # === AUCTION THEORY / MARKET STRUCTURE ===
        
        # Value Area approximation using rolling stats
        # POC (Point of Control) approximation = typical price
        df['typical_price'] = (high + low + close) / 3
        df['poc_20'] = df['typical_price'].rolling(20).mean()
        
        # Value Area (1 std dev around POC)
        df['price_std_20'] = close.rolling(20).std()
        df['va_high'] = df['poc_20'] + df['price_std_20']
        df['va_low'] = df['poc_20'] - df['price_std_20']
        
        # Price position relative to Value Area
        va_range = (df['va_high'] - df['va_low']).replace(0, np.nan)
        df['va_position'] = (close - df['va_low']) / va_range
        # < 0 = below VA (potential buy zone)
        # > 1 = above VA (potential sell zone)
        # 0.5 = at POC (fair value)
        
        # Distance from POC (normalized)
        df['poc_distance'] = (close - df['poc_20']) / df['price_std_20'].replace(0, 1)
        
        # Balance vs Imbalance detection
        # Low ATR = balance (consolidation), High ATR = imbalance (trending)
        df['atr_14'] = self._calculate_atr(high, low, close, 14)
        df['atr_ratio'] = df['atr_14'] / df['atr_14'].rolling(50).mean().replace(0, 1)
        
        # Rotation Factor (how much price rotates within range)
        # High rotation = balance, Low rotation = trend
        df['daily_range'] = high - low
        df['range_sma'] = df['daily_range'].rolling(10).mean()
        df['range_ratio'] = df['daily_range'] / df['range_sma'].replace(0, 1)
        
        # === SUPPORT/RESISTANCE LEVELS ===
        
        # Recent highs and lows
        df['high_20'] = high.rolling(20).max()
        df['low_20'] = low.rolling(20).min()
        
        # Distance to recent high/low (potential S/R)
        range_20 = (df['high_20'] - df['low_20']).replace(0, np.nan)
        df['dist_to_high'] = (df['high_20'] - close) / range_20
        df['dist_to_low'] = (close - df['low_20']) / range_20
        
        # Near level detection (within 1% of high/low)
        df['near_high'] = (df['dist_to_high'] < 0.05).astype(int)
        df['near_low'] = (df['dist_to_low'] < 0.05).astype(int)
        
        # Breakout detection (price outside recent range with volume)
        df['breakout_up'] = ((close > df['high_20'].shift(1)) & (df['volume_ratio'] > 1.5)).astype(int)
        df['breakout_down'] = ((close < df['low_20'].shift(1)) & (df['volume_ratio'] > 1.5)).astype(int)
        
        # === VOLUME-PRICE RELATIONSHIP ===
        
        # Price change
        df['price_change'] = close.pct_change() * 100
        df['price_change_5'] = close.pct_change(5) * 100
        
        # Volume-Price confirmation
        # Bullish: Price up + Volume up = strong
        # Bearish: Price down + Volume up = strong
        # Divergence: Price up + Volume down = weak
        df['vol_price_confirm'] = np.sign(df['price_change']) * df['volume_ratio']
        
        # Effort vs Result
        # High volume but small price move = absorption (potential reversal)
        df['effort_result'] = abs(df['price_change']) / df['volume_ratio'].replace(0, 1)
        
        # === SELECT FEATURES ===
        
        feature_cols = [
            # Volume Analysis
            'volume_ratio',           # Activity level
            'volume_trend',           # Volume momentum
            'cvd_normalized',         # Who's in control
            'cvd_momentum_norm',      # Buying/selling pressure change
            
            # Price Action
            'body_ratio',             # Conviction
            'upper_wick_ratio',       # Rejection from above
            'lower_wick_ratio',       # Rejection from below
            'wick_imbalance',         # Net rejection direction
            'close_position',         # Where price closed in range
            'bullish_streak',         # Consecutive bullish candles
            'bearish_streak',         # Consecutive bearish candles
            
            # Auction/Market Structure
            'va_position',            # Position in Value Area
            'poc_distance',           # Distance from fair value
            'atr_ratio',              # Balance vs Imbalance
            'range_ratio',            # Range expansion/contraction
            
            # Support/Resistance
            'dist_to_high',           # Distance to resistance
            'dist_to_low',            # Distance to support
            'near_high',              # At resistance
            'near_low',               # At support
            'breakout_up',            # Breaking resistance with volume
            'breakout_down',          # Breaking support with volume
            
            # Volume-Price Relationship
            'price_change',           # Current bar momentum
            'price_change_5',         # 5-bar momentum
            'vol_price_confirm',      # Confirmation signal
            'effort_result',          # Absorption detection
        ]
        
        self.feature_names = feature_cols
        
        # Fill NaN with forward fill then backward fill
        features_df = df[feature_cols].copy()
        features_df = features_df.ffill().bfill()
        
        # Replace any remaining NaN and inf with 0
        features_df = features_df.replace([np.inf, -np.inf], 0)
        features_df = features_df.fillna(0)
        
        return features_df
    
    def _count_streak(self, series: pd.Series, value: int) -> pd.Series:
        """Count consecutive occurrences of a value."""
        # Create groups where streak breaks
        groups = (series != value).cumsum()
        # Count within each group, but only where series == value
        streak = series.groupby(groups).cumsum()
        return streak.where(series == value, 0)
    
    def create_labels(self, data: pd.DataFrame, lookahead: int = 5, threshold: float = 0.002) -> pd.Series:
        """
        Create binary labels for classification.
        
        Args:
            data: DataFrame with Close column
            lookahead: Bars to look ahead
            threshold: Min price change to be considered "up" (0.002 = 0.2%)
        
        Returns:
            Series with 1 (price up) or 0 (price down/flat)
        """
        close = data['Close'] if 'Close' in data.columns else data['close']
        future_close = close.shift(-lookahead)
        
        # 1 if future price > current price * (1 + threshold)
        labels = (future_close > close * (1 + threshold)).astype(int)
        
        return labels
    
    def create_multi_class_labels(
        self,
        data: pd.DataFrame,
        lookahead: int = 10,
        profit_target: float = 0.012,  # 1.2% profit target
        stop_loss: float = 0.008,      # 0.8% stop loss
        min_confidence: float = 0.005, # 0.5% minimum move
    ) -> pd.Series:
        """
        Create 4-class labels for entry AND exit prediction.
        
        Labels:
            0 = HOLD (no clear signal, neutral zone)
            1 = LONG (bullish entry signal)
            2 = SHORT (bearish entry signal)
            3 = CLOSE (exit signal - take profit or cut loss)
        
        Args:
            data: DataFrame with OHLC columns
            lookahead: Bars to look ahead for outcome
            profit_target: Profit target as fraction (0.012 = 1.2%)
            stop_loss: Stop loss as fraction (0.008 = 0.8%)
            min_confidence: Minimum price movement to be confident
        
        Returns:
            Series with class labels (0-3)
        """
        df = data.copy()
        df.columns = [c.capitalize() for c in df.columns]
        
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        # Calculate ATR for dynamic targets
        atr = self._calculate_atr(high, low, close, 14)
        
        # Use ATR-based targets (more adaptive to volatility)
        atr_profit_target = atr * 1.5  # Target = 1.5x ATR
        atr_stop_loss = atr * 1.0      # Stop = 1x ATR
        
        # Calculate forward price movement over lookahead period
        future_high = high.shift(-1).rolling(lookahead).max()
        future_low = low.shift(-1).rolling(lookahead).min()
        
        # Calculate potential outcomes for LONG and SHORT
        long_profit = (future_high - close) / close
        long_loss = (close - future_low) / close
        short_profit = (close - future_low) / close
        short_loss = (future_high - close) / close
        
        # Initialize labels as HOLD (0)
        labels = pd.Series(0, index=df.index, dtype=int)
        
        # LONG signal: If LONG has better risk/reward than SHORT
        long_rr = long_profit / (long_loss + 0.001)
        short_rr = short_profit / (short_loss + 0.001)
        
        # Dynamic profit target based on ATR
        profit_threshold = atr_profit_target / close
        
        # === CLOSE SIGNAL DETECTION (Before Entry Signals) ===
        # CLOSE signal: Price made significant move and about to reverse
        
        # Recent price change (momentum)
        price_change_5 = close.pct_change(5)  # 5-bar momentum
        price_change_10 = close.pct_change(10)  # 10-bar momentum
        
        # Future reversal detection
        # For LONG positions: price went up, but will come down
        long_made_profit = price_change_5 > 0.005  # Up 0.5% recently
        long_will_reverse = (close - future_low) / close > 0.008  # Will drop 0.8%+
        
        # For SHORT positions: price went down, but will come up
        short_made_profit = price_change_5 < -0.005  # Down 0.5% recently
        short_will_reverse = (future_high - close) / close > 0.008  # Will rise 0.8%+
        
        # Overbought/Oversold detection (simple version using price position)
        rolling_high = high.rolling(20).max()
        rolling_low = low.rolling(20).min()
        price_position = (close - rolling_low) / (rolling_high - rolling_low + 0.0001)
        
        overbought = price_position > 0.85  # Near 20-bar high
        oversold = price_position < 0.15    # Near 20-bar low
        
        # Label CLOSE (3): When should exit position
        close_mask = (
            # Scenario 1: Long position made profit but will reverse
            ((long_made_profit & long_will_reverse & overbought) |
            # Scenario 2: Short position made profit but will reverse
            (short_made_profit & short_will_reverse & oversold) |
            # Scenario 3: Momentum exhaustion (big move, about to reverse)
            ((abs(price_change_10) > 0.02) & (abs(price_change_5) < 0.002)))
        )
        labels[close_mask] = 3
        
        # === ENTRY SIGNALS ===
        # Label LONG (1) only where NOT already labeled CLOSE
        long_mask = (
            (long_profit > profit_threshold) &
            (long_rr > 1.2) &
            (long_profit > short_profit + min_confidence) &
            (labels != 3)  # Don't override CLOSE
        )
        labels[long_mask] = 1
        
        # Label SHORT (2) only where NOT already labeled CLOSE
        short_mask = (
            (short_profit > profit_threshold) &
            (short_rr > 1.2) &
            (short_profit > long_profit + min_confidence) &
            (labels != 3)  # Don't override CLOSE
        )
        labels[short_mask] = 2
        
        return labels
    
    def _calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate ATR."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr
    
    def get_feature_names(self) -> list:
        """Return list of feature names."""
        return self.feature_names
