"""
Database ORM Models

SQLAlchemy models for HabitCity persistence:
- User: Firebase-authenticated users
- HabitBuilding: Building progression per habit
- HabitLog: Daily habit completion records
"""
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, Boolean, Date, DateTime, 
    ForeignKey, CheckConstraint, Index
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """
    User account linked to Firebase Auth.
    
    The id is the Firebase UID, not auto-generated.
    """
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)  # Firebase UID
    email = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    timezone = Column(String, default="UTC")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    buildings = relationship("HabitBuilding", back_populates="user", cascade="all, delete-orphan")
    habit_logs = relationship("HabitLog", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class HabitBuilding(Base):
    """
    Building progression for a specific habit.
    
    Each user has 5 buildings (one per habit type).
    Buildings track XP, level, and decay state.
    """
    __tablename__ = "habit_buildings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    habit_type = Column(String, nullable=False)  # 'gym', 'study', 'sleep', 'meditation', 'diet'
    
    # Progression
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    
    # Decay tracking
    decay_days = Column(Integer, default=0)
    last_completed_date = Column(Date, nullable=True)
    
    # Timestamps
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="buildings")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("level >= 1 AND level <= 5", name="check_level_range"),
        CheckConstraint(
            "habit_type IN ('gym', 'study', 'sleep', 'meditation', 'diet')", 
            name="check_habit_type"
        ),
        Index("idx_buildings_user", "user_id"),
        # Unique constraint: one building per habit per user
        {"sqlite_autoincrement": True},
    )
    
    def __repr__(self):
        return f"<HabitBuilding {self.habit_type} L{self.level} XP:{self.xp}>"
    
    @property
    def visual_state(self) -> str:
        """
        Get visual state based on decay days.
        
        Returns:
            Visual state string for frontend rendering.
        """
        if self.decay_days == 0:
            return "normal"
        elif self.decay_days == 1:
            return "smoke"
        elif self.decay_days == 2:
            return "small_fire"
        elif self.decay_days == 3:
            return "medium_fire"
        else:
            return "large_fire"


class HabitLog(Base):
    """
    Daily habit completion log.
    
    Records whether each habit was completed on each date.
    Used for streak calculation and decay logic.
    """
    __tablename__ = "habit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    habit_type = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="habit_logs")
    
    # Indexes and constraints
    __table_args__ = (
        Index("idx_logs_user_date", "user_id", "date"),
        {"sqlite_autoincrement": True},
    )
    
    def __repr__(self):
        return f"<HabitLog {self.habit_type} {self.date} completed={self.completed}>"


# Valid habit types for validation
VALID_HABIT_TYPES = frozenset(["gym", "study", "sleep", "meditation", "diet"])

# Habit to building name mapping
HABIT_TO_BUILDING = {
    "gym": "Arena",
    "study": "Library", 
    "sleep": "House",
    "meditation": "Shrine",
    "diet": "Farm",
}
