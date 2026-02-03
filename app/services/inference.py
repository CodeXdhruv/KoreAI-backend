"""
Inference Service

Orchestrates the full inference pipeline:
1. Normalize state
2. Run PPO model
3. Apply safety rules
4. Generate explanation
"""
import logging
import numpy as np
from typing import Optional

from app.models.model_loader import model_loader
from app.models.schemas import (
    ActionType, 
    UserState, 
    DecideActionResponse,
    ACTION_TO_CITY_EFFECT,
    ACTION_DISPLAY_NAMES,
)
from app.services.safety import safety_manager
from app.services.explainer import generate_explanation, get_safety_explanation
from app.config import settings

logger = logging.getLogger(__name__)


def run_inference(
    user_id: str,
    state: UserState,
    deterministic: Optional[bool] = None
) -> DecideActionResponse:
    """
    Run the full inference pipeline.
    
    Args:
        user_id: User identifier for safety tracking
        state: Current user state (5D normalized)
        deterministic: Override for deterministic mode
        
    Returns:
        DecideActionResponse with action, explanation, and city effect
    """
    use_deterministic = deterministic if deterministic is not None else settings.DETERMINISTIC_INFERENCE
    
    try:
        # Check if model is loaded
        if not model_loader.is_loaded:
            logger.warning("Model not loaded, using fallback")
            return _create_fallback_response(state)
        
        # Convert state to array
        obs = np.array(state.to_array(), dtype=np.float32)
        
        # Run model inference
        proposed_action, confidence = model_loader.predict(obs, deterministic=use_deterministic)
        logger.debug(f"Model proposed action {proposed_action} with confidence {confidence:.2f}")
        
        # Apply safety rules
        final_action, reason = safety_manager.apply_safety_rules(
            user_id, proposed_action, confidence
        )
        
        # Generate explanation
        if reason == "model_decision":
            explanation = generate_explanation(ActionType(final_action), state, reason)
        else:
            explanation = get_safety_explanation(reason)
        
        # Get city effect
        city_effect = ACTION_TO_CITY_EFFECT.get(ActionType(final_action), "idle")
        
        # Get user-facing action name
        action_name = ACTION_DISPLAY_NAMES.get(ActionType(final_action), "STEADY_PROGRESS")
        
        return DecideActionResponse(
            action=action_name,
            action_id=final_action,
            explanation=explanation,
            city_effect=city_effect,
            confidence=confidence
        )
        
    except Exception as e:
        logger.error(f"Inference error: {e}")
        return _create_fallback_response(state)


def _create_fallback_response(state: UserState) -> DecideActionResponse:
    """Create a safe fallback response when inference fails."""
    action = ActionType.NEUTRAL_WAIT
    return DecideActionResponse(
        action=ACTION_DISPLAY_NAMES[action],
        action_id=int(action),
        explanation="You're doing fine — just keep going.",
        city_effect=ACTION_TO_CITY_EFFECT[action],
        confidence=None
    )
