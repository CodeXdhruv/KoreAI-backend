"""
Progression Service

Handles building XP, level-ups, decay, and city initialization.
This is the core game logic for HabitCity.
"""
import logging
from datetime import date, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.db_models import User, HabitBuilding, HabitLog, VALID_HABIT_TYPES, HABIT_TO_BUILDING
from app.models.schemas import ActionType

logger = logging.getLogger(__name__)


# XP thresholds for each level
XP_THRESHOLDS = {
    1: 0,      # Level 1: Starting
    2: 100,    # Level 2: 100 XP
    3: 350,    # Level 3: 350 XP cumulative
    4: 850,    # Level 4: 850 XP cumulative
    5: 1850,   # Level 5: 1850 XP cumulative (max)
}

# Base XP for completing a habit
BASE_XP_GAIN = 25

# XP modifiers based on RL action
XP_MODIFIERS = {
    ActionType.COMPENSATE_REWARD: 1.5,   # +50% XP bonus
    ActionType.NEUTRAL_WAIT: 1.0,         # Normal XP
    ActionType.LOWER_GOAL: 1.0,           # Normal XP
    ActionType.SOFT_PENALTY: 0.8,         # -20% XP (still positive!)
}

# Days required for streak-based level up (alternative to XP)
STREAK_DAYS_FOR_LEVEL_UP = 7


def initialize_user_city(db: Session, user_id: str) -> List[HabitBuilding]:
    """
    Create default buildings for a new user.
    
    Each user starts with 5 buildings (one per habit) at Level 1.
    
    Args:
        db: Database session.
        user_id: Firebase UID.
        
    Returns:
        List of created HabitBuilding objects.
    """
    buildings = []
    
    for habit_type in VALID_HABIT_TYPES:
        building = HabitBuilding(
            user_id=user_id,
            habit_type=habit_type,
            xp=0,
            level=1,
            decay_days=0,
            last_completed_date=None,
        )
        db.add(building)
        buildings.append(building)
    
    db.commit()
    
    # Refresh to get IDs
    for building in buildings:
        db.refresh(building)
    
    logger.info(f"Initialized city for user {user_id} with {len(buildings)} buildings")
    return buildings


def get_user_buildings(db: Session, user_id: str) -> List[HabitBuilding]:
    """
    Get all buildings for a user.
    
    Args:
        db: Database session.
        user_id: Firebase UID.
        
    Returns:
        List of HabitBuilding objects.
    """
    return db.query(HabitBuilding).filter(HabitBuilding.user_id == user_id).all()


def calculate_xp_gain(
    habit_type: str,
    rl_action: Optional[ActionType] = None,
    base_xp: int = BASE_XP_GAIN,
) -> int:
    """
    Calculate XP gain for completing a habit.
    
    XP can be modified by the RL agent's action.
    
    Args:
        habit_type: The habit that was completed.
        rl_action: Optional RL action that may modify XP.
        base_xp: Base XP amount.
        
    Returns:
        Calculated XP gain (always positive).
    """
    modifier = 1.0
    if rl_action and rl_action in XP_MODIFIERS:
        modifier = XP_MODIFIERS[rl_action]
    
    xp_gain = int(base_xp * modifier)
    
    # Ensure minimum 1 XP
    return max(1, xp_gain)


def check_level_up(building: HabitBuilding) -> bool:
    """
    Check if a building should level up.
    
    Level up happens when:
    1. XP exceeds the threshold for next level, OR
    2. User completed the habit for 7 consecutive days
    
    Args:
        building: The HabitBuilding to check.
        
    Returns:
        True if level up should occur, False otherwise.
    """
    if building.level >= 5:
        return False  # Max level
    
    next_level = building.level + 1
    xp_threshold = XP_THRESHOLDS.get(next_level, float('inf'))
    
    return building.xp >= xp_threshold


def apply_xp_and_level(
    db: Session,
    building: HabitBuilding,
    xp_delta: int,
) -> dict:
    """
    Apply XP gain to a building and check for level-up.
    
    Args:
        db: Database session.
        building: The HabitBuilding to update.
        xp_delta: XP to add.
        
    Returns:
        Dict with xp_delta, new_xp, level_up, new_level.
    """
    old_level = building.level
    building.xp += xp_delta
    
    level_up = False
    while check_level_up(building) and building.level < 5:
        building.level += 1
        level_up = True
        logger.info(f"Building {building.habit_type} leveled up to {building.level}")
    
    # Reset decay on completion
    building.decay_days = 0
    building.last_completed_date = date.today()
    
    db.commit()
    
    return {
        "xp_delta": xp_delta,
        "new_xp": building.xp,
        "level_up": level_up,
        "old_level": old_level,
        "new_level": building.level,
    }


