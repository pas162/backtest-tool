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
        num_classes = self._all_predictions.shape[1]
        
        if num_classes >= 3:
            # Multi-class model
            pred_classes = np.argmax(self._all_predictions, axis=1)
            hold_count = (pred_classes == 0).sum()
            long_count = (pred_classes == 1).sum()
            short_count = (pred_classes == 2).sum()
            close_count = (pred_classes == 3).sum() if num_classes >= 4 else 0
            
            print(f"Pre-calculation complete: {len(self._all_predictions)} predictions ready")
            print(f"  Model type: MULTI-CLASS ({num_classes} classes)")
            print(f"  - HOLD signals:  {hold_count} ({hold_count/len(pred_classes)*100:.1f}%)")
            print(f"  - LONG signals:  {long_count} ({long_count/len(pred_classes)*100:.1f}%)")
            print(f"  - SHORT signals: {short_count} ({short_count/len(pred_classes)*100:.1f}%)")
            if num_classes >= 4:
                print(f"  - CLOSE signals: {close_count} ({close_count/len(pred_classes)*100:.1f}%)")
        else:
            # Binary model (legacy)
            prob_ups = self._all_predictions[:, 1]
            buy_signals = (prob_ups >= self.buy_threshold).sum()
            sell_signals = (prob_ups <= self.sell_threshold).sum()
            print(f"Pre-calculation complete: {len(self._all_predictions)} predictions ready")
            print(f"  Model type: BINARY")
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
        probs = self._all_predictions[bar_position]
        
        # Check if model is multi-class (3+ classes) or binary (2 classes)
        num_classes = probs.shape[0]
        is_multi_class = num_classes >= 3
        
        if is_multi_class:
            # MULTI-CLASS: [prob_hold, prob_long, prob_short, ...]
            # Get action with highest probability
            action_idx = np.argmax(probs)
            confidence = probs[action_idx]
            
            # Minimum confidence threshold
            min_confidence = 0.40  # 40% confidence required
            
            if confidence < min_confidence:
                self._last_reasoning = f"Low confidence: max_prob={confidence:.2f} < {min_confidence}"
                return Decision.HOLD
            
            # Map prediction to action
            if action_idx == 0:  # HOLD
                self._last_reasoning = f"HOLD predicted: prob={confidence:.2f}"
                return Decision.HOLD
                
            elif action_idx == 1:  # LONG
                if self._position is None:
                    self._last_reasoning = f"OPEN LONG: prob={confidence:.2f}"
                    self._position = "long"
                    return Decision.BUY
                elif self._position == "short":
                    # Close short before going long
                    self._last_reasoning = f"CLOSE SHORT (reversal): prob_long={confidence:.2f}"
                    self._position = None
                    return Decision.CLOSE
                else:
                    # Already long, hold
                    self._last_reasoning = f"HOLD LONG: prob={confidence:.2f}"
                    return Decision.HOLD
                    
            elif action_idx == 2:  # SHORT
                if self._position is None:
                    self._last_reasoning = f"OPEN SHORT: prob={confidence:.2f}"
                    self._position = "short"
                    return Decision.SELL
                elif self._position == "long":
                    # Close long before going short
                    self._last_reasoning = f"CLOSE LONG (reversal): prob_short={confidence:.2f}"
                    self._position = None
                    return Decision.CLOSE
                else:
                    # Already short, hold
                    self._last_reasoning = f"HOLD SHORT: prob={confidence:.2f}"
                    return Decision.HOLD
                    
            elif action_idx == 3:  # CLOSE - Model predicts exit
                if self._position is not None:
                    self._last_reasoning = f"CLOSE POSITION: prob={confidence:.2f} (exit signal)"
                    self._position = None
                    return Decision.CLOSE
                else:
                    # No position to close, treat as HOLD
                    self._last_reasoning = f"NO POSITION to close: prob={confidence:.2f}"
                    return Decision.HOLD
                    
            else:
                # Unknown class (shouldn't happen)
                self._last_reasoning = f"Unknown class: {action_idx}"
                return Decision.HOLD
                
        else:
            # BINARY: [prob_down, prob_up] - Legacy mode
            prob_up = probs[1]
            
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
