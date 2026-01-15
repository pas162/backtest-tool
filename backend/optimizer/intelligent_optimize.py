"""
Intelligent Strategy Optimizer
==============================

This script:
1. Runs a backtest
2. Analyzes detailed results
3. Identifies WHY the strategy is failing
4. Suggests specific code modifications
5. Can be used iteratively to improve strategy

Usage:
    python -m backend.optimizer.intelligent_optimize
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import json

# Configuration
API_BASE = "http://localhost:8000/api"
SYMBOL = "XRPUSDT"
TIMEFRAME = "5m"
STRATEGY = "vwap_supertrend_ema_v2"

# Date range: 1 month
END_DATE = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

# Current strategy parameters
CURRENT_PARAMS = {
    "ema1_length": 21,
    "ema2_length": 50,
    "st_length": 12,
    "st_multiplier": 3.0,
    "stop_loss_pct": 20,
    "take_profit_pct": 0,
}

# Backtest settings
CAPITAL = 100
LEVERAGE = 20
POSITION_SIZE = 10
COMMISSION = 0.001


async def run_backtest(session: aiohttp.ClientSession, params: dict) -> dict:
    """Run a single backtest."""
    payload = {
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "strategy": STRATEGY,
        "params": params,
        "initial_capital": CAPITAL,
        "leverage": LEVERAGE,
        "position_size": POSITION_SIZE,
        "commission": COMMISSION,
    }
    
    try:
        async with session.post(f"{API_BASE}/backtest/run", json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                text = await response.text()
                print(f"Error: {response.status} - {text[:200]}")
                return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None


def analyze_trades(trades: list) -> dict:
    """Deep analysis of trade performance."""
    if not trades:
        return {"error": "No trades"}
    
    # Separate by direction
    long_trades = [t for t in trades if t.get("side") == "long"]
    short_trades = [t for t in trades if t.get("side") == "short"]
    
    # Calculate stats
    def calc_stats(trade_list, name):
        if not trade_list:
            return {"name": name, "count": 0}
        
        wins = [t for t in trade_list if t.get("pnl", 0) > 0]
        losses = [t for t in trade_list if t.get("pnl", 0) < 0]
        
        total_pnl = sum(t.get("pnl", 0) for t in trade_list)
        avg_win = sum(t.get("pnl", 0) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get("pnl", 0) for t in losses) / len(losses) if losses else 0
        win_rate = len(wins) / len(trade_list) * 100 if trade_list else 0
        
        return {
            "name": name,
            "count": len(trade_list),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": abs(avg_win * len(wins) / (avg_loss * len(losses))) if losses and avg_loss != 0 else 0,
        }
    
    long_stats = calc_stats(long_trades, "LONG")
    short_stats = calc_stats(short_trades, "SHORT")
    all_stats = calc_stats(trades, "ALL")
    
    return {
        "total": all_stats,
        "long": long_stats,
        "short": short_stats,
    }


def identify_problems(analysis: dict, metrics: dict) -> list:
    """Identify specific problems with the strategy."""
    problems = []
    
    total = analysis.get("total", {})
    long = analysis.get("long", {})
    short = analysis.get("short", {})
    
    # Problem 1: Overall losing
    if total.get("total_pnl", 0) < 0:
        problems.append({
            "type": "OVERALL_LOSS",
            "severity": "HIGH",
            "description": f"Strategy is losing money: ${total.get('total_pnl', 0):.2f}",
        })
    
    # Problem 2: Low win rate
    if total.get("win_rate", 0) < 40:
        problems.append({
            "type": "LOW_WIN_RATE",
            "severity": "HIGH",
            "description": f"Win rate is only {total.get('win_rate', 0):.1f}% (should be >40%)",
        })
    
    # Problem 3: Avg loss > Avg win
    if abs(total.get("avg_loss", 0)) > total.get("avg_win", 0):
        problems.append({
            "type": "BAD_RR_RATIO",
            "severity": "MEDIUM",
            "description": f"Avg loss (${abs(total.get('avg_loss', 0)):.2f}) > Avg win (${total.get('avg_win', 0):.2f})",
        })
    
    # Problem 4: One direction is much worse
    long_pnl = long.get("total_pnl", 0)
    short_pnl = short.get("total_pnl", 0)
    
    if long.get("count", 0) > 5 and short.get("count", 0) > 5:
        if long_pnl < 0 and short_pnl > 0:
            problems.append({
                "type": "LONG_FAILING",
                "severity": "HIGH",
                "description": f"LONG losing ${abs(long_pnl):.2f} but SHORT winning ${short_pnl:.2f}",
                "suggestion": "Consider disabling LONG trades or adding stricter LONG entry conditions",
            })
        elif short_pnl < 0 and long_pnl > 0:
            problems.append({
                "type": "SHORT_FAILING",
                "severity": "HIGH",
                "description": f"SHORT losing ${abs(short_pnl):.2f} but LONG winning ${long_pnl:.2f}",
                "suggestion": "Consider disabling SHORT trades or adding stricter SHORT entry conditions",
            })
    
    # Problem 5: Both directions losing
    if long_pnl < 0 and short_pnl < 0:
        if long.get("win_rate", 0) > short.get("win_rate", 0):
            problems.append({
                "type": "BOTH_LOSING_LONG_BETTER",
                "severity": "HIGH",
                "description": f"Both losing. LONG win rate ({long.get('win_rate', 0):.1f}%) > SHORT ({short.get('win_rate', 0):.1f}%)",
                "suggestion": "Focus on LONG only, or tighten SHORT entry conditions",
            })
        else:
            problems.append({
                "type": "BOTH_LOSING_SHORT_BETTER",
                "severity": "HIGH",
                "description": f"Both losing. SHORT win rate ({short.get('win_rate', 0):.1f}%) > LONG ({long.get('win_rate', 0):.1f}%)",
                "suggestion": "Focus on SHORT only, or tighten LONG entry conditions",
            })
    
    # Problem 6: Too many trades (overtrading)
    if total.get("count", 0) > 200:
        problems.append({
            "type": "OVERTRADING",
            "severity": "MEDIUM",
            "description": f"Too many trades ({total.get('count', 0)}) in 1 month",
            "suggestion": "Add stricter filters (higher ADX threshold, cooldown period)",
        })
    
    # Problem 7: Too few trades
    if total.get("count", 0) < 10:
        problems.append({
            "type": "UNDERTRADING",
            "severity": "MEDIUM",
            "description": f"Too few trades ({total.get('count', 0)}) in 1 month",
            "suggestion": "Relax entry conditions",
        })
    
    return problems


def suggest_modifications(problems: list, current_params: dict) -> list:
    """Suggest specific code/parameter modifications based on problems."""
    suggestions = []
    
    for problem in problems:
        ptype = problem.get("type")
        
        if ptype == "LOW_WIN_RATE":
            suggestions.append({
                "action": "INCREASE_ADX_THRESHOLD",
                "reason": "Low win rate - only trade in stronger trends",
                "change": "Increase adx_threshold from current value to +5",
            })
            suggestions.append({
                "action": "TIGHTER_STOCHRSI",
                "reason": "Low win rate - wait for more extreme conditions",
                "change": "Change stoch_oversold from 30 to 20, stoch_overbought from 70 to 80",
            })
        
        elif ptype == "BAD_RR_RATIO":
            suggestions.append({
                "action": "TIGHTER_SL",
                "reason": "Losses are too big - cut losers faster",
                "change": f"Reduce stop_loss_pct from {current_params.get('stop_loss_pct', 20)} to {max(5, current_params.get('stop_loss_pct', 20) - 5)}",
            })
        
        elif ptype == "LONG_FAILING":
            suggestions.append({
                "action": "DISABLE_LONG_OR_STRICTER",
                "reason": "LONG trades consistently losing",
                "change": "Add EMA trend filter: only LONG when EMA1 > EMA2",
            })
        
        elif ptype == "SHORT_FAILING":
            suggestions.append({
                "action": "DISABLE_SHORT_OR_STRICTER",
                "reason": "SHORT trades consistently losing", 
                "change": "Add EMA trend filter: only SHORT when EMA1 < EMA2",
            })
        
        elif ptype == "OVERTRADING":
            suggestions.append({
                "action": "ADD_COOLDOWN",
                "reason": "Too many trades - add cooldown between trades",
                "change": "Add 5-10 bar cooldown after each trade",
            })
            suggestions.append({
                "action": "INCREASE_ST_MULTIPLIER",
                "reason": "Too many trades - reduce signal frequency",
                "change": f"Increase st_multiplier from {current_params.get('st_multiplier', 3.0)} to {current_params.get('st_multiplier', 3.0) + 1.0}",
            })
        
        elif ptype in ["BOTH_LOSING_LONG_BETTER", "BOTH_LOSING_SHORT_BETTER"]:
            suggestions.append({
                "action": "SINGLE_DIRECTION",
                "reason": problem.get("suggestion"),
                "change": "Modify strategy to trade only in the better direction",
            })
    
    return suggestions


async def run_optimization_cycle():
    """Run one optimization cycle: backtest -> analyze -> suggest."""
    print("=" * 70)
    print("🧠 INTELLIGENT STRATEGY OPTIMIZER")
    print("=" * 70)
    print(f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME}")
    print(f"Period: {START_DATE} to {END_DATE}")
    print(f"Strategy: {STRATEGY}")
    print(f"Current Params: {CURRENT_PARAMS}")
    print("=" * 70)
    
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        print("\n📊 Running backtest...")
        result = await run_backtest(session, CURRENT_PARAMS)
        
        if not result:
            print("❌ Backtest failed!")
            return
        
        metrics = result.get("metrics", {})
        trades = result.get("trades", [])
        
        print("\n📈 METRICS:")
        print(f"  Return: {metrics.get('return_pct', 0):.2f}%")
        print(f"  Win Rate: {metrics.get('win_rate_pct', 0):.1f}%")
        print(f"  Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
        print(f"  Total Trades: {metrics.get('total_trades', 0)}")
        print(f"  Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        
        print("\n🔍 ANALYZING TRADES...")
        analysis = analyze_trades(trades)
        
        print("\n📊 TRADE BREAKDOWN:")
        for key in ["long", "short"]:
            stats = analysis.get(key, {})
            if stats.get("count", 0) > 0:
                print(f"\n  {stats['name']}:")
                print(f"    Count: {stats['count']} | Wins: {stats['wins']} | Losses: {stats['losses']}")
                print(f"    Win Rate: {stats['win_rate']:.1f}%")
                print(f"    Total PnL: ${stats['total_pnl']:.2f}")
                print(f"    Avg Win: ${stats['avg_win']:.2f} | Avg Loss: ${stats['avg_loss']:.2f}")
        
        print("\n⚠️  IDENTIFIED PROBLEMS:")
        problems = identify_problems(analysis, metrics)
        
        if not problems:
            print("  ✅ No major problems found! Strategy may be profitable.")
        else:
            for i, prob in enumerate(problems, 1):
                print(f"\n  [{i}] {prob['type']} ({prob['severity']})")
                print(f"      {prob['description']}")
                if prob.get("suggestion"):
                    print(f"      💡 {prob['suggestion']}")
        
        print("\n🔧 SUGGESTED MODIFICATIONS:")
        suggestions = suggest_modifications(problems, CURRENT_PARAMS)
        
        if not suggestions:
            print("  No modifications needed!")
        else:
            for i, sug in enumerate(suggestions, 1):
                print(f"\n  [{i}] {sug['action']}")
                print(f"      Reason: {sug['reason']}")
                print(f"      Change: {sug['change']}")
        
        # Save analysis
        output = {
            "timestamp": datetime.now().isoformat(),
            "params": CURRENT_PARAMS,
            "metrics": metrics,
            "analysis": analysis,
            "problems": problems,
            "suggestions": suggestions,
        }
        
        with open("optimization_analysis.json", "w") as f:
            json.dump(output, f, indent=2, default=str)
        
        print("\n" + "=" * 70)
        print("📝 Analysis saved to: optimization_analysis.json")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_optimization_cycle())
