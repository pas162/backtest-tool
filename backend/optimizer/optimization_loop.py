"""
FULLY AUTONOMOUS Strategy Optimization Loop
=============================================

This script runs ENTIRELY inside Docker and:
1. Runs backtest
2. Analyzes results  
3. AUTOMATICALLY modifies strategy code based on analysis
4. Repeats until profitable or max iterations reached

Usage:
    docker exec backtest-app python -m backend.optimizer.optimization_loop
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
import json
import re

# Configuration
API_BASE = "http://localhost:8000/api"
SYMBOL = "XRPUSDT"
TIMEFRAME = "5m"
STRATEGY = "vwap_supertrend_ema_v2"
STRATEGY_FILE = "/app/backend/strategies/vwap_supertrend_ema_v2.py"

# Date range: 1 month
END_DATE = datetime.now().strftime("%Y-%m-%d")
START_DATE = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

# Goal thresholds
TARGET_RETURN = 0  # At least breakeven
TARGET_WIN_RATE = 35  # At least 35%
MAX_ITERATIONS = 10

# Backtest settings
CAPITAL = 100
LEVERAGE = 20
POSITION_SIZE = 10
COMMISSION = 0.001


def read_strategy_file():
    """Read current strategy code."""
    with open(STRATEGY_FILE, 'r') as f:
        return f.read()


def write_strategy_file(content):
    """Write modified strategy code."""
    with open(STRATEGY_FILE, 'w') as f:
        f.write(content)


def modify_parameter(code: str, param_name: str, new_value) -> str:
    """Modify a parameter value in the strategy code."""
    # Pattern: param_name = value  # comment
    pattern = rf'({param_name}\s*=\s*)(\d+\.?\d*)'
    replacement = rf'\g<1>{new_value}'
    return re.sub(pattern, replacement, code)


def get_current_params(code: str) -> dict:
    """Extract current parameter values from code."""
    params = {}
    patterns = {
        'adx_threshold': r'adx_threshold\s*=\s*(\d+)',
        'stoch_oversold': r'stoch_oversold\s*=\s*(\d+)',
        'stoch_overbought': r'stoch_overbought\s*=\s*(\d+)',
        'stop_loss_pct': r'stop_loss_pct\s*=\s*(\d+)',
        'st_multiplier': r'st_multiplier\s*=\s*(\d+\.?\d*)',
    }
    
    for name, pattern in patterns.items():
        match = re.search(pattern, code)
        if match:
            val = match.group(1)
            params[name] = float(val) if '.' in val else int(val)
    
    return params


async def run_backtest(session: aiohttp.ClientSession, params: dict) -> dict:
    """Run backtest with current params."""
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
            return None
    except Exception as e:
        print(f"Backtest failed: {e}")
        return None


def analyze_and_decide(metrics: dict, trades: list, current_params: dict) -> dict:
    """Analyze results and decide what to change."""
    changes = {}
    
    return_pct = metrics.get("return_pct", 0)
    win_rate = metrics.get("win_rate_pct", 0) or 0
    total_trades = metrics.get("total_trades", 0)
    
    # Problem: Low win rate
    if win_rate < TARGET_WIN_RATE:
        # Try increasing ADX threshold (stricter trend filter)
        current_adx = current_params.get('adx_threshold', 20)
        if current_adx < 35:
            changes['adx_threshold'] = current_adx + 5
            changes['reason_adx'] = f"Win rate {win_rate:.1f}% < {TARGET_WIN_RATE}%, increasing ADX filter"
        
        # Try tighter StochRSI
        current_oversold = current_params.get('stoch_oversold', 30)
        if current_oversold > 15:
            changes['stoch_oversold'] = max(15, current_oversold - 5)
            changes['reason_stoch'] = f"Making StochRSI oversold tighter: {current_oversold} -> {changes['stoch_oversold']}"
    
    # Problem: Too many trades (overtrading)
    if total_trades > 100:
        current_st = current_params.get('st_multiplier', 3.0)
        if current_st < 5.0:
            changes['st_multiplier'] = current_st + 0.5
            changes['reason_st'] = f"Reducing trades: increasing SuperTrend multiplier"
    
    # Problem: Too few trades
    if total_trades < 10:
        current_adx = current_params.get('adx_threshold', 20)
        if current_adx > 15:
            changes['adx_threshold'] = max(15, current_adx - 5)
            changes['reason_adx'] = f"Too few trades, relaxing ADX filter"
    
    # Problem: Big losses
    if return_pct < -20:
        current_sl = current_params.get('stop_loss_pct', 20)
        if current_sl > 10:
            changes['stop_loss_pct'] = max(10, current_sl - 5)
            changes['reason_sl'] = f"Big losses, tightening stop loss: {current_sl}% -> {changes['stop_loss_pct']}%"
    
    return changes


async def optimization_loop():
    """Main optimization loop."""
    print("=" * 70)
    print("🤖 AUTONOMOUS STRATEGY OPTIMIZATION LOOP")
    print("=" * 70)
    print(f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME}")
    print(f"Period: {START_DATE} to {END_DATE}")
    print(f"Target: Return >= {TARGET_RETURN}%, Win Rate >= {TARGET_WIN_RATE}%")
    print(f"Max Iterations: {MAX_ITERATIONS}")
    print("=" * 70)
    
    best_return = -float('inf')
    best_params = None
    history = []
    
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        
        for iteration in range(1, MAX_ITERATIONS + 1):
            print(f"\n{'='*70}")
            print(f"📊 ITERATION {iteration}/{MAX_ITERATIONS}")
            print("=" * 70)
            
            # Read current strategy code
            code = read_strategy_file()
            current_params = get_current_params(code)
            print(f"Current params: {current_params}")
            
            # Run backtest
            print("\nRunning backtest...")
            result = await run_backtest(session, {
                "ema1_length": 21,
                "ema2_length": 50,
                "st_length": 12,
                "st_multiplier": current_params.get('st_multiplier', 3.0),
                "stop_loss_pct": current_params.get('stop_loss_pct', 20),
                "take_profit_pct": 0,
            })
            
            if not result:
                print("❌ Backtest failed, retrying...")
                await asyncio.sleep(2)
                continue
            
            metrics = result.get("metrics", {})
            trades = result.get("trades", [])
            
            return_pct = metrics.get("return_pct", 0)
            win_rate = metrics.get("win_rate_pct", 0) or 0
            total_trades = metrics.get("total_trades", 0)
            
            print(f"\n📈 RESULTS:")
            print(f"  Return: {return_pct:.2f}%")
            print(f"  Win Rate: {win_rate:.1f}%")
            print(f"  Total Trades: {total_trades}")
            print(f"  Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%")
            
            # Track best
            if return_pct > best_return:
                best_return = return_pct
                best_params = current_params.copy()
                print(f"  ⭐ NEW BEST!")
            
            history.append({
                "iteration": iteration,
                "params": current_params,
                "return_pct": return_pct,
                "win_rate": win_rate,
                "trades": total_trades,
            })
            
            # Check if goal reached
            if return_pct >= TARGET_RETURN and win_rate >= TARGET_WIN_RATE:
                print(f"\n✅ GOAL REACHED!")
                print(f"  Return: {return_pct:.2f}% >= {TARGET_RETURN}%")
                print(f"  Win Rate: {win_rate:.1f}% >= {TARGET_WIN_RATE}%")
                break
            
            # Analyze and decide changes
            print(f"\n🔧 ANALYZING...")
            changes = analyze_and_decide(metrics, trades, current_params)
            
            if not changes:
                print("  No changes to make.")
                break
            
            # Apply changes to strategy code
            print(f"\n📝 MODIFYING STRATEGY:")
            for key, value in changes.items():
                if key.startswith('reason_'):
                    print(f"  → {value}")
                elif not key.startswith('reason_'):
                    code = modify_parameter(code, key, value)
                    print(f"  {key}: {current_params.get(key, '?')} → {value}")
            
            write_strategy_file(code)
            print("  ✓ Strategy file updated!")
            
            # Wait for hot reload
            await asyncio.sleep(2)
    
    # Final report
    print("\n" + "=" * 70)
    print("📊 OPTIMIZATION COMPLETE")
    print("=" * 70)
    print(f"Best Return: {best_return:.2f}%")
    print(f"Best Params: {best_params}")
    print(f"\nHistory:")
    for h in history:
        print(f"  [{h['iteration']}] Return: {h['return_pct']:.2f}%, WinRate: {h['win_rate']:.1f}%, Trades: {h['trades']}")
    
    # Save results
    output = {
        "best_return": best_return,
        "best_params": best_params,
        "history": history,
    }
    
    with open("/app/optimization_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print("\n📝 Results saved to: /app/optimization_results.json")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(optimization_loop())
