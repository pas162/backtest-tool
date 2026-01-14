"""
Strategies package.
Registry of all available trading strategies.
"""

from backend.strategies.base import BaseStrategy
from backend.strategies.vwap_supertrend_ema import VWAPSuperTrendEMA
from backend.strategies.vwap_supertrend_ema_v2 import VWAPSuperTrendEMAv2


# Strategy registry
STRATEGIES = {
    "vwap_supertrend_ema": VWAPSuperTrendEMA,
    "vwap_supertrend_ema_v2": VWAPSuperTrendEMAv2,
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
    "VWAPSuperTrendEMAv2",
    "get_strategy_class",
    "get_all_strategies",
]
