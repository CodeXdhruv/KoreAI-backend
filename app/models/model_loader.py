"""
PPO Model Loader Singleton

Loads the trained PPO model and VecNormalize stats once at startup.
Provides thread-safe access for inference.
"""
import logging
from pathlib import Path
from threading import Lock
from typing import Optional

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
import gymnasium as gym
from gymnasium import spaces

logger = logging.getLogger(__name__)


class HabitCityEnv(gym.Env):
    """
    Minimal Gymnasium environment for VecNormalize compatibility.
    Only used for loading the normalizer, not for training.
    """
    
    def __init__(self):
        super().__init__()
        # 5D observation: consistency, momentum, energy, failure_rate, fatigue
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(5,), dtype=np.float32
        )
        # 4 discrete actions
        self.action_space = spaces.Discrete(4)
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        return np.zeros(5, dtype=np.float32), {}
    
    def step(self, action):
        return np.zeros(5, dtype=np.float32), 0.0, False, False, {}


class ModelLoader:
    """
    Singleton class for loading and managing the PPO model.
    Thread-safe for concurrent inference requests.
    """
    
    _instance: Optional["ModelLoader"] = None
    _lock: Lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.model: Optional[PPO] = None
        self.vec_normalize: Optional[VecNormalize] = None
        self._model_loaded: bool = False
        self._inference_lock: Lock = Lock()
        self._initialized = True
    
    def load(self, model_path: Path, vecnorm_path: Path) -> bool:
        """
        Load the PPO model and VecNormalize stats.
        
        Args:
            model_path: Path to the .zip model file
            vecnorm_path: Path to the .pkl VecNormalize file
            
        Returns:
            True if loading succeeded, False otherwise
        """
        try:
            logger.info(f"Loading PPO model from {model_path}")
            
            # Load the PPO model (CPU only for free-tier compatibility)
            self.model = PPO.load(str(model_path), device="cpu")
            
            # Create dummy env for VecNormalize
            dummy_env = DummyVecEnv([lambda: HabitCityEnv()])
            
            # Load VecNormalize with the trained stats
            logger.info(f"Loading VecNormalize from {vecnorm_path}")
            self.vec_normalize = VecNormalize.load(str(vecnorm_path), dummy_env)
            
            # Set to evaluation mode (no stats updates)
            self.vec_normalize.training = False
            self.vec_normalize.norm_reward = False
            
            self._model_loaded = True
            logger.info("Model and normalizer loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self._model_loaded = False
            return False
    
    def predict(self, observation: np.ndarray, deterministic: bool = True) -> tuple[int, float]:
        """
        Run inference on the loaded model.
        
        Args:
            observation: 5D state vector (normalized 0-1)
            deterministic: If True, use deterministic policy
            
        Returns:
            Tuple of (action_id, confidence)
        """
        if not self._model_loaded or self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        with self._inference_lock:
            # Reshape for batch inference
            obs = np.array(observation, dtype=np.float32).reshape(1, -1)
            
            # Normalize observation using trained stats
            if self.vec_normalize is not None:
                obs = self.vec_normalize.normalize_obs(obs)
            
            # Get action and value
            action, _states = self.model.predict(obs, deterministic=deterministic)
            
            # Get action probabilities for confidence
            obs_tensor = self.model.policy.obs_to_tensor(obs)[0]
            distribution = self.model.policy.get_distribution(obs_tensor)
            action_probs = distribution.distribution.probs.detach().cpu().numpy()[0]
            confidence = float(action_probs[int(action[0])])
            
            return int(action[0]), confidence
    
    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model_loaded


# Global singleton instance
model_loader = ModelLoader()