def calculate_decay(building: HabitBuilding, today: date) -> int:
    """
    Calculate decay days based on last completion.
    
    Args:
        building: The HabitBuilding to check.
        today: Current date (can be passed for testing).
        
    Returns:
        Number of decay days (0 if completed today/yesterday).
    """
    if building.last_completed_date is None:
        # Never completed - treat as 0 decay (new building)
        return 0
    
    days_since = (today - building.last_completed_date).days
    
    if days_since <= 0:
        return 0  # Completed today
    elif days_since == 1:
        return 0  # Completed yesterday, no decay yet
    else:
        # Decay starts after missing 1 day
        return min(days_since - 1, 5)  # Cap at 5 days


def apply_daily_decay(db: Session, user_id: str, today: Optional[date] = None) -> List[dict]:
    """
    Apply daily decay to all buildings for a user.
    
    Should be called at the start of each day (via cron or on app open).
    
    Args:
        db: Database session.
        user_id: Firebase UID.
        today: Override date for testing.
        
    Returns:
        List of building updates with decay info.
    """
    if today is None:
        today = date.today()
    
    buildings = get_user_buildings(db, user_id)
    updates = []
    
    for building in buildings:
        old_decay = building.decay_days
        new_decay = calculate_decay(building, today)
        
        if new_decay != old_decay:
            building.decay_days = new_decay
            updates.append({
                "building": HABIT_TO_BUILDING.get(building.habit_type, building.habit_type),
                "habit_type": building.habit_type,
                "old_decay": old_decay,
                "new_decay": new_decay,
                "visual_state": building.visual_state,
            })
    
    if updates:
        db.commit()
        logger.info(f"Applied decay to {len(updates)} buildings for user {user_id}")
    
    return updates


def complete_habit(
    db: Session,
    user_id: str,
    habit_type: str,
    rl_action: Optional[ActionType] = None,
) -> dict:
    """
    Handle habit completion - the main progression entry point.
    
    1. Records habit log
    2. Calculates XP gain
    3. Applies XP and checks level-up
    4. Resets decay
    
    Args:
        db: Database session.
        user_id: Firebase UID.
        habit_type: Habit that was completed.
        rl_action: Optional RL action for XP modifier.
        
    Returns:
        Dict with full progression update info.
    """
    if habit_type not in VALID_HABIT_TYPES:
        raise ValueError(f"Invalid habit type: {habit_type}")
    
    # Get the building
    building = db.query(HabitBuilding).filter(
        HabitBuilding.user_id == user_id,
        HabitBuilding.habit_type == habit_type,
    ).first()
    
    if not building:
        raise ValueError(f"Building not found for habit {habit_type}")
    
    # Log the completion
    today = date.today()
    existing_log = db.query(HabitLog).filter(
        HabitLog.user_id == user_id,
        HabitLog.habit_type == habit_type,
        HabitLog.date == today,
    ).first()
    
    if existing_log:
        # Already completed today
        existing_log.completed = True
    else:
        log = HabitLog(
            user_id=user_id,
            habit_type=habit_type,
            date=today,
            completed=True,
        )
        db.add(log)
    
    # Calculate and apply XP
    xp_gain = calculate_xp_gain(habit_type, rl_action)
    result = apply_xp_and_level(db, building, xp_gain)
    
    return {
        "building": HABIT_TO_BUILDING.get(habit_type, habit_type),
        "habit_type": habit_type,
        "xp": building.xp,
        "xp_delta": result["xp_delta"],
        "level": building.level,
        "level_up": result["level_up"],
        "old_level": result["old_level"],
        "decay_days": building.decay_days,
        "visual_state": building.visual_state,
    }


def get_city_state(db: Session, user_id: str) -> dict:
    """
    Get the full city state for a user.
    
    Args:
        db: Database session.
        user_id: Firebase UID.
        
    Returns:
        Dict with all building states.
    """
    buildings = get_user_buildings(db, user_id)
    
    return {
        "buildings": [
            {
                "building": HABIT_TO_BUILDING.get(b.habit_type, b.habit_type),
                "habit_type": b.habit_type,
                "xp": b.xp,
                "level": b.level,
                "decay_days": b.decay_days,
                "visual_state": b.visual_state,
                "last_completed": b.last_completed_date.isoformat() if b.last_completed_date else None,
            }
            for b in buildings
        ]
    }


def get_streak(db: Session, user_id: str, habit_type: str) -> int:
    """
    Calculate current streak for a habit.
    
    Args:
        db: Database session.
        user_id: Firebase UID.
        habit_type: Habit to check.
        
    Returns:
        Number of consecutive days completed.
    """
    today = date.today()
    streak = 0
    current_date = today
    
    while True:
        log = db.query(HabitLog).filter(
            HabitLog.user_id == user_id,
            HabitLog.habit_type == habit_type,
            HabitLog.date == current_date,
            HabitLog.completed == True,
        ).first()
        
        if log:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            break
        
        # Safety limit
        if streak > 365:
            break
    
    return streak
