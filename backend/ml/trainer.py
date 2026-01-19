"""
Model Training Pipeline for ML Trading Agent.

Trains XGBoost or RandomForest classifier on historical data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import joblib
from typing import Optional, Tuple
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

from backend.ml.features import FeatureEngineer
from backend.data.fetcher import BinanceFetcher


class ModelTrainer:
    """
    Trains ML models for trading predictions.
    
    Supports:
    - XGBoost (if installed)
    - RandomForest (fallback)
    """
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.feature_engineer = FeatureEngineer()
        self.model = None
        self.model_type = None
    
    async def prepare_data(
        self,
        symbol: str = "XRPUSDT",
        timeframe: str = "5m",
        days: int = 90,
        lookahead: int = 10,
        threshold: float = 0.002,
        use_multi_class: bool = True,  # NEW: Use multi-class labels
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Fetch and prepare training data.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            days: Days of historical data
            lookahead: Bars to look ahead for labels
            threshold: Min price change threshold (for binary labels)
            use_multi_class: If True, use 3-class labels (HOLD/LONG/SHORT)
        
        Returns:
            Tuple of (features DataFrame, labels Series)
        """
        print(f"Fetching {days} days of {symbol} {timeframe} data...")
        
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days)
        
        fetcher = BinanceFetcher()
        try:
            ohlcv = await fetcher.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                start_time=start_dt,
                end_time=end_dt,
            )
        finally:
            await fetcher.close()
        
        if not ohlcv:
            raise ValueError("No data fetched")
        
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        df.columns = [c.capitalize() for c in df.columns]
        
        print(f"Fetched {len(df)} candles")
        
        # Create features
        print("Creating features...")
        features = self.feature_engineer.create_features(df)
        
        # Create labels
        print("Creating labels...")
        if use_multi_class:
            labels = self.feature_engineer.create_multi_class_labels(
                df,
                lookahead=lookahead
            )
            print(f"Using MULTI-CLASS labels (0=HOLD, 1=LONG, 2=SHORT)")
        else:
            labels = self.feature_engineer.create_labels(
                df,
                lookahead=lookahead,
                threshold=threshold
            )
            print(f"Using BINARY labels (0=DOWN, 1=UP)")
        
        # Remove rows without valid labels (last lookahead rows)
        valid_mask = labels.notna()
        features = features[valid_mask]
        labels = labels[valid_mask]
        
        print(f"Prepared {len(features)} samples")
        
        if use_multi_class:
            # Show distribution for multi-class
            label_counts = labels.value_counts().sort_index()
            print(f"Label distribution:")
            print(f"  HOLD (0):  {label_counts.get(0, 0)} ({label_counts.get(0, 0)/len(labels)*100:.1f}%)")
            print(f"  LONG (1):  {label_counts.get(1, 0)} ({label_counts.get(1, 0)/len(labels)*100:.1f}%)")
            print(f"  SHORT (2): {label_counts.get(2, 0)} ({label_counts.get(2, 0)/len(labels)*100:.1f}%)")
        else:
            # Show distribution for binary
            print(f"Label distribution: Up={labels.sum()} ({labels.mean()*100:.1f}%), Down={len(labels)-labels.sum()}")
        
        return features, labels
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_type: str = "auto",
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> dict:
        """
        Train the ML model.
        
        Args:
            X: Feature DataFrame
            y: Label Series
            model_type: "xgboost", "randomforest", or "auto"
            test_size: Fraction for test set
            random_state: Random seed
        
        Returns:
            Dict with metrics
        """
        print(f"\nTraining model (type={model_type})...")
        
        # Check if labels are multi-class (0, 1, 2) or binary (0, 1)
        num_classes = len(y.unique())
        is_multi_class = num_classes > 2
        
        print(f"Number of classes: {num_classes}")
        print(f"Classification type: {'MULTI-CLASS' if is_multi_class else 'BINARY'}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, shuffle=False
        )
        
        print(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
       
        # Select model
        if model_type == "auto":
            model_type = "xgboost" if HAS_XGBOOST else "randomforest"
        
        if model_type == "xgboost" and HAS_XGBOOST:
            if is_multi_class:
                self.model = xgb.XGBClassifier(
                    objective='multi:softmax',
                    num_class=num_classes,
                    n_estimators=150,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=random_state,
                    eval_metric='mlogloss',
                )
            else:
                self.model = xgb.XGBClassifier(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    random_state=random_state,
                    eval_metric='logloss',
                )
            self.model_type = "xgboost"
        else:
            self.model = RandomForestClassifier(
                n_estimators=150,
                max_depth=12,
                random_state=random_state,
                n_jobs=-1,
                class_weight='balanced',  # Handle class imbalance
            )
            self.model_type = "randomforest"
        
        print(f"Using {self.model_type}...")
        
        # Train
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        y_prob = self.model.predict_proba(X_test)
        
        metrics = {
            "model_type": self.model_type,
            "num_classes": num_classes,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "accuracy": accuracy_score(y_test, y_pred),
        }
        
        # Calculate precision/recall/f1
        if is_multi_class:
            metrics["precision"] = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            metrics["recall"] = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            metrics["f1"] = f1_score(y_test, y_pred, average='weighted', zero_division=0)
        else:
            metrics["precision"] = precision_score(y_test, y_pred, zero_division=0)
            metrics["recall"] = recall_score(y_test, y_pred, zero_division=0)
            metrics["f1"] = f1_score(y_test, y_pred, zero_division=0)
        
        print(f"\n📊 Results:")
        print(f"  Accuracy:  {metrics['accuracy']:.4f}")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall:    {metrics['recall']:.4f}")
        print(f"  F1 Score:  {metrics['f1']:.4f}")
        
        # Show per-class metrics for multi-class
        if is_multi_class:
            print(f"\n📈 Per-Class Metrics:")
            class_names = ['HOLD', 'LONG', 'SHORT'] if num_classes == 3 else [f'Class_{i}' for i in range(num_classes)]
            print(classification_report(y_test, y_pred, target_names=class_names, zero_division=0))
        
        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            importance = pd.Series(
                self.model.feature_importances_,
                index=X.columns
            ).sort_values(ascending=False)
            
            print(f"\n🔝 Top 10 Features:")
            for feat, imp in importance.head(10).items():
                print(f"  {feat}: {imp:.4f}")
            
            metrics["feature_importance"] = importance.to_dict()
        
        return metrics
    
    def save_model(self, name: str = "trading_model") -> str:
        """Save trained model to disk."""
        if self.model is None:
            raise ValueError("No model trained yet")
        
        path = self.model_dir / f"{name}.pkl"
        joblib.dump({
            "model": self.model,
            "model_type": self.model_type,
            "feature_names": self.feature_engineer.get_feature_names(),
        }, path)
        
        print(f"✅ Model saved to: {path}")
        return str(path)
    
    def load_model(self, path: str) -> None:
        """Load model from disk."""
        data = joblib.load(path)
        self.model = data["model"]
        self.model_type = data["model_type"]
        self.feature_engineer.feature_names = data["feature_names"]
        
        print(f"✅ Model loaded from: {path}")


async def train_model_cli():
    """CLI for training model."""
    trainer = ModelTrainer()
    
    # Prepare data with MULTI-CLASS labels
    X, y = await trainer.prepare_data(
        symbol="XRPUSDT",
        timeframe="5m",
        days=90,
        lookahead=10,          # Look ahead 10 bars (~50 minutes for 5m)
        use_multi_class=True,  # Use 3-class labels
    )
    
    # Train
    metrics = trainer.train(X, y)
    
    # Save
    trainer.save_model("xrp_5m_model_multiclass")
    
    return metrics


if __name__ == "__main__":
    import asyncio
    asyncio.run(train_model_cli())
