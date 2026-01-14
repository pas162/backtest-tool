"""
Base strategy class.
All strategies must inherit from this base class.
"""

from abc import abstractmethod
from backtesting import Strategy


class BaseStrategy(Strategy):
    """
    Abstract base class for all trading strategies.
    
    Subclasses must implement:
    - init(): Calculate indicators
    - next(): Execute trading logic
    """
    
    @abstractmethod
    def init(self):
        """
        Initialize indicators.
        Called once before backtesting starts.
        Use self.I() to create indicators.
        """
        pass
    
    @abstractmethod
    def next(self):
        """
        Execute trading logic for each candle.
        Called for each new bar/candle.
        Use self.buy() and self.sell() to place orders.
        """
        pass
    
    @classmethod
    def get_parameters(cls) -> list[dict]:
        """
        Get list of optimizable parameters.
        
        Returns:
            List of dicts with keys: name, type, default, min, max
        """
        return []
    
    @classmethod
    def get_info(cls) -> dict:
        """
        Get strategy metadata.
        
        Returns:
            Dict with keys: name, display_name, description, parameters
        """
        return {
            "name": cls.__name__.lower(),
            "display_name": cls.__name__,
            "description": cls.__doc__ or "",
            "parameters": cls.get_parameters()
        }
