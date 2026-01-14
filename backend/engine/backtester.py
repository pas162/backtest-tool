"""
Backtesting engine module.
Wraps backtesting.py for running strategy backtests.
"""

import math
from datetime import datetime
from typing import Any
import pandas as pd
from backtesting import Backtest
from loguru import logger

from backend.config import settings
from backend.strategies.base import BaseStrategy


def sanitize_for_json(value):
    """Convert NaN/Inf values to None for JSON compatibility."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
    return value


def sanitize_dict_for_json(d: dict) -> dict:
    """Recursively sanitize a dictionary for JSON serialization."""
    return {k: sanitize_for_json(v) for k, v in d.items()}


class BacktestEngine:
    """Engine for running backtests."""
    
    def __init__(
        self,
        cash: float = None,
        commission: float = None
    ):
        self.cash = cash or settings.default_cash
        self.commission = commission or settings.default_commission
    
    def run(
        self,
        strategy_class: type[BaseStrategy],
        data: pd.DataFrame,
        **strategy_params
    ) -> dict[str, Any]:
        """
        Run a backtest.
        
        Args:
            strategy_class: Strategy class to backtest
            data: DataFrame with OHLCV data
            **strategy_params: Strategy-specific parameters
            
        Returns:
            Dict with metrics, equity_curve, and trades
        """
        # Create backtest instance
        bt = Backtest(
            data,
            strategy_class,
            cash=self.cash,
            commission=self.commission,
            exclusive_orders=True
        )
        
        # Run backtest with parameters
        stats = bt.run(**strategy_params)
        
        # Extract metrics
        metrics = self._extract_metrics(stats)
        
        # Extract equity curve
        equity_curve = self._extract_equity_curve(stats)
        
        # Extract trades
        trades = self._extract_trades(stats)
        
        logger.info(
            f"Backtest complete: {len(trades)} trades, "
            f"{metrics['return_pct']:.2f}% return"
        )
        
        return {
            "metrics": metrics,
            "equity_curve": equity_curve,
            "trades": trades
        }
    
    def _extract_metrics(self, stats) -> dict:
        """Extract performance metrics from backtest stats."""
        metrics = {
            "return_pct": float(stats.get("Return [%]", 0)),
            "buy_hold_return_pct": float(stats.get("Buy & Hold Return [%]", 0)),
            "max_drawdown_pct": float(stats.get("Max. Drawdown [%]", 0)),
            "win_rate_pct": float(stats.get("Win Rate [%]", 0)),
            "total_trades": int(stats.get("# Trades", 0)),
            "avg_trade_pct": float(stats.get("Avg. Trade [%]", 0)),
            "sharpe_ratio": stats.get("Sharpe Ratio"),
            "profit_factor": stats.get("Profit Factor"),
        }
        # Sanitize NaN/Inf values for JSON
        return sanitize_dict_for_json(metrics)
    
    def _extract_equity_curve(self, stats) -> list[dict]:
        """Extract equity curve data."""
        equity = stats.get("_equity_curve")
        if equity is None:
            return []
        
        result = []
        for timestamp, row in equity.iterrows():
            equity_val = row.get("Equity", 0)
            result.append({
                "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                "equity": sanitize_for_json(float(equity_val))
            })
        
        return result
    
    def _extract_trades(self, stats) -> list[dict]:
        """Extract trade records."""
        trades_df = stats.get("_trades")
        if trades_df is None or trades_df.empty:
            return []
        
        result = []
        for _, trade in trades_df.iterrows():
            entry_time = trade.get("EntryTime")
            exit_time = trade.get("ExitTime")
            
            result.append({
                "entry_time": entry_time.isoformat() if hasattr(entry_time, 'isoformat') else str(entry_time),
                "exit_time": exit_time.isoformat() if hasattr(exit_time, 'isoformat') else str(exit_time),
                "side": "long" if trade.get("Size", 0) > 0 else "short",
                "entry_price": sanitize_for_json(float(trade.get("EntryPrice", 0))),
                "exit_price": sanitize_for_json(float(trade.get("ExitPrice", 0))),
                "size": abs(float(trade.get("Size", 0))),
                "pnl": sanitize_for_json(float(trade.get("PnL", 0))),
                "pnl_pct": sanitize_for_json(float(trade.get("ReturnPct", 0)) * 100),
                "signal_type": trade.get("Tag")
            })
        
        return result
