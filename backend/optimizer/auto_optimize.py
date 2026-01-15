"""
Automated Strategy Optimizer
=============================

This script automatically:
1. Tests different parameter combinations
2. Analyzes results
3. Identifies best performing parameters
4. Updates strategy with optimal settings

Usage:
    python -m backend.optimizer.auto_optimize
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from itertools import product
import json

# Configuration
API_BASE = "http://localhost:8000/api"
SYMBOL = "XRPUSDT"
TIMEFRAME = "5m"
STRATEGY = "vwap_supertrend_ema_v2"

# Date range: 1 month ago to now
END_DATE = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

# Parameter grid to search
PARAM_GRID = {
    "ema1_length": [14, 21, 34],
    "ema2_length": [50, 100],
    "st_length": [10, 12, 14],
    "st_multiplier": [2.0, 3.0, 4.0],
    "stop_loss_pct": [10, 15, 20],
    "take_profit_pct": [0, 20, 40],
}

# Backtest settings
CAPITAL = 100
LEVERAGE = 20
POSITION_SIZE = 10
COMMISSION = 0.001


async def run_backtest(session: aiohttp.ClientSession, params: dict) -> dict:
    """Run a single backtest with given parameters."""
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
                print(f"Error: {response.status} - {text[:100]}")
                return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None


def calculate_score(metrics: dict) -> float:
    """
    Calculate a composite score for strategy performance.
    Higher is better.
    """
    if not metrics or metrics.get("total_trades", 0) < 5:
        return -1000  # Not enough trades
    
    return_pct = metrics.get("return_pct", 0)
    win_rate = metrics.get("win_rate_pct", 0) or 0
    max_dd = abs(metrics.get("max_drawdown_pct", 0) or 0)
    profit_factor = metrics.get("profit_factor", 0) or 0
    total_trades = metrics.get("total_trades", 0)
    
    # Composite score:
    # - Prioritize return
    # - Reward high win rate
    # - Penalize high drawdown
    # - Bonus for good profit factor
    # - Minimum trades requirement met
    
    score = (
        return_pct * 2 +  # Return is most important
        win_rate * 0.5 +  # Win rate matters
        profit_factor * 10 +  # Profit factor bonus
        - max_dd * 0.5  # Penalize drawdown
    )
    
    return score


async def optimize():
    """Run optimization grid search."""
    print("=" * 60)
    print("🚀 AUTOMATED STRATEGY OPTIMIZER")
    print("=" * 60)
    print(f"Symbol: {SYMBOL}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Period: {START_DATE} to {END_DATE}")
    print(f"Strategy: {STRATEGY}")
    print("=" * 60)
    
    # Generate all parameter combinations
    param_names = list(PARAM_GRID.keys())
    param_values = list(PARAM_GRID.values())
    combinations = list(product(*param_values))
    
    print(f"Testing {len(combinations)} parameter combinations...")
    print()
    
    results = []
    best_score = -float("inf")
    best_params = None
    best_metrics = None
    
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))
            
            print(f"[{i+1}/{len(combinations)}] Testing: {params}")
            
            result = await run_backtest(session, params)
            
            if result and "metrics" in result:
                metrics = result["metrics"]
                score = calculate_score(metrics)
                
                results.append({
                    "params": params,
                    "metrics": metrics,
                    "score": score
                })
                
                trades = metrics.get("total_trades", 0)
                ret = metrics.get("return_pct", 0)
                win_rate = metrics.get("win_rate_pct", 0) or 0
                
                print(f"  → Trades: {trades}, Return: {ret:.2f}%, Win Rate: {win_rate:.1f}%, Score: {score:.2f}")
                
                if score > best_score:
                    best_score = score
                    best_params = params
                    best_metrics = metrics
                    print(f"  ⭐ NEW BEST!")
            else:
                print(f"  → Failed")
            
            # Small delay to avoid overwhelming the server
            await asyncio.sleep(0.5)
    
    # Final report
    print()
    print("=" * 60)
    print("📊 OPTIMIZATION COMPLETE")
    print("=" * 60)
    
    if best_params:
        print(f"Best Score: {best_score:.2f}")
        print()
        print("Best Parameters:")
        for k, v in best_params.items():
            print(f"  {k}: {v}")
        print()
        print("Best Metrics:")
        print(f"  Return: {best_metrics.get('return_pct', 0):.2f}%")
        print(f"  Win Rate: {best_metrics.get('win_rate_pct', 0):.1f}%")
        print(f"  Max Drawdown: {best_metrics.get('max_drawdown_pct', 0):.2f}%")
        print(f"  Total Trades: {best_metrics.get('total_trades', 0)}")
        print(f"  Profit Factor: {best_metrics.get('profit_factor', 0):.2f}")
        
        # Save results
        output = {
            "best_params": best_params,
            "best_metrics": best_metrics,
            "best_score": best_score,
            "all_results": sorted(results, key=lambda x: x["score"], reverse=True)[:10]
        }
        
        with open("optimization_results.json", "w") as f:
            json.dump(output, f, indent=2, default=str)
        
        print()
        print("Results saved to: optimization_results.json")
    else:
        print("No successful results found!")
    
    print("=" * 60)
    
    return best_params, best_metrics


if __name__ == "__main__":
    asyncio.run(optimize())
