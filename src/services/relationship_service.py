"""
Relationship service with bidirectional management for MCP Character Service.
"""
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
import structlog

from src.models.relationship import Relationship, RelationshipType, RelationshipStatus
from src.models.character import Character
from src.database.connection import DatabaseError

logger = structlog.get_logger(__name__)


class RelationshipNotFoundError(Exception):
    """Raised when a relationship is not found."""
    pass


class RelationshipValidationError(Exception):
    """Raised when relationship data validation fails."""
    pass


class RelationshipService:
    """Service for relationship-related business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_relationship(self, relationship_data: Dict[str, Any]) -> Relationship:
        """Create a new relationship with bidirectional consistency."""
        logger.info("Creating new relationship", 
                   character_a=str(relationship_data.get('character_a_id')),
                   character_b=str(relationship_data.get('character_b_id')),
                   type=relationship_data.get('relationship_type'))
        
        try:
            # Validate characters exist
            character_a_id = relationship_data['character_a_id']
            character_b_id = relationship_data['character_b_id']
            
            if isinstance(character_a_id, str):
                character_a_id = uuid.UUID(character_a_id)
            if isinstance(character_b_id, str):
                character_b_id = uuid.UUID(character_b_id)
            
            # Check if characters exist
            characters_exist = await self._verify_characters_exist([character_a_id, character_b_id])
            if not characters_exist:
                raise RelationshipValidationError("One or both characters do not exist")
            
            # Check for existing relationship
            existing = await self.get_relationship_between_characters(
                character_a_id, character_b_id, relationship_data['relationship_type']
            )
            if existing:
                raise RelationshipValidationError("Relationship already exists between these characters")
            
            # Create relationship
            relationship_data['character_a_id'] = character_a_id
            relationship_data['character_b_id'] = character_b_id
            relationship = Relationship(**relationship_data)
            
            self.session.add(relationship)
            await self.session.flush()  # Get the ID without committing
            
            await self.session.commit()
            
            logger.info("Relationship created successfully", 
                       relationship_id=str(relationship.id),
                       type=relationship.relationship_type)
            return relationship
            
        except RelationshipValidationError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to create relationship", error=str(e))
            raise RelationshipValidationError(f"Failed to create relationship: {e}")
    
    async def get_relationship_by_id(self, relationship_id: uuid.UUID) -> Optional[Relationship]:
        """Get relationship by ID with related data."""
        try:
            stmt = (
                select(Relationship)
                .options(
                    selectinload(Relationship.character_a),
                    selectinload(Relationship.character_b)
                )
                .where(Relationship.id == relationship_id)
            )
            
            result = await self.session.execute(stmt)
            relationship = result.scalar_one_or_none()
            
            if relationship:
                logger.debug("Relationship retrieved", relationship_id=str(relationship_id))
            else:
                logger.debug("Relationship not found", relationship_id=str(relationship_id))
            
            return relationship
            
        except Exception as e:
            logger.error("Failed to retrieve relationship", relationship_id=str(relationship_id), error=str(e))
            raise DatabaseError(f"Failed to retrieve relationship: {e}")
    
    async def get_character_relationships(
        self,
        character_id: uuid.UUID,
        relationship_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Relationship]:
        """Get all relationships for a character."""
        logger.debug("Getting character relationships", 
                    character_id=str(character_id), 
                    type=relationship_type)
        
        try:
            # Get relationships where character is either character_a or character_b
            stmt = (
                select(Relationship)
                .options(
                    selectinload(Relationship.character_a),
                    selectinload(Relationship.character_b)
                )
                .where(
                    or_(
                        Relationship.character_a_id == character_id,
                        Relationship.character_b_id == character_id
                    )
                )
            )
            
            # Apply filters
            conditions = []
            if relationship_type:
                conditions.append(Relationship.relationship_type == relationship_type)
            if status:
                conditions.append(Relationship.status == status)
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.order_by(Relationship.created_at.desc())
            
            result = await self.session.execute(stmt)
            relationships = result.scalars().all()
            
            logger.debug("Character relationships retrieved", 
                        character_id=str(character_id), 
                        count=len(relationships))
            return list(relationships)
            
        except Exception as e:
            logger.error("Failed to get character relationships", 
                        character_id=str(character_id), error=str(e))
            raise DatabaseError(f"Failed to get character relationships: {e}")
    
    async def get_relationship_between_characters(
        self,
        character_a_id: uuid.UUID,
        character_b_id: uuid.UUID,
        relationship_type: Optional[str] = None
    ) -> Optional[Relationship]:
        """Get relationship between two specific characters."""
        try:
            stmt = select(Relationship).where(
                or_(
                    and_(
                        Relationship.character_a_id == character_a_id,
                        Relationship.character_b_id == character_b_id
                    ),
                    and_(
                        Relationship.character_a_id == character_b_id,
                        Relationship.character_b_id == character_a_id
                    )
                )
            )
            
            if relationship_type:
                stmt = stmt.where(Relationship.relationship_type == relationship_type)
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error("Failed to get relationship between characters", error=str(e))
            return None
    
    async def update_relationship(self, relationship_id: uuid.UUID, updates: Dict[str, Any]) -> Relationship:
        """Update relationship with bidirectional consistency."""
        logger.info("Updating relationship", relationship_id=str(relationship_id))
        
        try:
            # Get current relationship
            relationship = await self.get_relationship_by_id(relationship_id)
            if not relationship:
                raise RelationshipNotFoundError(f"Relationship {relationship_id} not found")
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(relationship, key) and key not in ['id', 'character_a_id', 'character_b_id']:
                    setattr(relationship, key, value)
            
            relationship.updated_at = datetime.utcnow()
            
            await self.session.commit()
            
            logger.info("Relationship updated successfully", relationship_id=str(relationship_id))
            return relationship
            
        except RelationshipNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to update relationship", relationship_id=str(relationship_id), error=str(e))
            raise RelationshipValidationError(f"Failed to update relationship: {e}")
    
    async def delete_relationship(self, relationship_id: uuid.UUID) -> bool:
        """Delete relationship and its bidirectional counterpart."""
        logger.info("Deleting relationship", relationship_id=str(relationship_id))
        
        try:
            # Get relationship
            relationship = await self.get_relationship_by_id(relationship_id)
            if not relationship:
                return False
            
            # Delete relationship (bidirectional deletion handled by event listeners)
            await self.session.delete(relationship)
            await self.session.commit()
            
            logger.info("Relationship deleted successfully", relationship_id=str(relationship_id))
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to delete relationship", relationship_id=str(relationship_id), error=str(e))
            raise DatabaseError(f"Failed to delete relationship: {e}")
    
    async def get_relationship_network(
        self,
        character_id: uuid.UUID,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """Get relationship network for a character up to specified depth."""
        logger.debug("Getting relationship network", 
                    character_id=str(character_id), 
                    max_depth=max_depth)
        
        try:
            network = {
                "center_character_id": str(character_id),
                "relationships": [],
                "characters": {},
                "depth": max_depth
            }
            
            visited_characters = set()
            current_level = {character_id}
            
            for depth in range(max_depth):
                if not current_level:
                    break
                
                next_level = set()
                
                for char_id in current_level:
                    if char_id in visited_characters:
                        continue
                    
                    visited_characters.add(char_id)
                    
                    # Get relationships for this character
                    relationships = await self.get_character_relationships(char_id)
                    
                    for rel in relationships:
                        other_char_id = rel.get_other_character_id(char_id)
                        
                        # Add to network
                        network["relationships"].append({
                            "id": str(rel.id),
                            "from_character_id": str(char_id),
                            "to_character_id": str(other_char_id),
                            "type": rel.relationship_type,
                            "strength": rel.strength,
                            "status": rel.status,
                            "depth": depth + 1
                        })
                        
                        # Add to next level if not visited
                        if other_char_id not in visited_characters:
                            next_level.add(other_char_id)
                
                current_level = next_level
            
            # Get character details for all characters in network
            all_character_ids = list(visited_characters)
            characters = await self._get_characters_by_ids(all_character_ids)
            
            for char in characters:
                network["characters"][str(char.id)] = {
                    "id": str(char.id),
                    "name": char.name,
                    "nickname": char.nickname,
                    "narrative_role": char.narrative_role
                }
            
            logger.debug("Relationship network retrieved", 
                        character_id=str(character_id),
                        relationship_count=len(network["relationships"]),
                        character_count=len(network["characters"]))
            
            return network
            
        except Exception as e:
            logger.error("Failed to get relationship network", 
                        character_id=str(character_id), error=str(e))
            raise DatabaseError(f"Failed to get relationship network: {e}")
    
    async def validate_relationship_data(self, relationship_data: Dict[str, Any]) -> List[str]:
        """Validate relationship data and return list of errors."""
        errors = []
        
        # Required fields
        required_fields = ['character_a_id', 'character_b_id', 'relationship_type']
        for field in required_fields:
            if not relationship_data.get(field):
                errors.append(f"{field} is required")
        
        # Character IDs validation
        character_a_id = relationship_data.get('character_a_id')
        character_b_id = relationship_data.get('character_b_id')
        
        if character_a_id and character_b_id:
            # Convert to UUID if strings
            try:
                if isinstance(character_a_id, str):
                    character_a_id = uuid.UUID(character_a_id)
                if isinstance(character_b_id, str):
                    character_b_id = uuid.UUID(character_b_id)
                
                # Check for self-relationship
                if character_a_id == character_b_id:
                    errors.append("Cannot create relationship between the same character")
                
            except ValueError:
                errors.append("Invalid character ID format")
        
        # Relationship type validation
        relationship_type = relationship_data.get('relationship_type')
        if relationship_type:
            valid_types = [t.value for t in RelationshipType]
            if relationship_type not in valid_types:
                errors.append(f"Invalid relationship type. Must be one of: {valid_types}")
        
        # Status validation
        status = relationship_data.get('status')
        if status:
            valid_statuses = [s.value for s in RelationshipStatus]
            if status not in valid_statuses:
                errors.append(f"Invalid relationship status. Must be one of: {valid_statuses}")
        
        # Strength validation
        strength = relationship_data.get('strength')
        if strength is not None:
            if not isinstance(strength, int) or strength < 1 or strength > 10:
                errors.append("Relationship strength must be an integer between 1 and 10")
        
        return errors
    
    async def _verify_characters_exist(self, character_ids: List[uuid.UUID]) -> bool:
        """Verify that all characters exist."""
        try:
            stmt = select(func.count(Character.id)).where(Character.id.in_(character_ids))
            result = await self.session.execute(stmt)
            count = result.scalar()
            return count == len(character_ids)
        except Exception:
            return False
    
    async def _get_characters_by_ids(self, character_ids: List[uuid.UUID]) -> List[Character]:
        """Get characters by IDs."""
        try:
            stmt = select(Character).where(Character.id.in_(character_ids))
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception:
            return []
