"""
API Routes for HabitCity Backend

Endpoints:
- POST /decide-action: Get AI recommendation
- POST /update-state: Track state changes  
- GET /health: Health check for warm-up
- POST /register: Register/login user and initialize city
- GET /city-state: Get full city state
- POST /complete-habit: Complete a habit and get progression
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging

from app.models.schemas import (
    DecideActionRequest,
    DecideActionResponse,
    UpdateStateRequest,
    UpdateStateResponse,
    HealthResponse,
    RegisterRequest,
    RegisterResponse,
    UserResponse,
    CityStateResponse,
    BuildingState,
    CompleteHabitRequest,
    CompleteHabitResponse,
    BuildingUpdate,
    ActionType,
    ACTION_TO_CITY_EFFECT,
    ACTION_DISPLAY_NAMES,
    VALID_HABIT_TYPES,
)
from app.models.model_loader import model_loader
from app.models.db_models import User, HABIT_TO_BUILDING
from app.services.inference import run_inference
from app.services.progression import (
    initialize_user_city,
    get_city_state,
    complete_habit,
    apply_daily_decay,
)
from app.api.dependencies import get_current_user, get_firebase_user_info, get_db
from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/decide-action", response_model=DecideActionResponse)
async def decide_action(request: DecideActionRequest) -> DecideActionResponse:
    """
    Get an AI-driven action recommendation based on user state.
    
    The AI adapts its motivation strategy based on:
    - Consistency: How regularly the user completes habits
    - Momentum: Recent positive trend
    - Energy: Current energy level
    - Failure Rate: Recent failures
    - Fatigue: Accumulated tiredness
    
    Returns a user-facing action with explanation and city visual effect.
    """
    logger.info(f"Deciding action for user {request.user_id}")
    
    try:
        response = run_inference(
            user_id=request.user_id,
            state=request.state
        )
        logger.info(f"Action decided: {response.action} for user {request.user_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error in decide_action: {e}")
        raise HTTPException(status_code=500, detail="Inference error")


@router.post("/update-state", response_model=UpdateStateResponse)
async def update_state(request: UpdateStateRequest) -> UpdateStateResponse:
    """
    Track habit completion for state updates.
    
    Note: In the MVP, state is managed client-side.
    This endpoint is for future persistence integration.
    """
    logger.info(f"State update for user {request.user_id}: habit_completed={request.habit_completed}")
    
    # MVP: Just acknowledge the update
    # Future: Persist to database, update user profile
    return UpdateStateResponse(
        success=True,
        message="State update recorded"
    )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for warm-up pings.
    
    Frontend should ping this on load and periodically
    to prevent cold-start latency on free tiers.
    """
    return HealthResponse(
        status="healthy",
        model_loaded=model_loader.is_loaded,
        version=settings.API_VERSION
    )


# ============================================
# NEW: Protected Endpoints (Require Firebase Auth)
# ============================================

@router.post("/register", response_model=RegisterResponse)
async def register_user(
    request: RegisterRequest = None,
    firebase_user: dict = Depends(get_firebase_user_info),
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """
    Register a new user or login existing user.
    
    Called after Firebase authentication on the frontend.
    Creates user in database and initializes city if new.
    
    Returns user info and full city state.
    """
    uid = firebase_user["uid"]
    email = firebase_user["email"]
    display_name = firebase_user.get("display_name")
    timezone = request.timezone if request else "UTC"
    
    logger.info(f"Register/login request for {email}")
    
    # Check if user exists
    existing_user = db.query(User).filter(User.id == uid).first()
    
    if existing_user:
        # Existing user - just return their city state
        logger.info(f"Existing user found: {email}")
        city_state = get_city_state(db, uid)
        
        # Apply any pending decay
        apply_daily_decay(db, uid)
        
        return RegisterResponse(
            user=UserResponse(
                id=existing_user.id,
                email=existing_user.email,
                display_name=existing_user.display_name,
                timezone=existing_user.timezone,
                created_at=existing_user.created_at.isoformat(),
            ),
            city_state=CityStateResponse(
                buildings=[BuildingState(**b) for b in city_state["buildings"]]
            ),
            is_new_user=False,
        )
    
    # New user - create account and initialize city
    logger.info(f"Creating new user: {email}")
    
    new_user = User(
        id=uid,
        email=email,
        display_name=display_name,
        timezone=timezone,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Initialize city with 5 default buildings
    initialize_user_city(db, uid)
    
    city_state = get_city_state(db, uid)
    
    return RegisterResponse(
        user=UserResponse(
            id=new_user.id,
            email=new_user.email,
            display_name=new_user.display_name,
            timezone=new_user.timezone,
            created_at=new_user.created_at.isoformat(),
        ),
        city_state=CityStateResponse(
            buildings=[BuildingState(**b) for b in city_state["buildings"]]
        ),
        is_new_user=True,
    )


@router.get("/city-state", response_model=CityStateResponse)
async def get_user_city_state(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CityStateResponse:
    """
    Get the full city state for the authenticated user.
    
    Includes all buildings with their XP, level, and decay state.
    Also applies any pending daily decay.
    """
    # Apply decay first
    apply_daily_decay(db, user.id)
    
    city_state = get_city_state(db, user.id)
    
    return CityStateResponse(
        buildings=[BuildingState(**b) for b in city_state["buildings"]]
    )


@router.post("/complete-habit", response_model=CompleteHabitResponse)
async def complete_habit_endpoint(
    request: CompleteHabitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompleteHabitResponse:
    """
    Complete a habit and get progression update.
    
    1. Records habit completion
    2. Runs RL inference for motivation action
    3. Calculates XP gain (may be modified by RL action)
    4. Checks for level-up
    5. Returns full update for frontend animation
    """
    habit_type = request.habit_type
    
    # Validate habit type
    if habit_type not in VALID_HABIT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid habit type. Must be one of: {VALID_HABIT_TYPES}"
        )
    
    logger.info(f"User {user.id} completing habit: {habit_type}")
    
    # First, run RL inference to get action and XP modifier
    # Use default state for now (can be enhanced later)
    from app.models.schemas import UserState
    default_state = UserState(
        consistency=0.5,
        momentum=0.5,
        energy=0.7,
        failure_rate=0.2,
        fatigue=0.3,
    )
    
    rl_response = run_inference(user_id=user.id, state=default_state)
    rl_action = ActionType(rl_response.action_id)
    
    # Complete the habit with RL modifier
    try:
        progression_result = complete_habit(
            db=db,
            user_id=user.id,
            habit_type=habit_type,
            rl_action=rl_action,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return CompleteHabitResponse(
        action=rl_response.action,
        action_id=rl_response.action_id,
        explanation=rl_response.explanation,
        city_effect=rl_response.city_effect,
        building_update=BuildingUpdate(
            building=progression_result["building"],
            habit_type=progression_result["habit_type"],
            xp=progression_result["xp"],
            xp_delta=progression_result["xp_delta"],
            level=progression_result["level"],
            level_up=progression_result["level_up"],
            old_level=progression_result["old_level"],
            decay_days=progression_result["decay_days"],
            visual_state=progression_result["visual_state"],
        ),
    )
