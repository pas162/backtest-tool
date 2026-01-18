"""
Replay Engine - Simulates real-time trading using historical data.

The engine processes data bar-by-bar, ensuring the AI agent only sees
historical data up to the current bar (no look-ahead bias).
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable
from enum import Enum
import pandas as pd


class Decision(Enum):
    """Trading decision types."""
    HOLD = "HOLD"
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"


@dataclass
class Position:
    """Represents an open position."""
    side: str  # "long" or "short"
    entry_price: float
    entry_time: datetime
    size: float  # Position size in dollars
    leverage: float = 1.0  # Leverage multiplier
    
    def pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL in dollars."""
        # Price change percentage
        if self.side == "long":
            price_change_pct = (current_price - self.entry_price) / self.entry_price
        else:
            price_change_pct = (self.entry_price - current_price) / self.entry_price
        
        # PnL = position_value * leverage * price_change_pct
        position_value = self.size
        pnl_dollars = position_value * self.leverage * price_change_pct
        return pnl_dollars


@dataclass
class Trade:
    """Completed trade record."""
    side: str
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    fee: float = 0.0


@dataclass
class DecisionLog:
    """Log entry for each decision made."""
    timestamp: datetime
    bar_index: int
    price: float
    decision: Decision
    reasoning: str
    position: Optional[str] = None
    unrealized_pnl: Optional[float] = None


@dataclass
class ReplayState:
    """Current state of the replay simulation."""
    current_bar: int = 0
    position: Optional[Position] = None
    equity: float = 100.0
    initial_capital: float = 100.0
    trades: list = field(default_factory=list)
    decision_log: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)


