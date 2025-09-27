"""
Personality model with JSON fields for MCP Character Service.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator

from sqlalchemy import (
    Column, String, Text, DateTime, UUID, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from src.database.connection import Base


class PersonalityTrait(BaseModel):
    """Pydantic model for individual personality traits."""
    trait: str = Field(..., min_length=1, max_length=50)
    intensity: int = Field(..., ge=1, le=10)
    manifestation: str = Field(..., min_length=1, max_length=200)


class Motivation(BaseModel):
    """Pydantic model for character motivations."""
    type: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=500)
    priority: int = Field(..., ge=1, le=10)


class Fear(BaseModel):
    """Pydantic model for character fears."""
    fear: str = Field(..., min_length=1, max_length=100)
    intensity: int = Field(..., ge=1, le=10)
    trigger: Optional[str] = Field(None, max_length=200)


class Value(BaseModel):
    """Pydantic model for character values."""
    value: str = Field(..., min_length=1, max_length=50)
    importance: int = Field(..., ge=1, le=10)
    description: Optional[str] = Field(None, max_length=200)


class BehavioralPattern(BaseModel):
    """Pydantic model for behavioral patterns."""
    pattern: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., regex=r'^(always|often|sometimes|rarely|never)$')
    context: Optional[str] = Field(None, max_length=200)


class GrowthArcStage(BaseModel):
    """Pydantic model for growth arc stages."""
    stage: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=500)
    triggers: Optional[List[str]] = Field(default_factory=list)
    outcomes: Optional[List[str]] = Field(default_factory=list)


class PersonalityStructure(BaseModel):
    """Pydantic model for complete personality structure validation."""
    dominant_traits: Optional[List[PersonalityTrait]] = Field(default_factory=list)
    secondary_traits: Optional[List[PersonalityTrait]] = Field(default_factory=list)
    motivations: Optional[List[Motivation]] = Field(default_factory=list)
    fears: Optional[List[Fear]] = Field(default_factory=list)
    values: Optional[List[Value]] = Field(default_factory=list)
    behavioral_patterns: Optional[List[BehavioralPattern]] = Field(default_factory=list)
    growth_arc: Optional[List[GrowthArcStage]] = Field(default_factory=list)
    
    @validator('dominant_traits', 'secondary_traits')
    def validate_unique_traits(cls, v):
        """Ensure no duplicate traits."""
        if not v:
            return v
        
        trait_names = [trait.trait.lower() for trait in v]
        if len(trait_names) != len(set(trait_names)):
            raise ValueError("Duplicate traits are not allowed")
        return v
    
    @validator('motivations')
    def validate_motivations_consistency(cls, v):
        """Validate motivation consistency."""
        if not v:
            return v
        
        # Check for conflicting motivations (basic validation)
        motivation_types = [m.type.lower() for m in v]
        if len(motivation_types) != len(set(motivation_types)):
            raise ValueError("Duplicate motivation types are not allowed")
        return v
    
    @validator('fears')
    def validate_fears_consistency(cls, v):
        """Validate fear consistency."""
        if not v:
            return v
        
        fear_names = [f.fear.lower() for f in v]
        if len(fear_names) != len(set(fear_names)):
            raise ValueError("Duplicate fears are not allowed")
        return v


class Personality(Base):
    """Personality model for detailed psychological profiles."""
    
    __tablename__ = "personalities"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Character reference (one-to-one)
    character_id = Column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Personality components (JSON fields)
    dominant_traits = Column(JSON, nullable=True)
    secondary_traits = Column(JSON, nullable=True)
    motivations = Column(JSON, nullable=True)
    fears = Column(JSON, nullable=True)
    values = Column(JSON, nullable=True)
    behavioral_patterns = Column(JSON, nullable=True)
    growth_arc = Column(JSON, nullable=True)
    
    # Detailed analysis
    psychological_profile = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship to character
    character = relationship("Character", back_populates="personality")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('character_id', name='unique_personality_per_character'),
    )
    
    @validates('dominant_traits', 'secondary_traits', 'motivations', 'fears', 'values', 'behavioral_patterns', 'growth_arc')
    def validate_personality_structure(self, key, value):
        """Validate personality structure using Pydantic models."""
        if value is None:
            return value
        
        try:
            # Create a temporary structure for validation
            temp_structure = {
                'dominant_traits': [],
                'secondary_traits': [],
                'motivations': [],
                'fears': [],
                'values': [],
                'behavioral_patterns': [],
                'growth_arc': []
            }
            temp_structure[key] = value
            
            # Validate the specific field
            if key in ['dominant_traits', 'secondary_traits']:
                [PersonalityTrait(**trait) for trait in value]
            elif key == 'motivations':
                [Motivation(**motivation) for motivation in value]
            elif key == 'fears':
                [Fear(**fear) for fear in value]
            elif key == 'values':
                [Value(**val) for val in value]
            elif key == 'behavioral_patterns':
                [BehavioralPattern(**pattern) for pattern in value]
            elif key == 'growth_arc':
                [GrowthArcStage(**stage) for stage in value]
                
        except Exception as e:
            raise ValueError(f"Invalid {key} structure: {e}")
        
        return value
    
    def validate_complete_structure(self) -> bool:
        """Validate the complete personality structure for consistency."""
        try:
            structure_data = {
                'dominant_traits': self.dominant_traits or [],
                'secondary_traits': self.secondary_traits or [],
                'motivations': self.motivations or [],
                'fears': self.fears or [],
                'values': self.values or [],
                'behavioral_patterns': self.behavioral_patterns or [],
                'growth_arc': self.growth_arc or []
            }
            
            PersonalityStructure(**structure_data)
            return True
        except Exception:
            return False
    
    def get_trait_by_name(self, trait_name: str, include_secondary: bool = True) -> Optional[Dict[str, Any]]:
        """Get a specific trait by name."""
        trait_name_lower = trait_name.lower()
        
        # Check dominant traits
        if self.dominant_traits:
            for trait in self.dominant_traits:
                if trait.get('trait', '').lower() == trait_name_lower:
                    return trait
        
        # Check secondary traits if requested
        if include_secondary and self.secondary_traits:
            for trait in self.secondary_traits:
                if trait.get('trait', '').lower() == trait_name_lower:
                    return trait
        
        return None
    
    def get_strongest_traits(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get the strongest personality traits."""
        all_traits = []
        
        if self.dominant_traits:
            all_traits.extend(self.dominant_traits)
        if self.secondary_traits:
            all_traits.extend(self.secondary_traits)
        
        # Sort by intensity (descending)
        sorted_traits = sorted(all_traits, key=lambda x: x.get('intensity', 0), reverse=True)
        return sorted_traits[:limit]
    
    def get_primary_motivations(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get the primary motivations by priority."""
        if not self.motivations:
            return []
        
        sorted_motivations = sorted(self.motivations, key=lambda x: x.get('priority', 0), reverse=True)
        return sorted_motivations[:limit]
    
    def has_conflicting_elements(self) -> List[str]:
        """Check for potential conflicts in personality elements."""
        conflicts = []
        
        # Check for conflicting traits and fears
        if self.dominant_traits and self.fears:
            trait_names = [trait.get('trait', '').lower() for trait in self.dominant_traits]
            fear_names = [fear.get('fear', '').lower() for fear in self.fears]
            
            # Simple conflict detection (can be expanded)
            if 'brave' in trait_names and 'fear' in ' '.join(fear_names):
                conflicts.append("Potential conflict between brave trait and fears")
        
        return conflicts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert personality to dictionary representation."""
        return {
            "id": str(self.id),
            "character_id": str(self.character_id),
            "dominant_traits": self.dominant_traits,
            "secondary_traits": self.secondary_traits,
            "motivations": self.motivations,
            "fears": self.fears,
            "values": self.values,
            "behavioral_patterns": self.behavioral_patterns,
            "growth_arc": self.growth_arc,
            "psychological_profile": self.psychological_profile,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self) -> str:
        trait_count = len(self.dominant_traits) if self.dominant_traits else 0
        return f"<Personality(id={self.id}, character_id={self.character_id}, traits={trait_count})>"
