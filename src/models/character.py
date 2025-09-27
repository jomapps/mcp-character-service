"""
Character model with SQLAlchemy for MCP Character Service.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, 
    UUID, JSON, ForeignKey, CheckConstraint
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, validator

from src.database.connection import Base


class NarrativeRole(str, Enum):
    """Enumeration of narrative roles for characters."""
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    MENTOR = "mentor"
    ALLY = "ally"
    NEUTRAL = "neutral"
    COMIC_RELIEF = "comic_relief"


class PersonalityTrait(BaseModel):
    """Pydantic model for personality traits."""
    trait: str = Field(..., min_length=1, max_length=50)
    intensity: int = Field(..., ge=1, le=10)
    manifestation: str = Field(..., min_length=1, max_length=200)


class PersonalityTraits(BaseModel):
    """Pydantic model for personality traits structure."""
    dominant_traits: List[PersonalityTrait] = Field(default_factory=list)
    
    @validator('dominant_traits')
    def validate_dominant_traits(cls, v):
        if not v:
            return v
        
        # Check for duplicate traits
        trait_names = [trait.trait.lower() for trait in v]
        if len(trait_names) != len(set(trait_names)):
            raise ValueError("Duplicate personality traits are not allowed")
        
        return v


class EmotionalState(BaseModel):
    """Pydantic model for emotional state."""
    current_mood: Optional[str] = Field(None, max_length=50)
    stress_level: Optional[int] = Field(None, ge=0, le=10)
    dominant_emotion: Optional[str] = Field(None, max_length=50)
    emotional_stability: Optional[int] = Field(None, ge=1, le=10)


class Character(Base):
    """Character model representing a story character."""
    
    __tablename__ = "characters"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(100), nullable=False, index=True)
    nickname = Column(String(50), nullable=True, index=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)
    occupation = Column(String(100), nullable=True)
    
    # Detailed information
    backstory = Column(Text, nullable=True)
    physical_description = Column(Text, nullable=True)
    
    # JSON fields for complex data
    personality_traits = Column(JSON, nullable=True)
    emotional_state = Column(JSON, nullable=True)
    
    # Story-related fields
    narrative_role = Column(String(20), nullable=True, index=True)
    archetype_id = Column(UUID(as_uuid=True), ForeignKey("archetypes.id", ondelete="SET NULL"), nullable=True)
    
    # Metadata
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    archetype = relationship("Archetype", back_populates="characters")
    personality = relationship("Personality", back_populates="character", uselist=False, cascade="all, delete-orphan")
    
    # Relationship connections (both directions)
    relationships_as_a = relationship(
        "Relationship",
        foreign_keys="Relationship.character_a_id",
        back_populates="character_a",
        cascade="all, delete-orphan"
    )
    relationships_as_b = relationship(
        "Relationship",
        foreign_keys="Relationship.character_b_id",
        back_populates="character_b",
        cascade="all, delete-orphan"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint('age IS NULL OR (age >= 0 AND age <= 200)', name='valid_age_range'),
        CheckConstraint('length(name) > 0', name='non_empty_name'),
    )
    
    @validates('name')
    def validate_name(self, key, name):
        """Validate character name."""
        if not name or not name.strip():
            raise ValueError("Character name cannot be empty")
        if len(name) > 100:
            raise ValueError("Character name cannot exceed 100 characters")
        return name.strip()
    
    @validates('nickname')
    def validate_nickname(self, key, nickname):
        """Validate character nickname."""
        if nickname is not None:
            if len(nickname) > 50:
                raise ValueError("Character nickname cannot exceed 50 characters")
            return nickname.strip() if nickname.strip() else None
        return nickname
    
    @validates('age')
    def validate_age(self, key, age):
        """Validate character age."""
        if age is not None:
            if age < 0 or age > 200:
                raise ValueError("Character age must be between 0 and 200")
        return age
    
    @validates('narrative_role')
    def validate_narrative_role(self, key, role):
        """Validate narrative role."""
        if role is not None:
            valid_roles = [r.value for r in NarrativeRole]
            if role not in valid_roles:
                raise ValueError(f"Invalid narrative role. Must be one of: {valid_roles}")
        return role
    
    @validates('personality_traits')
    def validate_personality_traits(self, key, traits):
        """Validate personality traits structure."""
        if traits is not None:
            try:
                # Validate using Pydantic model
                PersonalityTraits(**traits)
            except Exception as e:
                raise ValueError(f"Invalid personality traits structure: {e}")
        return traits
    
    @validates('emotional_state')
    def validate_emotional_state(self, key, state):
        """Validate emotional state structure."""
        if state is not None:
            try:
                # Validate using Pydantic model
                EmotionalState(**state)
            except Exception as e:
                raise ValueError(f"Invalid emotional state structure: {e}")
        return state
    
    def get_all_relationships(self):
        """Get all relationships for this character (both directions)."""
        return self.relationships_as_a + self.relationships_as_b
    
    def get_relationships_by_type(self, relationship_type: str):
        """Get relationships of a specific type."""
        all_relationships = self.get_all_relationships()
        return [rel for rel in all_relationships if rel.relationship_type == relationship_type]
    
    def has_relationship_with(self, other_character_id: uuid.UUID, relationship_type: Optional[str] = None):
        """Check if this character has a relationship with another character."""
        all_relationships = self.get_all_relationships()
        
        for rel in all_relationships:
            other_id = rel.character_b_id if rel.character_a_id == self.id else rel.character_a_id
            if other_id == other_character_id:
                if relationship_type is None or rel.relationship_type == relationship_type:
                    return True
        return False
    
    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """Convert character to dictionary representation."""
        result = {
            "id": str(self.id),
            "name": self.name,
            "nickname": self.nickname,
            "age": self.age,
            "gender": self.gender,
            "occupation": self.occupation,
            "backstory": self.backstory,
            "physical_description": self.physical_description,
            "personality_traits": self.personality_traits,
            "emotional_state": self.emotional_state,
            "narrative_role": self.narrative_role,
            "archetype_id": str(self.archetype_id) if self.archetype_id else None,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_relationships:
            result["relationships"] = [
                {
                    "id": str(rel.id),
                    "type": rel.relationship_type,
                    "other_character_id": str(
                        rel.character_b_id if rel.character_a_id == self.id else rel.character_a_id
                    ),
                    "strength": rel.strength,
                    "status": rel.status,
                }
                for rel in self.get_all_relationships()
            ]
        
        return result
    
    def __repr__(self) -> str:
        return f"<Character(id={self.id}, name='{self.name}', role='{self.narrative_role}')>"
