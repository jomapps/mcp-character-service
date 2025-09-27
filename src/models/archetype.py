"""
Archetype model with templates for MCP Character Service.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator

from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, UUID, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from src.database.connection import Base


class ArchetypeTemplate(BaseModel):
    """Pydantic model for archetype template validation."""
    default_traits: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    common_motivations: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    relationship_patterns: Optional[List[str]] = Field(default_factory=list)
    growth_patterns: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    examples: Optional[List[str]] = Field(default_factory=list)
    
    @validator('default_traits')
    def validate_default_traits(cls, v):
        """Validate default traits structure."""
        if not v:
            return v
        
        for trait in v:
            if not isinstance(trait, dict):
                raise ValueError("Each trait must be a dictionary")
            
            required_fields = ['trait', 'intensity']
            for field in required_fields:
                if field not in trait:
                    raise ValueError(f"Trait must contain '{field}' field")
            
            if not isinstance(trait['intensity'], int) or trait['intensity'] < 1 or trait['intensity'] > 10:
                raise ValueError("Trait intensity must be an integer between 1 and 10")
        
        return v
    
    @validator('common_motivations')
    def validate_common_motivations(cls, v):
        """Validate common motivations structure."""
        if not v:
            return v
        
        for motivation in v:
            if not isinstance(motivation, dict):
                raise ValueError("Each motivation must be a dictionary")
            
            required_fields = ['type', 'description']
            for field in required_fields:
                if field not in motivation:
                    raise ValueError(f"Motivation must contain '{field}' field")
        
        return v


class Archetype(Base):
    """Archetype model for character templates and patterns."""
    
    __tablename__ = "archetypes"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # Template data (JSON fields)
    default_traits = Column(JSON, nullable=True)
    narrative_function = Column(String(100), nullable=True)
    common_motivations = Column(JSON, nullable=True)
    relationship_patterns = Column(JSON, nullable=True)
    growth_patterns = Column(JSON, nullable=True)
    examples = Column(JSON, nullable=True)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    characters = relationship("Character", back_populates="archetype")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('name', name='unique_archetype_name'),
    )
    
    @validates('name')
    def validate_name(self, key, name):
        """Validate archetype name."""
        if not name or not name.strip():
            raise ValueError("Archetype name cannot be empty")
        if len(name) > 100:
            raise ValueError("Archetype name cannot exceed 100 characters")
        return name.strip()
    
    @validates('default_traits', 'common_motivations', 'relationship_patterns', 'growth_patterns', 'examples')
    def validate_template_structure(self, key, value):
        """Validate archetype template structure."""
        if value is None:
            return value
        
        try:
            # Create a temporary template for validation
            temp_template = {
                'default_traits': [],
                'common_motivations': [],
                'relationship_patterns': [],
                'growth_patterns': [],
                'examples': []
            }
            temp_template[key] = value
            
            # Validate using Pydantic model
            ArchetypeTemplate(**temp_template)
            
        except Exception as e:
            raise ValueError(f"Invalid {key} structure: {e}")
        
        return value
    
    def get_default_personality_traits(self) -> List[Dict[str, Any]]:
        """Get default personality traits for this archetype."""
        return self.default_traits or []
    
    def get_common_motivations(self) -> List[Dict[str, Any]]:
        """Get common motivations for this archetype."""
        return self.common_motivations or []
    
    def get_relationship_patterns(self) -> List[str]:
        """Get typical relationship patterns for this archetype."""
        return self.relationship_patterns or []
    
    def get_growth_patterns(self) -> List[Dict[str, Any]]:
        """Get typical growth patterns for this archetype."""
        return self.growth_patterns or []
    
    def get_examples(self) -> List[str]:
        """Get example characters of this archetype."""
        return self.examples or []
    
    def apply_to_character_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply archetype defaults to character data."""
        enhanced_data = character_data.copy()
        
        # Apply default narrative function if not specified
        if not enhanced_data.get('narrative_role') and self.narrative_function:
            enhanced_data['narrative_role'] = self.narrative_function
        
        # Apply default personality traits if not specified
        if not enhanced_data.get('personality_traits') and self.default_traits:
            enhanced_data['personality_traits'] = {
                'dominant_traits': self.default_traits.copy()
            }
        elif enhanced_data.get('personality_traits') and self.default_traits:
            # Merge with existing traits (existing traits take precedence)
            existing_traits = enhanced_data['personality_traits'].get('dominant_traits', [])
            existing_trait_names = {trait.get('trait', '').lower() for trait in existing_traits}
            
            # Add archetype traits that don't conflict
            for archetype_trait in self.default_traits:
                trait_name = archetype_trait.get('trait', '').lower()
                if trait_name not in existing_trait_names:
                    existing_traits.append(archetype_trait)
            
            enhanced_data['personality_traits']['dominant_traits'] = existing_traits
        
        return enhanced_data
    
    def is_compatible_with_role(self, narrative_role: str) -> bool:
        """Check if this archetype is compatible with a narrative role."""
        if not self.narrative_function:
            return True  # Compatible with any role if no specific function
        
        # Define compatibility mappings
        compatibility_map = {
            'protagonist': ['hero', 'leader', 'chosen_one', 'everyman'],
            'antagonist': ['villain', 'shadow', 'destroyer', 'trickster'],
            'mentor': ['wise_old_man', 'sage', 'teacher', 'guide'],
            'ally': ['loyal_friend', 'sidekick', 'supporter', 'companion'],
            'neutral': ['innocent', 'explorer', 'regular_guy', 'observer'],
            'comic_relief': ['jester', 'fool', 'trickster', 'entertainer']
        }
        
        compatible_functions = compatibility_map.get(narrative_role, [])
        return self.narrative_function.lower() in compatible_functions
    
    def get_character_count(self) -> int:
        """Get the number of characters using this archetype."""
        return len(self.characters) if self.characters else 0
    
    def to_dict(self, include_usage_stats: bool = False) -> Dict[str, Any]:
        """Convert archetype to dictionary representation."""
        result = {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "default_traits": self.default_traits,
            "narrative_function": self.narrative_function,
            "common_motivations": self.common_motivations,
            "relationship_patterns": self.relationship_patterns,
            "growth_patterns": self.growth_patterns,
            "examples": self.examples,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_usage_stats:
            result["character_count"] = self.get_character_count()
        
        return result
    
    @classmethod
    def create_default_archetypes(cls) -> List['Archetype']:
        """Create a set of default archetypes."""
        default_archetypes = [
            {
                "name": "Hero",
                "description": "The protagonist who embarks on a journey and faces challenges",
                "narrative_function": "protagonist",
                "default_traits": [
                    {"trait": "brave", "intensity": 8, "manifestation": "Faces danger courageously"},
                    {"trait": "determined", "intensity": 9, "manifestation": "Never gives up on goals"},
                    {"trait": "compassionate", "intensity": 7, "manifestation": "Cares for others' wellbeing"}
                ],
                "common_motivations": [
                    {"type": "justice", "description": "Desire to right wrongs and protect the innocent"},
                    {"type": "self_improvement", "description": "Quest for personal growth and mastery"}
                ],
                "relationship_patterns": ["mentor-student", "loyal friendships", "romantic interest"],
                "examples": ["Luke Skywalker", "Harry Potter", "Frodo Baggins"]
            },
            {
                "name": "Mentor",
                "description": "The wise guide who helps the hero on their journey",
                "narrative_function": "mentor",
                "default_traits": [
                    {"trait": "wise", "intensity": 9, "manifestation": "Provides valuable guidance"},
                    {"trait": "patient", "intensity": 8, "manifestation": "Takes time to teach properly"},
                    {"trait": "experienced", "intensity": 9, "manifestation": "Has lived through many challenges"}
                ],
                "common_motivations": [
                    {"type": "legacy", "description": "Desire to pass on knowledge and wisdom"},
                    {"type": "redemption", "description": "Making up for past mistakes"}
                ],
                "relationship_patterns": ["teacher-student", "parental figure", "spiritual guide"],
                "examples": ["Obi-Wan Kenobi", "Dumbledore", "Gandalf"]
            },
            {
                "name": "Shadow",
                "description": "The antagonist who opposes the hero and represents their dark side",
                "narrative_function": "antagonist",
                "default_traits": [
                    {"trait": "ambitious", "intensity": 9, "manifestation": "Ruthlessly pursues power"},
                    {"trait": "cunning", "intensity": 8, "manifestation": "Uses clever schemes and manipulation"},
                    {"trait": "charismatic", "intensity": 7, "manifestation": "Attracts followers and allies"}
                ],
                "common_motivations": [
                    {"type": "power", "description": "Desire for control and dominance"},
                    {"type": "revenge", "description": "Seeking retribution for past wrongs"}
                ],
                "relationship_patterns": ["master-servant", "rivalry", "corruption of allies"],
                "examples": ["Darth Vader", "Voldemort", "Sauron"]
            }
        ]
        
        return [cls(**archetype_data) for archetype_data in default_archetypes]
    
    def __repr__(self) -> str:
        return f"<Archetype(id={self.id}, name='{self.name}', active={self.is_active})>"