class ReplayEngine:
    """
    Event-driven backtesting engine that simulates real-time trading.
    
    Key features:
    - Processes data bar-by-bar
    - AI agent only sees historical data (no look-ahead)
    - Logs every decision with reasoning
    - Tracks equity curve and trades
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        agent,  # TradingAgent instance
        initial_capital: float = 100.0,
        position_size: float = 10.0,
        commission: float = 0.001,
        leverage: float = 1.0,
    ):
        """
        Initialize replay engine.
        
        Args:
            data: OHLCV DataFrame with DatetimeIndex
            agent: TradingAgent instance
            initial_capital: Starting capital
            position_size: Size per trade in dollars
            commission: Commission rate (0.001 = 0.1%)
            leverage: Leverage multiplier (1-100x)
        """
        self.data = data
        self.agent = agent
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.commission = commission
        self.leverage = leverage
        
        self.state = ReplayState(
            equity=initial_capital,
            initial_capital=initial_capital,
        )
        
        self._on_bar_callback: Optional[Callable] = None
        self._on_trade_callback: Optional[Callable] = None
        self._running = False
    
    def on_bar(self, callback: Callable):
        """Register callback for each bar processed."""
        self._on_bar_callback = callback
    
    def on_trade(self, callback: Callable):
        """Register callback for each trade."""
        self._on_trade_callback = callback
    
    async def run(self, speed: float = 1.0, start_bar: int = 0):
        """
        Run the replay simulation.
        
        Args:
            speed: Playback speed (1.0 = real-time delay, 0 = instant)
            start_bar: Bar index to start from
        """
        self._running = True
        self.state.current_bar = start_bar
        
        # Minimum warmup period for indicators and ML features
        # Need more candles for smaller timeframes (1m, 5m)
        warmup = min(500, len(self.data) // 5)  # At least 500 candles or 20% of data
        
        for i in range(max(start_bar, warmup), len(self.data)):
            if not self._running:
                break
            
            self.state.current_bar = i
            
            # Get visible data (only up to current bar)
            visible_data = self.data.iloc[:i+1].copy()
            current_bar = self.data.iloc[i]
            current_price = current_bar['Close']
            current_time = self.data.index[i]
            
            # Calculate order flow metrics if available
            order_flow = self._calculate_order_flow(visible_data)
            
            # Agent analyzes and decides
            decision = self.agent.analyze(visible_data, order_flow)
            reasoning = self.agent.get_reasoning()
            
            # Execute decision
            self._execute_decision(decision, current_price, current_time)
            
            # Check for liquidation (stop if equity <= 0)
            current_equity = self.state.equity
            if self.state.position:
                current_equity += self.state.position.pnl(current_price)
            
            if current_equity <= 0:
                # Liquidated - close any open position and stop
                if self.state.position:
                    self._close_position(current_price, current_time)
                print(f"[LIQUIDATED] Equity: ${current_equity:.2f} at {current_time}")
                self._running = False
                break
            
            # Log decision
            log_entry = DecisionLog(
                timestamp=current_time,
                bar_index=i,
                price=current_price,
                decision=decision,
                reasoning=reasoning,
                position=self.state.position.side if self.state.position else None,
                unrealized_pnl=self.state.position.pnl(current_price) if self.state.position else None,
            )
            self.state.decision_log.append(log_entry)
            
            # Update equity curve
            unrealized = 0
            if self.state.position:
                unrealized = self.state.position.pnl(current_price)
            self.state.equity_curve.append({
                "time": current_time,
                "equity": self.state.equity + unrealized,
            })
            
            # Callbacks
            if self._on_bar_callback:
                await self._on_bar_callback(i, current_bar, decision, reasoning)
            
            # Speed control
            if speed > 0:
                await asyncio.sleep(1.0 / speed)
        
        self._running = False
        return self.get_results()
    
    def stop(self):
        """Stop the replay."""
        self._running = False
    
    def _calculate_order_flow(self, data: pd.DataFrame) -> dict:
        """Calculate order flow metrics from visible data."""
        if len(data) < 2:
            return {}
        
        # Basic volume analysis
        recent = data.tail(20)
        avg_volume = recent['Volume'].mean()
        current_volume = data.iloc[-1]['Volume']
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Price momentum
        close = data['Close']
        momentum = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100 if len(close) >= 5 else 0
        
        # Volume delta approximation (green vs red candles)
        recent_deltas = []
        for i in range(-min(10, len(data)), 0):
            bar = data.iloc[i]
            delta = bar['Volume'] if bar['Close'] > bar['Open'] else -bar['Volume']
            recent_deltas.append(delta)
        
        cvd = sum(recent_deltas)
        
        return {
            "volume_ratio": volume_ratio,
            "cvd": cvd,
            "momentum": momentum,
            "is_high_volume": volume_ratio > 1.5,
        }
    
    def _execute_decision(self, decision: Decision, price: float, time: datetime):
        """Execute a trading decision."""
        if decision == Decision.HOLD:
            return
        
        if decision == Decision.BUY:
            # Only open LONG if flat (no position)
            if self.state.position is None:
                self.state.position = Position(
                    side="long",
                    entry_price=price,
                    entry_time=time,
                    size=self.position_size,
                    leverage=self.leverage,
                )
            # Ignore BUY if already in a position (agent should CLOSE first)
        
        elif decision == Decision.SELL:
            # Only open SHORT if flat (no position)
            if self.state.position is None:
                self.state.position = Position(
                    side="short",
                    entry_price=price,
                    entry_time=time,
                    size=self.position_size,
                    leverage=self.leverage,
                )
            # Ignore SELL if already in a position (agent should CLOSE first)
        
        elif decision == Decision.CLOSE:
            if self.state.position:
                self._close_position(price, time)
    
    def _close_position(self, price: float, time: datetime):
        """Close current position."""
        if not self.state.position:
            return
        
        pos = self.state.position
        pnl_dollars = pos.pnl(price)  # PnL in dollars
        
        # Apply commission (on leveraged position value)
        leveraged_value = pos.size * pos.leverage
        commission_cost = self.commission * leveraged_value * 2  # Entry + exit
        pnl_dollars -= commission_cost
        
        # Calculate PnL percentage (relative to capital)
        pnl_pct = (pnl_dollars / self.initial_capital) * 100
        
        trade = Trade(
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=price,
            entry_time=pos.entry_time,
            exit_time=time,
            pnl=pnl_dollars,
            pnl_pct=pnl_pct,
            fee=commission_cost,
        )
        self.state.trades.append(trade)
        self.state.equity += pnl_dollars
        
        if self._on_trade_callback:
            asyncio.create_task(self._on_trade_callback(trade))
        
        self.state.position = None
    
    def get_results(self) -> dict:
        """Get simulation results."""
        trades = self.state.trades
        
        if not trades:
            return {
                "total_trades": 0,
                "equity": self.state.equity,
                "return_pct": 0,
                "trades": [],
                "decision_log": [self._log_to_dict(l) for l in self.state.decision_log if l.decision != Decision.HOLD],
            }
        
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        
        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trades) * 100 if trades else 0,
            "total_pnl": sum(t.pnl for t in trades),
            "equity": self.state.equity,
            "return_pct": (self.state.equity - self.initial_capital) / self.initial_capital * 100,
            "avg_win": sum(t.pnl for t in wins) / len(wins) if wins else 0,
            "avg_loss": sum(t.pnl for t in losses) / len(losses) if losses else 0,
            "trades": [self._trade_to_dict(t) for t in trades],
            "equity_curve": self.state.equity_curve,
            # Return ALL non-HOLD decisions for accurate chart markers
            "decision_log": [self._log_to_dict(l) for l in self.state.decision_log if l.decision != Decision.HOLD],
        }
    
    def _trade_to_dict(self, trade: Trade) -> dict:
        return {
            "side": trade.side,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "entry_time": trade.entry_time.isoformat() if hasattr(trade.entry_time, 'isoformat') else str(trade.entry_time),
            "exit_time": trade.exit_time.isoformat() if hasattr(trade.exit_time, 'isoformat') else str(trade.exit_time),
            "pnl": trade.pnl,
            "pnl_pct": trade.pnl_pct,
        }
    
    def _log_to_dict(self, log: DecisionLog) -> dict:
        return {
            "time": log.timestamp.isoformat() if hasattr(log.timestamp, 'isoformat') else str(log.timestamp),
            "bar": log.bar_index,
            "price": log.price,
            "decision": log.decision.value,
            "reasoning": log.reasoning,
            "position": log.position,
            "unrealized_pnl": log.unrealized_pnl,
        }
