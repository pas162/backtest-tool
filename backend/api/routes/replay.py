"""
API routes for Replay Simulator.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import pandas as pd

from backend.data.fetcher import DataService
from backend.database.connection import async_session_factory
from backend.replay.engine import ReplayEngine

# Import ML agents
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
    initial_capital: float = 100.0
    position_size: float = 20.0
    leverage: float = 1.0
    commission: float = 0.001  # 0.1% default
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
        
        # Fetch historical data with caching (PostgreSQL)
        async with async_session_factory() as db:
            service = DataService(db)
            try:
                data = await service.get_data(
                    symbol=request.symbol,
                    timeframe=request.timeframe,
                    start_time=start_dt,
                    end_time=end_dt,
                )
            finally:
                await service.close()
        
        if data.empty:
            raise HTTPException(status_code=400, detail="No data fetched")
        
        # Create ML agent
        if not HAS_ML_AGENT:
            raise HTTPException(status_code=400, detail="ML agent not available")
        
        agent = FastMLAgent()
        if not agent.is_model_loaded:
            raise HTTPException(status_code=400, detail="ML model not trained. Click '🧠 Train Model' first")
        
        # Pre-calculate ALL predictions (this is the key optimization!)
        agent.prepare(data)
        
        # Create replay engine
        engine = ReplayEngine(
            data=data,
            agent=agent,
            initial_capital=request.initial_capital,
            position_size=request.position_size,
            leverage=request.leverage,
            commission=request.commission,
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


class TrainRequest(BaseModel):
    """Request to train ML model."""
    symbol: str = "XRPUSDT"
    timeframe: str = "5m"
    days: int = 90
    lookahead: int = 5
    threshold: float = 0.002
    model_name: str = ""  # Custom model name (auto-generated if empty)


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
        from backend.ml.model_registry import get_registry
        
        trainer = ModelTrainer()
        registry = get_registry()
        
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
        
        # Generate model name if not provided
        model_name = request.model_name.strip()
        if not model_name:
            model_name = f"{request.symbol}_{request.timeframe}_{request.days}d"
        
        # Save model with unique name
        model_filename = model_name.replace(" ", "_").lower()
        model_path = trainer.save_model(model_filename)
        
        # Auto-generate description from training args and metrics
        acc_pct = metrics.get("accuracy", 0) * 100
        prec_pct = metrics.get("precision", 0) * 100
        recall_pct = metrics.get("recall", 0) * 100
        threshold_pct = request.threshold * 100
        
        description = (
            f"Trained on {request.symbol} {request.timeframe} with {request.days} days data. "
            f"Lookahead: {request.lookahead} bars, Threshold: {threshold_pct:.1f}%. "
            f"Results: Acc={acc_pct:.1f}%, Prec={prec_pct:.1f}%, Recall={recall_pct:.1f}%"
        )
        
        # Register model
        model_info = registry.register_model(
            name=model_name,
            model_path=model_path,
            metrics=metrics,
            training_args={
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "days": request.days,
                "lookahead": request.lookahead,
                "threshold": request.threshold,
            },
            description=description,
        )
        
        # Set as active model
        registry.set_active_model(model_info["name"])
        
        return {
            "success": True,
            "model_name": model_info["name"],
            "model_path": model_path,
            "metrics": metrics,
            "samples": len(X),
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """Get list of all trained models."""
    try:
        from backend.ml.model_registry import get_registry
        registry = get_registry()
        models = registry.list_models()
        active = registry.get_active_model()
        
        return {
            "success": True,
            "models": models,
            "active_model": active["name"] if active else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_name}/activate")
async def activate_model(model_name: str):
    """Set a model as the active model."""
    try:
        from backend.ml.model_registry import get_registry
        registry = get_registry()
        
        if not registry.set_active_model(model_name):
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
        
        # Reload the agent with new model
        if HAS_ML_AGENT:
            from backend.ml.fast_agent import FastMLAgent
            # Force reload of model
            agent = FastMLAgent(model_path=registry.get_active_model_path())
        
        return {
            "success": True,
            "active_model": model_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/models/{model_name}")
async def delete_model(model_name: str):
    """Delete a trained model."""
    try:
        from backend.ml.model_registry import get_registry
        registry = get_registry()
        
        if not registry.delete_model(model_name):
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
        
        return {
            "success": True,
            "message": f"Model '{model_name}' deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
