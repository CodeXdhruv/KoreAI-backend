"""
Rule-Based Explanation Generator

Generates friendly, human-readable explanations for AI decisions.
Uses templates - no ML internals exposed to users.
"""
from app.models.schemas import ActionType, UserState


# Explanation templates for each action
EXPLANATIONS = {
    ActionType.SOFT_PENALTY: [
        "Let's take a breath and reset gently.",
        "A fresh start might help today.",
        "No worries — just a gentle reset.",
    ],
    ActionType.LOWER_GOAL: [
        "Let's make today a bit easier.",
        "A lighter goal might feel better right now.",
        "Taking it easy today is okay.",
    ],
    ActionType.COMPENSATE_REWARD: [
        "You've been consistent — enjoy a small boost!",
        "Great momentum! Here's something nice.",
        "You earned this — keep it up!",
    ],
    ActionType.NEUTRAL_WAIT: [
        "You're doing fine — just keep going.",
        "Steady progress is the goal.",
        "Nothing to change — you're on track.",
    ],
}

# Context-aware modifiers based on state
STATE_MODIFIERS = {
    "high_fatigue": "Remember to rest when you need to.",
    "low_energy": "Take care of yourself today.",
    "high_momentum": "Your streak is looking great!",
    "recovering": "Coming back strong — that's what matters.",
}


def generate_explanation(
    action: ActionType, 
    state: UserState,
    reason: str = "model_decision"
) -> str:
    """
    Generate a friendly explanation for the action.
    
    Args:
        action: The chosen action
        state: Current user state
        reason: Why this action was chosen
        
    Returns:
        Human-readable explanation string
    """
    # Get base explanation
    templates = EXPLANATIONS.get(action, EXPLANATIONS[ActionType.NEUTRAL_WAIT])
    
    # Select template based on state for variety
    # Use a simple hash of state values to pick consistently
    state_hash = int((state.consistency + state.momentum + state.energy) * 100) % len(templates)
    base_explanation = templates[state_hash]
    
    # Add context-aware modifier if applicable
    modifier = ""
    if state.fatigue > 0.7:
        modifier = f" {STATE_MODIFIERS['high_fatigue']}"
    elif state.energy < 0.3:
        modifier = f" {STATE_MODIFIERS['low_energy']}"
    elif state.momentum > 0.8:
        modifier = f" {STATE_MODIFIERS['high_momentum']}"
    elif state.failure_rate > 0.5 and state.consistency > 0.4:
        modifier = f" {STATE_MODIFIERS['recovering']}"
    
    return base_explanation + modifier


def get_safety_explanation(reason: str) -> str:
    """
    Get explanation for safety-overridden actions.
    
    Args:
        reason: The safety rule that triggered
        
    Returns:
        Explanation that doesn't expose internal logic
    """
    safety_explanations = {
        "uncertainty_fallback": "Let's keep things steady for now.",
        "anti_penalty_collapse": "Time for a calmer approach.",
        "anti_reward_spam": "Steady progress matters more than rewards.",
        "max_consecutive_reached": "Mixing things up a bit.",
    }
    return safety_explanations.get(reason, "You're doing fine.")
