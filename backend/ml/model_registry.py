"""
Model Registry - Manage multiple trained ML models.

Stores model metadata and allows selecting models for use.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import joblib


class ModelRegistry:
    """
    Registry for managing multiple trained models.
    
    Stores metadata in models/registry.json
    """
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.registry_path = self.model_dir / "registry.json"
        self._load_registry()
    
    def _load_registry(self):
        """Load registry from disk."""
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                self.registry = json.load(f)
        else:
            self.registry = {
                "models": {},
                "active_model": None
            }
            self._save_registry()
    
    def _save_registry(self):
        """Save registry to disk."""
        with open(self.registry_path, 'w') as f:
            json.dump(self.registry, f, indent=2, default=str)
    
    def register_model(
        self,
        name: str,
        model_path: str,
        metrics: Dict,
        training_args: Dict,
        description: str = ""
    ) -> Dict:
        """
        Register a trained model.
        
        Args:
            name: Unique model name
            model_path: Path to saved .pkl file
            metrics: Training metrics (accuracy, precision, etc.)
            training_args: Arguments used for training
            description: Optional description
        
        Returns:
            Model info dict
        """
        # Generate unique ID if name exists
        original_name = name
        counter = 1
        while name in self.registry["models"]:
            name = f"{original_name}_{counter}"
            counter += 1
        
        model_info = {
            "name": name,
            "path": model_path,
            "created_at": datetime.now().isoformat(),
            "metrics": {
                "accuracy": metrics.get("accuracy", 0),
                "precision": metrics.get("precision", 0),
                "recall": metrics.get("recall", 0),
                "f1": metrics.get("f1", 0),
            },
            "training_args": {
                "symbol": training_args.get("symbol", ""),
                "timeframe": training_args.get("timeframe", ""),
                "days": training_args.get("days", 0),
                "lookahead": training_args.get("lookahead", 0),
                "threshold": training_args.get("threshold", 0),
            },
            "description": description,
            "samples": metrics.get("train_size", 0) + metrics.get("test_size", 0),
        }
        
        self.registry["models"][name] = model_info
        
        # Set as active if first model
        if self.registry["active_model"] is None:
            self.registry["active_model"] = name
        
        self._save_registry()
        return model_info
    
    def list_models(self) -> List[Dict]:
        """Get list of all registered models."""
        models = []
        for name, info in self.registry["models"].items():
            models.append({
                **info,
                "is_active": name == self.registry["active_model"]
            })
        # Sort by created_at descending
        models.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return models
    
    def get_model(self, name: str) -> Optional[Dict]:
        """Get model info by name."""
        return self.registry["models"].get(name)
    
    def get_active_model(self) -> Optional[Dict]:
        """Get currently active model."""
        active_name = self.registry["active_model"]
        if active_name and active_name in self.registry["models"]:
            return {
                **self.registry["models"][active_name],
                "is_active": True
            }
        return None
    
    def set_active_model(self, name: str) -> bool:
        """Set a model as active."""
        if name not in self.registry["models"]:
            return False
        
        self.registry["active_model"] = name
        self._save_registry()
        return True
    
    def delete_model(self, name: str) -> bool:
        """Delete a model from registry and disk."""
        if name not in self.registry["models"]:
            return False
        
        model_info = self.registry["models"][name]
        
        # Delete file
        try:
            model_path = Path(model_info["path"])
            if model_path.exists():
                model_path.unlink()
        except Exception as e:
            print(f"Warning: Could not delete model file: {e}")
        
        # Remove from registry
        del self.registry["models"][name]
        
        # Clear active if deleted
        if self.registry["active_model"] == name:
            # Set to most recent model or None
            models = self.list_models()
            self.registry["active_model"] = models[0]["name"] if models else None
        
        self._save_registry()
        return True
    
    def get_active_model_path(self) -> Optional[str]:
        """Get path to active model file."""
        active = self.get_active_model()
        if active:
            return active.get("path")
        return None


# Singleton instance
_registry = None

def get_registry() -> ModelRegistry:
    """Get singleton registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
