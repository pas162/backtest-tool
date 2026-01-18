"""
Fast ML Agent for Trading Replay.

Pre-calculates all features ONCE before replay starts,
then just looks up predictions during replay (instant).
"""

import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from typing import Optional

from backend.replay.engine import Decision
from backend.replay.agent import TradingAgent
from backend.ml.features import FeatureEngineer


class FastMLAgent(TradingAgent):
    """
    Fast ML agent - pre-calculates all predictions.
    
    Key optimization: Features are calculated ONCE for all data,
    not recalculated on every bar.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        buy_threshold: float = 0.55,  # Lowered from 0.6 for more trades
        sell_threshold: float = 0.45,  # Raised from 0.4 for more trades
    ):
        super().__init__()
        
        # Get model path from registry if not provided
        if model_path is None:
            model_path = self._get_active_model_path()
        
        self.model_path = Path(model_path) if model_path else None
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self._position = None
        
        # Pre-calculated data
        self._all_predictions = None
        self._current_bar_index = 0
        
        # Load model
        if self.model_path and self.model_path.exists():
            self._load_model()
    
    def _get_active_model_path(self) -> Optional[str]:
        """Get active model path from registry."""
        try:
            from backend.ml.model_registry import get_registry
            registry = get_registry()
            return registry.get_active_model_path()
        except Exception:
            # Fallback to default
            return "models/trading_model.pkl"
    
    def _load_model(self):
        """Load model from disk."""
        try:
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.feature_engineer.feature_names = data["feature_names"]
        except Exception as e:
            print(f"Failed to load model: {e}")
            self.model = None
    
    def prepare(self, full_data: pd.DataFrame):
        """
        Pre-calculate ALL features and predictions ONCE.
        Call this before starting replay.
        """
        if self.model is None:
            print("Model not loaded!")
            return
        
        print(f"Pre-calculating features for {len(full_data)} bars...")
        
        # Calculate features for ALL data at once
        features = self.feature_engineer.create_features(full_data)
        
        # Store the original data index for mapping
        self._data_index = list(full_data.index)
        
        # Predict ALL at once
        self._all_predictions = self.model.predict_proba(features)
        
        # Debug: show prediction distribution
        prob_ups = self._all_predictions[:, 1]
        buy_signals = (prob_ups >= self.buy_threshold).sum()
        sell_signals = (prob_ups <= self.sell_threshold).sum()
        print(f"Pre-calculation complete: {len(self._all_predictions)} predictions ready")
        print(f"  - BUY signals (prob >= {self.buy_threshold}): {buy_signals}")
        print(f"  - SELL signals (prob <= {self.sell_threshold}): {sell_signals}")
        print(f"  - Prob range: {prob_ups.min():.3f} - {prob_ups.max():.3f}")
        
        self._current_bar_index = 0
    
    def analyze(self, data: pd.DataFrame, order_flow: dict) -> Decision:
        """
        Analyze current bar using pre-calculated predictions.
        INSTANT - just a dictionary lookup!
        """
        # If no pre-calculated predictions, use fallback
        if self._all_predictions is None:
            self._last_reasoning = "No predictions - prepare() not called"
            return Decision.HOLD
        
        # Get the CURRENT bar's index from visible_data
        current_timestamp = data.index[-1]
        
        # Find the position of this timestamp in the original data
        try:
            bar_position = self._data_index.index(current_timestamp)
        except (ValueError, AttributeError):
            # Fallback: use length-based indexing
            bar_position = len(data) - 1
        
        # Check bounds
        if bar_position >= len(self._all_predictions):
            self._last_reasoning = f"Index {bar_position} out of bounds ({len(self._all_predictions)})"
            return Decision.HOLD
        
        # Get pre-calculated prediction (INSTANT!)
        prob = self._all_predictions[bar_position]
        prob_up = prob[1]
        
        # Decision logic with proper position management
        # If we have a position, check if we should close it
        if self._position is not None:
            # Close LONG if probability drops below neutral zone
            if self._position == "long" and prob_up < 0.5:
                self._last_reasoning = f"CLOSE LONG: prob_up={prob_up:.2f} (reversal)"
                self._position = None
                return Decision.CLOSE
            
            # Close SHORT if probability rises above neutral zone
            elif self._position == "short" and prob_up > 0.5:
                self._last_reasoning = f"CLOSE SHORT: prob_up={prob_up:.2f} (reversal)"
                self._position = None
                return Decision.CLOSE
            
            # Hold position if still in favorable zone
            else:
                self._last_reasoning = f"HOLD {self._position.upper()}: prob_up={prob_up:.2f}"
                return Decision.HOLD
        
        # If flat, check if we should open a position
        else:
            # Open LONG if strong bullish signal
            if prob_up >= self.buy_threshold:
                self._last_reasoning = f"OPEN LONG: prob_up={prob_up:.2f}"
                self._position = "long"
                return Decision.BUY
            
            # Open SHORT if strong bearish signal
            elif prob_up <= self.sell_threshold:
                self._last_reasoning = f"OPEN SHORT: prob_up={prob_up:.2f}"
                self._position = "short"
                return Decision.SELL
            
            # Stay flat if no strong signal
            else:
                self._last_reasoning = f"FLAT: prob_up={prob_up:.2f} (neutral)"
                return Decision.HOLD
    
    @property
    def is_model_loaded(self) -> bool:
        return self.model is not None
