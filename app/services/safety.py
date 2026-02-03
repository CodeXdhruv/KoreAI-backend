"""
Safety Rules for RL Actions

Implements anti-collapse clamping and fallback logic to ensure
the AI never spirals into punishment or reward spam.
"""
from collections import defaultdict
from typing import Optional
import logging

from app.models.schemas import ActionType

logger = logging.getLogger(__name__)


class SafetyManager:
    """
    Manages safety constraints for action selection.
    Prevents action spam and ensures graceful degradation.
    """
    
    def __init__(self, max_consecutive: int = 3, default_action: int = 3):
        """
        Args:
            max_consecutive: Max times the same action can repeat
            default_action: Fallback action (NEUTRAL_WAIT = 3)
        """
        self.max_consecutive = max_consecutive
        self.default_action = default_action
        
        # Track action history per user (in-memory, ephemeral)
        self._user_history: dict[str, list[int]] = defaultdict(list)
        self._history_limit = 10  # Keep last N actions
    
    def apply_safety_rules(
        self, 
        user_id: str, 
        proposed_action: int,
        confidence: float
    ) -> tuple[int, str]:
        """
        Apply safety rules to the proposed action.
        
        Args:
            user_id: User identifier
            proposed_action: Action suggested by the model
            confidence: Model's confidence in the action
            
        Returns:
            Tuple of (final_action, reason)
        """
        history = self._user_history[user_id]
        
        # Rule 1: Low confidence → default to NEUTRAL_WAIT
        if confidence < 0.25:
            logger.info(f"Low confidence ({confidence:.2f}), defaulting to NEUTRAL_WAIT")
            final_action = ActionType.NEUTRAL_WAIT
            reason = "uncertainty_fallback"
            self._record_action(user_id, final_action)
            return final_action, reason
        
        # Rule 2: Anti-collapse - prevent consecutive penalties
        if proposed_action == ActionType.SOFT_PENALTY:
            penalty_count = sum(1 for a in history[-3:] if a == ActionType.SOFT_PENALTY)
            if penalty_count >= 2:
                logger.info("Anti-collapse: too many penalties, switching to NEUTRAL_WAIT")
                final_action = ActionType.NEUTRAL_WAIT
                reason = "anti_penalty_collapse"
                self._record_action(user_id, final_action)
                return final_action, reason
        
        # Rule 3: Anti-spam - prevent reward spam
        if proposed_action == ActionType.COMPENSATE_REWARD:
            reward_count = sum(1 for a in history[-3:] if a == ActionType.COMPENSATE_REWARD)
            if reward_count >= 2:
                logger.info("Anti-spam: too many rewards, switching to NEUTRAL_WAIT")
                final_action = ActionType.NEUTRAL_WAIT
                reason = "anti_reward_spam"
                self._record_action(user_id, final_action)
                return final_action, reason
        
        # Rule 4: General consecutive action limit
        if len(history) >= self.max_consecutive:
            recent = history[-self.max_consecutive:]
            if all(a == proposed_action for a in recent):
                logger.info(f"Max consecutive ({self.max_consecutive}) reached, switching to NEUTRAL_WAIT")
                final_action = ActionType.NEUTRAL_WAIT
                reason = "max_consecutive_reached"
                self._record_action(user_id, final_action)
                return final_action, reason
        
        # No rules triggered, use proposed action
        self._record_action(user_id, proposed_action)
        return proposed_action, "model_decision"
    
    def _record_action(self, user_id: str, action: int):
        """Record action in user history."""
        history = self._user_history[user_id]
        history.append(action)
        # Trim to limit
        if len(history) > self._history_limit:
            self._user_history[user_id] = history[-self._history_limit:]
    
    def get_fallback_action(self) -> int:
        """Get the default fallback action."""
        return self.default_action
    
    def clear_user_history(self, user_id: str):
        """Clear action history for a user."""
        if user_id in self._user_history:
            del self._user_history[user_id]


# Global instance
safety_manager = SafetyManager()
