"""
Relationship model with bidirectional consistency for MCP Character Service.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, 
    UUID, JSON, ForeignKey, CheckConstraint, UniqueConstraint,
    event
)
from sqlalchemy.orm import relationship, validates, Session
from sqlalchemy.sql import func

from src.database.connection import Base


class RelationshipType(str, Enum):
    """Enumeration of relationship types."""
    FAMILY = "family"
    ROMANTIC = "romantic"
    FRIENDSHIP = "friendship"
    PROFESSIONAL = "professional"
    ADVERSARIAL = "adversarial"
    MENTOR = "mentor"


class RelationshipStatus(str, Enum):
    """Enumeration of relationship statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLICATED = "complicated"
    DEVELOPING = "developing"


class Relationship(Base):
    """Relationship model representing connections between characters."""
    
    __tablename__ = "relationships"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Character references
    character_a_id = Column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    character_b_id = Column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    
    # Relationship details
    relationship_type = Column(String(20), nullable=False, index=True)
    strength = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default=RelationshipStatus.ACTIVE.value, index=True)
    
    # Additional information
    history = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)
    is_mutual = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships to characters
    character_a = relationship("Character", foreign_keys=[character_a_id], back_populates="relationships_as_a")
    character_b = relationship("Character", foreign_keys=[character_b_id], back_populates="relationships_as_b")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('character_a_id != character_b_id', name='no_self_relationship'),
        CheckConstraint('strength IS NULL OR (strength >= 1 AND strength <= 10)', name='valid_strength_range'),
        UniqueConstraint('character_a_id', 'character_b_id', 'relationship_type', name='unique_relationship_per_type'),
    )
    
    @validates('relationship_type')
    def validate_relationship_type(self, key, rel_type):
        """Validate relationship type."""
        if rel_type is not None:
            valid_types = [t.value for t in RelationshipType]
            if rel_type not in valid_types:
                raise ValueError(f"Invalid relationship type. Must be one of: {valid_types}")
        return rel_type
    
    @validates('status')
    def validate_status(self, key, status):
        """Validate relationship status."""
        if status is not None:
            valid_statuses = [s.value for s in RelationshipStatus]
            if status not in valid_statuses:
                raise ValueError(f"Invalid relationship status. Must be one of: {valid_statuses}")
        return status
    
    @validates('strength')
    def validate_strength(self, key, strength):
        """Validate relationship strength."""
        if strength is not None:
            if strength < 1 or strength > 10:
                raise ValueError("Relationship strength must be between 1 and 10")
        return strength
    
    @validates('character_a_id', 'character_b_id')
    def validate_different_characters(self, key, character_id):
        """Validate that characters are different."""
        if key == 'character_b_id' and hasattr(self, 'character_a_id'):
            if character_id == self.character_a_id:
                raise ValueError("Cannot create relationship between the same character")
        elif key == 'character_a_id' and hasattr(self, 'character_b_id'):
            if character_id == self.character_b_id:
                raise ValueError("Cannot create relationship between the same character")
        return character_id
    
    def get_other_character_id(self, character_id: uuid.UUID) -> uuid.UUID:
        """Get the ID of the other character in this relationship."""
        if character_id == self.character_a_id:
            return self.character_b_id
        elif character_id == self.character_b_id:
            return self.character_a_id
        else:
            raise ValueError("Character ID not found in this relationship")
    
    def involves_character(self, character_id: uuid.UUID) -> bool:
        """Check if this relationship involves the specified character."""
        return character_id in (self.character_a_id, self.character_b_id)
    
    def to_dict(self, perspective_character_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Convert relationship to dictionary representation.
        
        Args:
            perspective_character_id: If provided, the relationship is presented from this character's perspective
        """
        result = {
            "id": str(self.id),
            "character_a_id": str(self.character_a_id),
            "character_b_id": str(self.character_b_id),
            "relationship_type": self.relationship_type,
            "strength": self.strength,
            "status": self.status,
            "history": self.history,
            "metadata": self.metadata,
            "is_mutual": self.is_mutual,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        # If perspective is provided, add the other character's info
        if perspective_character_id:
            try:
                other_character_id = self.get_other_character_id(perspective_character_id)
                result["other_character_id"] = str(other_character_id)
            except ValueError:
                pass  # Character not involved in this relationship
        
        return result
    
    def __repr__(self) -> str:
        return (f"<Relationship(id={self.id}, "
                f"characters={self.character_a_id}<->{self.character_b_id}, "
                f"type='{self.relationship_type}', strength={self.strength})>")


# Event listeners for bidirectional consistency
@event.listens_for(Relationship, 'after_insert')
def create_bidirectional_relationship(mapper, connection, target):
    """Create bidirectional relationship if is_mutual is True."""
    if target.is_mutual:
        # Check if reverse relationship already exists
        reverse_exists = connection.execute(
            "SELECT id FROM relationships WHERE "
            "character_a_id = %s AND character_b_id = %s AND relationship_type = %s",
            (str(target.character_b_id), str(target.character_a_id), target.relationship_type)
        ).fetchone()
        
        if not reverse_exists:
            # Create reverse relationship
            reverse_relationship = {
                'id': str(uuid.uuid4()),
                'character_a_id': str(target.character_b_id),
                'character_b_id': str(target.character_a_id),
                'relationship_type': target.relationship_type,
                'strength': target.strength,
                'status': target.status,
                'history': target.history,
                'metadata': target.metadata,
                'is_mutual': True,
                'created_at': target.created_at,
                'updated_at': target.updated_at,
            }
            
            connection.execute(
                "INSERT INTO relationships (id, character_a_id, character_b_id, "
                "relationship_type, strength, status, history, metadata, is_mutual, "
                "created_at, updated_at) VALUES "
                "(%(id)s, %(character_a_id)s, %(character_b_id)s, %(relationship_type)s, "
                "%(strength)s, %(status)s, %(history)s, %(metadata)s, %(is_mutual)s, "
                "%(created_at)s, %(updated_at)s)",
                reverse_relationship
            )


@event.listens_for(Relationship, 'after_update')
def update_bidirectional_relationship(mapper, connection, target):
    """Update bidirectional relationship if is_mutual is True."""
    if target.is_mutual:
        # Update reverse relationship
        connection.execute(
            "UPDATE relationships SET "
            "strength = %s, status = %s, history = %s, metadata = %s, updated_at = %s "
            "WHERE character_a_id = %s AND character_b_id = %s AND relationship_type = %s",
            (target.strength, target.status, target.history, target.metadata, 
             target.updated_at, str(target.character_b_id), str(target.character_a_id), 
             target.relationship_type)
        )


@event.listens_for(Relationship, 'after_delete')
def delete_bidirectional_relationship(mapper, connection, target):
    """Delete bidirectional relationship if is_mutual was True."""
    if target.is_mutual:
        # Delete reverse relationship
        connection.execute(
            "DELETE FROM relationships WHERE "
            "character_a_id = %s AND character_b_id = %s AND relationship_type = %s",
            (str(target.character_b_id), str(target.character_a_id), target.relationship_type)
        )
