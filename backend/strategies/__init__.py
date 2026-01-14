"""
Strategies package.
Registry of all available trading strategies.
"""

from backend.strategies.base import BaseStrategy
from backend.strategies.vwap_supertrend_ema import VWAPSuperTrendEMA


# Strategy registry
STRATEGIES = {
    "vwap_supertrend_ema": VWAPSuperTrendEMA,
}


def get_strategy_class(name: str) -> type[BaseStrategy] | None:
    """Get strategy class by name."""
    return STRATEGIES.get(name)


def get_all_strategies() -> list[dict]:
    """Get metadata for all registered strategies."""
    return [
        {
            "name": name,
            "display_name": cls.__name__,
            "description": cls.__doc__ or "",
            "parameters": cls.get_parameters()
        }
        for name, cls in STRATEGIES.items()
    ]


__all__ = [
    "BaseStrategy",
    "VWAPSuperTrendEMA",
    "get_strategy_class",
    "get_all_strategies",
]
