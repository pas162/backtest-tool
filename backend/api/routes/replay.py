"""
API routes for Replay Simulator.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import pandas as pd

from backend.data.fetcher import BinanceFetcher
from backend.replay.engine import ReplayEngine
from backend.replay.agent import SimpleOrderFlowAgent, MomentumAgent

# Try to import ML agents
try:
    from backend.ml.agent import MLTradingAgent
    from backend.ml.fast_agent import FastMLAgent
    HAS_ML_AGENT = True
except ImportError:
    HAS_ML_AGENT = False


router = APIRouter(prefix="/replay", tags=["replay"])


class ReplayRequest(BaseModel):
    """Request to run replay simulation."""
    symbol: str = "XRPUSDT"
    timeframe: str = "5m"
    start_date: str
    end_date: str
    agent_type: str = "orderflow"  # "orderflow" or "momentum"
    initial_capital: float = 100.0
    position_size: float = 20.0
    speed: float = 0  # 0 = instant, > 0 = bars per second


class ReplayResponse(BaseModel):
    """Response from replay simulation."""
    success: bool
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    return_pct: float
    equity: float
    trades: list
    decision_log: list
    equity_curve: list
    candles: list = []  # OHLCV candles for chart


@router.post("/run", response_model=ReplayResponse)
async def run_replay(request: ReplayRequest):
    """
    Run replay simulation on historical data.
    
    The agent will process data bar-by-bar, only seeing
    historical data up to the current bar (no look-ahead).
    """
    try:
        # Parse dates
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        # Fetch historical data
        fetcher = BinanceFetcher()
        try:
            ohlcv_data = await fetcher.fetch_ohlcv(
                symbol=request.symbol,
                timeframe=request.timeframe,
                start_time=start_dt,
                end_time=end_dt,
            )
        finally:
            await fetcher.close()
        
        if not ohlcv_data:
            raise HTTPException(status_code=400, detail="No data fetched")
        
        # Convert to DataFrame
        data = pd.DataFrame(ohlcv_data)
        data['timestamp'] = pd.to_datetime(data['timestamp'])
        data = data.set_index('timestamp')
        data = data.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        
        # Create agent
        if request.agent_type == "orderflow":
            agent = SimpleOrderFlowAgent()
        elif request.agent_type == "momentum":
            agent = MomentumAgent()
        elif request.agent_type == "ml":
            if not HAS_ML_AGENT:
                raise HTTPException(status_code=400, detail="ML agent not available")
            # Use FastMLAgent for instant replay
            agent = FastMLAgent()
            if not agent.is_model_loaded:
                raise HTTPException(status_code=400, detail="ML model not trained. Run /api/replay/train first")
            # Pre-calculate ALL predictions (this is the key optimization!)
            agent.prepare(data)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown agent: {request.agent_type}")
        
        # Create replay engine
        engine = ReplayEngine(
            data=data,
            agent=agent,
            initial_capital=request.initial_capital,
            position_size=request.position_size,
        )
        
        # Run simulation
        print(f"Starting Replay with Position Size (Leverage): {request.position_size}x")
        results = await engine.run(speed=request.speed)
        
        # Format candles for Lightweight Charts (time as Unix timestamp)
        candles_for_chart = []
        for idx, row in data.iterrows():
            candles_for_chart.append({
                "time": int(idx.timestamp()),  # Unix timestamp
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
            })
        
        return ReplayResponse(
            success=True,
            total_trades=results.get("total_trades", 0),
            wins=results.get("wins", 0),
            losses=results.get("losses", 0),
            win_rate=results.get("win_rate", 0),
            return_pct=results.get("return_pct", 0),
            equity=results.get("equity", request.initial_capital),
            trades=results.get("trades", []),
            decision_log=results.get("decision_log", []),
            equity_curve=results.get("equity_curve", []),
            candles=candles_for_chart,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_agents():
    """List available trading agents."""
    agents = [
        {
            "id": "orderflow",
            "name": "Order Flow Agent",
            "description": "Uses volume delta and CVD for decisions",
        },
        {
            "id": "momentum",
            "name": "Momentum Agent", 
            "description": "Uses price momentum for decisions",
        },
    ]
    
    if HAS_ML_AGENT:
        agents.append({
            "id": "ml",
            "name": "ML Agent (XGBoost)",
            "description": "Machine learning model trained on historical data",
        })
    
    return {"agents": agents}


class TrainRequest(BaseModel):
    """Request to train ML model."""
    symbol: str = "XRPUSDT"
    timeframe: str = "5m"
    days: int = 90
    lookahead: int = 5
    threshold: float = 0.002


@router.post("/train")
async def train_ml_model(request: TrainRequest):
    """
    Train ML model on historical data.
    
    This may take a few minutes.
    """
    if not HAS_ML_AGENT:
        raise HTTPException(status_code=400, detail="ML module not available")
    
    try:
        from backend.ml.trainer import ModelTrainer
        
        trainer = ModelTrainer()
        
        # Prepare data
        X, y = await trainer.prepare_data(
            symbol=request.symbol,
            timeframe=request.timeframe,
            days=request.days,
            lookahead=request.lookahead,
            threshold=request.threshold,
        )
        
        # Train model
        metrics = trainer.train(X, y)
        
        # Save model
        model_path = trainer.save_model("trading_model")
        
        return {
            "success": True,
            "model_path": model_path,
            "metrics": metrics,
            "samples": len(X),
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
