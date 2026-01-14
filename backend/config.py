"""
Application configuration module.
Loads settings from environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql+asyncpg://backtest:backtest@postgres:5432/backtest_db"
    
    # Redis
    redis_url: str = "redis://redis:6379"
    
    # API
    api_prefix: str = "/api"
    debug: bool = True
    
    # Binance
    binance_testnet: bool = False
    
    # Backtesting defaults
    default_commission: float = 0.001  # 0.1% for Binance Futures
    default_cash: float = 10000.0
    position_size_pct: float = 0.95  # 95% of capital per trade
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
