"""
Feature Engineering for ML Trading Agent.

Creates technical indicators and order flow features from OHLCV data.
"""

import pandas as pd
import numpy as np
from typing import Optional


class FeatureEngineer:
    """
    Generates features from OHLCV data for ML model.
    
    Features include:
    - Technical indicators (RSI, MACD, EMA ratios)
    - Volume features (volume ratio, CVD)
    - Price patterns (momentum, candle patterns)
    """
    
    def __init__(self):
        self.feature_names = []
    
    def create_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create all features from OHLCV data.
        
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
        
        # === TREND FEATURES ===
        
        # EMA ratios
        df['ema_5'] = close.ewm(span=5).mean()
        df['ema_10'] = close.ewm(span=10).mean()
        df['ema_20'] = close.ewm(span=20).mean()
        df['ema_50'] = close.ewm(span=50).mean()
        
        df['ema_5_10_ratio'] = df['ema_5'] / df['ema_10']
        df['ema_10_20_ratio'] = df['ema_10'] / df['ema_20']
        df['ema_20_50_ratio'] = df['ema_20'] / df['ema_50']
        
        # Price vs EMAs
        df['price_ema20_ratio'] = close / df['ema_20']
        df['price_ema50_ratio'] = close / df['ema_50']
        
        # === MOMENTUM FEATURES ===
        
        # RSI
        df['rsi_14'] = self._calculate_rsi(close, 14)
        df['rsi_7'] = self._calculate_rsi(close, 7)
        
        # Momentum (price change)
        df['momentum_3'] = close.pct_change(3) * 100
        df['momentum_5'] = close.pct_change(5) * 100
        df['momentum_10'] = close.pct_change(10) * 100
        
        # Rate of change
        df['roc_5'] = (close - close.shift(5)) / close.shift(5) * 100
        
        # === MACD ===
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # === VOLATILITY FEATURES ===
        
        # ATR
        df['atr_14'] = self._calculate_atr(high, low, close, 14)
        df['atr_pct'] = df['atr_14'] / close * 100
        
        # Bollinger Bands
        df['bb_middle'] = close.rolling(20).mean()
        df['bb_std'] = close.rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        df['bb_position'] = (close - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # === VOLUME FEATURES ===
        
        # Volume ratio
        df['volume_sma_20'] = volume.rolling(20).mean()
        df['volume_ratio'] = volume / df['volume_sma_20']
        
        # Volume change
        df['volume_change'] = volume.pct_change() * 100
        
        # CVD (Cumulative Volume Delta) approximation
        # Green candle = buy volume, Red candle = sell volume
        df['delta'] = np.where(close > open_, volume, -volume)
        df['cvd_5'] = df['delta'].rolling(5).sum()
        df['cvd_10'] = df['delta'].rolling(10).sum()
        df['cvd_normalized'] = df['cvd_10'] / df['volume_sma_20'] / 10
        
        # === CANDLE PATTERN FEATURES ===
        
        # Candle body ratio
        candle_range = high - low
        candle_body = abs(close - open_)
        df['body_ratio'] = candle_body / candle_range.replace(0, np.nan)
        
        # Upper/Lower wick
        df['upper_wick'] = np.where(close > open_, high - close, high - open_) / candle_range.replace(0, np.nan)
        df['lower_wick'] = np.where(close > open_, open_ - low, close - low) / candle_range.replace(0, np.nan)
        
        # Candle direction (1 = bullish, 0 = bearish)
        df['candle_direction'] = (close > open_).astype(int)
        
        # Consecutive candles
        df['consecutive_bullish'] = (df['candle_direction'].rolling(3).sum())
        
        # === SELECT FEATURES ===
        
        feature_cols = [
            # Trend
            'ema_5_10_ratio', 'ema_10_20_ratio', 'ema_20_50_ratio',
            'price_ema20_ratio', 'price_ema50_ratio',
            # Momentum
            'rsi_14', 'rsi_7', 'momentum_3', 'momentum_5', 'momentum_10', 'roc_5',
            # MACD
            'macd_hist',
            # Volatility
            'atr_pct', 'bb_position',
            # Volume
            'volume_ratio', 'cvd_normalized',
            # Candle
            'body_ratio', 'upper_wick', 'lower_wick', 'candle_direction', 'consecutive_bullish',
        ]
        
        self.feature_names = feature_cols
        
        # Fill NaN with forward fill then backward fill
        features_df = df[feature_cols].copy()
        features_df = features_df.ffill().bfill()
        
        # Replace any remaining NaN and inf with 0
        features_df = features_df.replace([np.inf, -np.inf], 0)
        features_df = features_df.fillna(0)
        
        return features_df
    
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
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(50)
    
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
