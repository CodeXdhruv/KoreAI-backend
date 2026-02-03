from enum import IntEnum
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class ActionType(IntEnum):
    """RL action types mapped to user-facing meanings."""
    SOFT_PENALTY = 0       # "Let's reset gently"
    LOWER_GOAL = 1         # "Let's make today easier"
    COMPENSATE_REWARD = 2  # "You earned something nice"
    NEUTRAL_WAIT = 3       # "You're doing fine"


class CityEffect(str):
    """City visual effects for each action."""
    UPGRADE_BUILDING = "upgrade_building"
    SIMPLIFY_BUILDING = "simplify_building"
    ADD_FOG = "add_fog"
    IDLE = "idle"


# Map actions to city effects
ACTION_TO_CITY_EFFECT = {
    ActionType.SOFT_PENALTY: "add_fog",
    ActionType.LOWER_GOAL: "simplify_building",
    ActionType.COMPENSATE_REWARD: "upgrade_building",
    ActionType.NEUTRAL_WAIT: "idle",
}

# User-facing action names (never expose internal terms)
ACTION_DISPLAY_NAMES = {
    ActionType.SOFT_PENALTY: "GENTLE_RESET",
    ActionType.LOWER_GOAL: "EASIER_DAY",
    ActionType.COMPENSATE_REWARD: "REWARD_BOOST",
    ActionType.NEUTRAL_WAIT: "STEADY_PROGRESS",
}

# Valid habit types
VALID_HABIT_TYPES = ["gym", "study", "sleep", "meditation", "diet"]


class UserState(BaseModel):
    """5D normalized state vector for RL inference."""
    consistency: float = Field(..., ge=0.0, le=1.0, description="How consistent the user has been")
    momentum: float = Field(..., ge=0.0, le=1.0, description="Recent positive trend")
    energy: float = Field(..., ge=0.0, le=1.0, description="User's current energy level")
    failure_rate: float = Field(..., ge=0.0, le=1.0, description="Recent failure rate")
    fatigue: float = Field(..., ge=0.0, le=1.0, description="Accumulated fatigue")
    
    def to_array(self) -> list[float]:
        """Convert to numpy-compatible array."""
        return [self.consistency, self.momentum, self.energy, self.failure_rate, self.fatigue]


class DecideActionRequest(BaseModel):
    """Request body for /decide-action endpoint."""
    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    state: UserState = Field(..., description="Current user state vector")


class DecideActionResponse(BaseModel):
    """Response body for /decide-action endpoint."""
    action: str = Field(..., description="User-facing action name")
    action_id: int = Field(..., ge=0, le=3, description="Internal action ID")
    explanation: str = Field(..., description="Friendly explanation for the user")
    city_effect: str = Field(..., description="Visual effect to apply to the city")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model confidence")


class UpdateStateRequest(BaseModel):
    """Request body for /update-state endpoint."""
    user_id: str = Field(..., min_length=1)
    habit_completed: bool = Field(..., description="Whether the habit was completed")
    habit_type: Optional[str] = Field(None, description="Type of habit (gym, study, etc.)")


class UpdateStateResponse(BaseModel):
    """Response body for /update-state endpoint."""
    success: bool
    message: str


class HealthResponse(BaseModel):
    """Response body for /health endpoint."""
    status: str
    model_loaded: bool
    version: str


# ============================================
# NEW: Building Progression Schemas
# ============================================

class UserResponse(BaseModel):
    """User info response."""
    id: str
    email: str
    display_name: Optional[str] = None
    timezone: str = "UTC"
    created_at: str


class BuildingState(BaseModel):
    """State of a single building."""
    building: str = Field(..., description="Building name (Arena, Library, etc.)")
    habit_type: str = Field(..., description="Habit type (gym, study, etc.)")
    xp: int = Field(..., ge=0, description="Current XP")
    level: int = Field(..., ge=1, le=5, description="Building level 1-5")
    decay_days: int = Field(..., ge=0, description="Days since last completion")
    visual_state: str = Field(..., description="Visual state (normal, smoke, small_fire, etc.)")
    last_completed: Optional[str] = Field(None, description="Last completion date ISO format")


class CityStateResponse(BaseModel):
    """Full city state response."""
    buildings: List[BuildingState]


class RegisterRequest(BaseModel):
    """Request body for /register endpoint (optional, uses token)."""
    timezone: Optional[str] = Field("UTC", description="User's timezone")


class RegisterResponse(BaseModel):
    """Response body for /register endpoint."""
    user: UserResponse
    city_state: CityStateResponse
    is_new_user: bool


class CompleteHabitRequest(BaseModel):
    """Request body for /complete-habit endpoint."""
    habit_type: str = Field(..., description="Habit type to complete")
    
    def validate_habit_type(self):
        if self.habit_type not in VALID_HABIT_TYPES:
            raise ValueError(f"Invalid habit type. Must be one of: {VALID_HABIT_TYPES}")


class BuildingUpdate(BaseModel):
    """Single building update after habit completion."""
    building: str
    habit_type: str
    xp: int
    xp_delta: int
    level: int
    level_up: bool
    old_level: int
    decay_days: int
    visual_state: str


class CompleteHabitResponse(BaseModel):
    """Response body for /complete-habit endpoint."""
    action: str = Field(..., description="RL action taken")
    action_id: int
    explanation: str
    building_update: BuildingUpdate
    city_effect: str

