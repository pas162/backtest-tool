"""
ML-Based Trading Strategy.

Uses trained XGBoost model for trading decisions.
Compatible with backtesting.py library.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import joblib

from backend.strategies.base import BaseStrategy
from backend.ml.features import FeatureEngineer


class MLStrategy(BaseStrategy):
    """
    Machine Learning based trading strategy using XGBoost.
    
    Loads a pre-trained model and makes predictions based on
    22 technical features including:
    - Trend indicators (EMA ratios)
    - Momentum (RSI, MACD)
    - Volatility (ATR, Bollinger Bands)
    - Order flow (CVD, volume ratio)
    """
    
    # Strategy parameters
    model_path = "models/trading_model.pkl"
    buy_threshold = 0.55
    sell_threshold = 0.45
    stop_loss_pct = 5.0
    take_profit_pct = 10.0
    
    def init(self):
        """Initialize ML model and feature engineer."""
        self.feature_engineer = FeatureEngineer()
        self.model = None
        self.model_loaded = False
        
        # Try to load model
        model_file = Path(self.model_path)
        if model_file.exists():
            try:
                data = joblib.load(model_file)
                self.model = data["model"]
                self.feature_engineer.feature_names = data.get("feature_names", [])
                self.model_loaded = True
            except Exception as e:
                print(f"Failed to load model: {e}")
        
        # Track position
        self._last_signal = None
    
    def next(self):
        """Execute ML-based trading logic."""
        # Need minimum bars for features
        if len(self.data) < 60:
            return
        
        # If model not loaded, skip
        if not self.model_loaded:
            return
        
        try:
            # Get visible data up to current bar (NO LOOK-AHEAD!)
            current_index = len(self.data)
            visible_df = self.data.df.iloc[:current_index].copy()
            
            # Create features
            features = self.feature_engineer.create_features(visible_df)
            
            # Get latest features
            current_features = features.iloc[[-1]]
            
            # Predict
            prob = self.model.predict_proba(current_features)[0]
            prob_up = prob[1]  # Probability price goes up
            
            # Trading logic
            # Trading logic (Futures: Bi-directional)
            if prob_up >= self.buy_threshold:
                # BUY signal (Long)
                # If currently Short, close it first
                if self.position and self.position.is_short:
                    self.position.close()
                
                # If no position (or closed), open Long
                if not self.position:
                    sl = self.data.Close[-1] * (1 - self.stop_loss_pct / 100)
                    tp = self.data.Close[-1] * (1 + self.take_profit_pct / 100)
                    self.buy(sl=sl, tp=tp)
                    self._last_signal = "BUY"
                
            elif prob_up <= self.sell_threshold:
                # SELL signal (Short)
                # If currently Long, close it first
                if self.position and self.position.is_long:
                    self.position.close()
                
                # If no position (or closed), open Short
                if not self.position:
                    sl = self.data.Close[-1] * (1 + self.stop_loss_pct / 100)
                    tp = self.data.Close[-1] * (1 - self.take_profit_pct / 100)
                    self.sell(sl=sl, tp=tp)
                    self._last_signal = "SELL"
                
        except Exception as e:
            # Silently skip on errors
            pass
    
    @classmethod
    def get_parameters(cls) -> list[dict]:
        """Get list of optimizable parameters."""
        return [
            {
                "name": "buy_threshold",
                "type": "float",
                "default": 0.60,
                "min": 0.50,
                "max": 0.80,
                "description": "Probability threshold for BUY signal"
            },
            {
                "name": "sell_threshold",
                "type": "float",
                "default": 0.40,
                "min": 0.20,
                "max": 0.50,
                "description": "Probability threshold for SELL/CLOSE signal"
            },
            {
                "name": "stop_loss_pct",
                "type": "float",
                "default": 5.0,
                "min": 1.0,
                "max": 20.0,
                "description": "Stop loss percentage"
            },
            {
                "name": "take_profit_pct",
                "type": "float",
                "default": 10.0,
                "min": 1.0,
                "max": 50.0,
                "description": "Take profit percentage"
            },
        ]
