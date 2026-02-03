import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings."""
    
    # API
    API_TITLE: str = "HabitCity AI Backend"
    API_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Model paths - relative to backend/ directory
    MODEL_DIR: Path = Path(__file__).resolve().parent.parent / "models"
    PPO_MODEL_PATH: str = "habit_city_ppo_v5.zip"
    VECNORM_PATH: str = "habit_city_vecnorm_v5.pkl"
    
    # Inference settings
    DETERMINISTIC_INFERENCE: bool = True
    
    # Safety settings
    MAX_CONSECUTIVE_SAME_ACTION: int = 3
    DEFAULT_ACTION: int = 3  # NEUTRAL_WAIT
    
    @property
    def full_model_path(self) -> Path:
        return self.MODEL_DIR / self.PPO_MODEL_PATH
    
    @property
    def full_vecnorm_path(self) -> Path:
        return self.MODEL_DIR / self.VECNORM_PATH

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
        "protected_namespaces": (),  # Fix pydantic warning
    }

settings = Settings()
