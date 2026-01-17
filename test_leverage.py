
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from backend.replay.engine import ReplayEngine, Decision

class MockAgent:
    def __init__(self):
        self.step = 0
    
    def analyze(self, data, order_flow):
        self.step += 1
        # Buy on bar 2, Close on bar 5
        if self.step == 2:
            return Decision.BUY
        elif self.step == 5:
            return Decision.CLOSE
        return Decision.HOLD
    
    def get_reasoning(self):
        return "Mock Reasoning"

async def test_leverage(size):
    # create dummy data
    dates = [datetime(2025, 1, 1) + timedelta(minutes=i*5) for i in range(10)]
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
    # Price moves 1 per bar. 
    # Buy at bar 2 (Price 102 - wait Engine uses visible data. 
    # On bar 2 (index 2), current is price[2]=102.
    # Close at bar 5 (index 5), current is price[5]=105.
    # Diff = 3. Entry 102.
    # PnL = (3/102) * 100 * size.
    
    df = pd.DataFrame({
        'Open': prices,
        'High': prices,
        'Low': prices,
        'Close': prices,
        'Volume': [1000]*10
    }, index=dates)
    
    agent = MockAgent()
    engine = ReplayEngine(
        data=df,
        agent=agent,
        initial_capital=100.0,
        position_size=float(size),
        commission=0.0 # disable fee for clear math
    )
    
    results = await engine.run(speed=0)
    
    trades = results['trades']
    if not trades:
        print(f"Size {size}: No trades!")
        return 0
    
    pnl = trades[0]['pnl']
    print(f"Size {size}: PnL = {pnl:.2f}, Return% = {trades[0]['pnl_pct']:.2f}%")
    return pnl

async def main():
    print("Testing Leverage Logic...")
    pnl_20 = await test_leverage(20)
    pnl_100 = await test_leverage(100)
    
    if abs(pnl_100 - pnl_20 * 5) < 0.1: # 100 is 5x of 20
        print("SUCCESS: Leverage is working (PnL scales linearly).")
    elif pnl_100 == pnl_20:
        print("FAILURE: PnL is identical! Logic is broken.")
    else:
        print(f"FAILURE: Scaling incorrect. 20x={pnl_20}, 100x={pnl_100}")

if __name__ == "__main__":
    asyncio.run(main())
