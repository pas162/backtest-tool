"""
ML-Based Trading Agent.

Uses trained XGBoost/RandomForest model for trading decisions.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from typing import Optional

from backend.replay.engine import Decision
from backend.replay.agent import TradingAgent
from backend.ml.features import FeatureEngineer


class MLTradingAgent(TradingAgent):
    """
    ML-based trading agent using XGBoost or RandomForest.
    
    Makes decisions based on model predictions with confidence thresholds.
    """
    
    def __init__(
        self,
        model_path: str = "models/trading_model.pkl",
        buy_threshold: float = 0.6,
        sell_threshold: float = 0.4,
        min_confidence: float = 0.55,
    ):
        """
        Initialize ML agent.
        
        Args:
            model_path: Path to saved model
            buy_threshold: Min probability for BUY signal
            sell_threshold: Max probability for SELL signal
            min_confidence: Min abs(prob - 0.5) to take action
        """
        super().__init__()
        
        self.model_path = Path(model_path)
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.min_confidence = min_confidence
        
        self.model = None
        self.model_type = None
        self.feature_engineer = FeatureEngineer()
        self._position = None
        
        # Try to load model
        if self.model_path.exists():
            self._load_model()
    
    def _load_model(self):
        """Load model from disk."""
        try:
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.model_type = data["model_type"]
            self.feature_engineer.feature_names = data["feature_names"]
        except Exception as e:
            print(f"Failed to load model: {e}")
            self.model = None
    
    def analyze(self, data: pd.DataFrame, order_flow: dict) -> Decision:
        """
        Analyze data and make trading decision.
        
        Args:
            data: OHLCV DataFrame (only historical data)
            order_flow: Order flow metrics
        
        Returns:
            Trading decision
        """
        # Fallback if model not loaded
        if self.model is None:
            self._last_reasoning = "Model not loaded - using fallback"
            return self._fallback_decision(data, order_flow)
        
        # Need enough data for features
        if len(data) < 60:
            self._last_reasoning = "Not enough data for ML features"
            return Decision.HOLD
        
        # Create features
        try:
            features = self.feature_engineer.create_features(data)
            
            # Get last row (current bar)
            current_features = features.iloc[[-1]]
            
            # Get prediction probability
            prob = self.model.predict_proba(current_features)[0]
            prob_up = prob[1]  # Probability of price going up
            
            confidence = abs(prob_up - 0.5) * 2  # 0 to 1 scale
            
        except Exception as e:
            self._last_reasoning = f"Feature error: {str(e)}"
            return Decision.HOLD
        
        # Make decision based on probability
        if prob_up >= self.buy_threshold and confidence >= self.min_confidence:
            if self._position == "short":
                self._last_reasoning = f"ML: Close short + Open long (prob_up={prob_up:.2f})"
                self._position = "long"
                return Decision.BUY
            elif self._position != "long":
                self._last_reasoning = f"ML: Open long (prob_up={prob_up:.2f})"
                self._position = "long"
                return Decision.BUY
        
        elif prob_up <= self.sell_threshold and confidence >= self.min_confidence:
            if self._position == "long":
                self._last_reasoning = f"ML: Close long + Open short (prob_up={prob_up:.2f})"
                self._position = "short"
                return Decision.SELL
            elif self._position != "short":
                self._last_reasoning = f"ML: Open short (prob_up={prob_up:.2f})"
                self._position = "short"
                return Decision.SELL
        
        # Exit position if confidence is low
        elif self._position and confidence < 0.1:
            self._last_reasoning = f"ML: Close position - low confidence ({confidence:.2f})"
            self._position = None
            return Decision.CLOSE
        
        self._last_reasoning = f"ML: Hold (prob_up={prob_up:.2f}, conf={confidence:.2f})"
        return Decision.HOLD
    
    def _fallback_decision(self, data: pd.DataFrame, order_flow: dict) -> Decision:
        """Fallback decision when model not available."""
        # Simple momentum-based fallback
        if len(data) < 10:
            return Decision.HOLD
        
        close = data['Close'] if 'Close' in data.columns else data['close']
        momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100
        
        if momentum > 0.5 and self._position != "long":
            self._last_reasoning = f"Fallback: momentum up {momentum:.2f}%"
            self._position = "long"
            return Decision.BUY
        elif momentum < -0.5 and self._position != "short":
            self._last_reasoning = f"Fallback: momentum down {momentum:.2f}%"
            self._position = "short"
            return Decision.SELL
        
        return Decision.HOLD
    
    @property
    def is_model_loaded(self) -> bool:
        """Check if model is loaded."""
        return self.model is not None
