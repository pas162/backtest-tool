"""
Trading Agent Interface and Implementations.

Agents make trading decisions based on visible market data.
They must not have access to future data.
"""

from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd

from backend.replay.engine import Decision


class TradingAgent(ABC):
    """
    Abstract base class for trading agents.
    
    All agents must implement:
    - analyze(): Make a trading decision
    - get_reasoning(): Explain the decision
    """
    
    def __init__(self):
        self._last_reasoning = ""
    
    @abstractmethod
    def analyze(self, data: pd.DataFrame, order_flow: dict) -> Decision:
        """
        Analyze market data and make a trading decision.
        
        Args:
            data: OHLCV DataFrame up to current bar (no future data!)
            order_flow: Order flow metrics (volume delta, CVD, etc.)
        
        Returns:
            Decision: BUY, SELL, HOLD, or CLOSE
        """
        pass
    
    def get_reasoning(self) -> str:
        """Return explanation for the last decision."""
        return self._last_reasoning


class SimpleOrderFlowAgent(TradingAgent):
    """
    Simple order flow based trading agent.
    
    Logic:
    - BUY when: High volume + positive CVD + momentum turning up
    - SELL when: High volume + negative CVD + momentum turning down
    - CLOSE when: CVD reverses against position
    """
    
    def __init__(
        self,
        cvd_threshold: float = 1000,
        volume_threshold: float = 1.5,
        momentum_threshold: float = 0.5,
    ):
        super().__init__()
        self.cvd_threshold = cvd_threshold
        self.volume_threshold = volume_threshold
        self.momentum_threshold = momentum_threshold
        self._position = None  # Track our view of position
    
    def analyze(self, data: pd.DataFrame, order_flow: dict) -> Decision:
        if len(data) < 20:
            self._last_reasoning = "Not enough data for analysis"
            return Decision.HOLD
        
        # Extract metrics
        cvd = order_flow.get("cvd", 0)
        volume_ratio = order_flow.get("volume_ratio", 1.0)
        momentum = order_flow.get("momentum", 0)
        is_high_volume = order_flow.get("is_high_volume", False)
        
        # Current price info
        current = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Trend detection using EMA
        close = data['Close']
        ema20 = close.ewm(span=20).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1] if len(close) >= 50 else ema20
        
        is_uptrend = ema20 > ema50
        is_downtrend = ema20 < ema50
        
        # Build reasoning
        reasons = []
        
        # Check for strong buy signal
        if (
            is_high_volume and
            cvd > self.cvd_threshold and
            momentum > self.momentum_threshold and
            is_uptrend
        ):
            reasons.append(f"High volume ({volume_ratio:.1f}x avg)")
            reasons.append(f"Positive CVD ({cvd:.0f})")
            reasons.append(f"Momentum up ({momentum:.2f}%)")
            reasons.append(f"Uptrend (EMA20 > EMA50)")
            self._last_reasoning = " | ".join(reasons)
            self._position = "long"
            return Decision.BUY
        
        # Check for strong sell signal
        if (
            is_high_volume and
            cvd < -self.cvd_threshold and
            momentum < -self.momentum_threshold and
            is_downtrend
        ):
            reasons.append(f"High volume ({volume_ratio:.1f}x avg)")
            reasons.append(f"Negative CVD ({cvd:.0f})")
            reasons.append(f"Momentum down ({momentum:.2f}%)")
            reasons.append(f"Downtrend (EMA20 < EMA50)")
            self._last_reasoning = " | ".join(reasons)
            self._position = "short"
            return Decision.SELL
        
        # Check for exit signals
        if self._position == "long" and (cvd < 0 or momentum < -self.momentum_threshold):
            reasons.append(f"Exit long: CVD turned negative ({cvd:.0f})")
            self._last_reasoning = " | ".join(reasons)
            self._position = None
            return Decision.CLOSE
        
        if self._position == "short" and (cvd > 0 or momentum > self.momentum_threshold):
            reasons.append(f"Exit short: CVD turned positive ({cvd:.0f})")
            self._last_reasoning = " | ".join(reasons)
            self._position = None
            return Decision.CLOSE
        
        # No signal
        self._last_reasoning = f"No signal: CVD={cvd:.0f}, Vol={volume_ratio:.1f}x, Mom={momentum:.2f}%"
        return Decision.HOLD


class MomentumAgent(TradingAgent):
    """
    Momentum-based agent using price action.
    
    Simpler than order flow, for comparison testing.
    """
    
    def __init__(self, lookback: int = 10, threshold: float = 1.0):
        super().__init__()
        self.lookback = lookback
        self.threshold = threshold
        self._position = None
    
    def analyze(self, data: pd.DataFrame, order_flow: dict) -> Decision:
        if len(data) < self.lookback + 5:
            self._last_reasoning = "Not enough data"
            return Decision.HOLD
        
        close = data['Close']
        current = close.iloc[-1]
        past = close.iloc[-self.lookback]
        
        momentum = (current - past) / past * 100
        
        # Simple momentum crossover
        if momentum > self.threshold and self._position != "long":
            self._last_reasoning = f"Momentum up {momentum:.2f}% > {self.threshold}%"
            self._position = "long"
            return Decision.BUY
        
        if momentum < -self.threshold and self._position != "short":
            self._last_reasoning = f"Momentum down {momentum:.2f}% < -{self.threshold}%"
            self._position = "short"
            return Decision.SELL
        
        # Exit on reversal
        if self._position == "long" and momentum < 0:
            self._last_reasoning = f"Exit long: momentum reversed ({momentum:.2f}%)"
            self._position = None
            return Decision.CLOSE
        
        if self._position == "short" and momentum > 0:
            self._last_reasoning = f"Exit short: momentum reversed ({momentum:.2f}%)"
            self._position = None
            return Decision.CLOSE
        
        self._last_reasoning = f"Hold: momentum = {momentum:.2f}%"
        return Decision.HOLD
