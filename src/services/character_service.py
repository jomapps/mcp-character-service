"""
Character service with business logic for MCP Character Service.
"""
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_, and_
from sqlalchemy.orm import selectinload
import structlog

from src.models.character import Character, NarrativeRole
from src.models.personality import Personality
from src.models.archetype import Archetype
from src.database.connection import DatabaseError

logger = structlog.get_logger(__name__)


class CharacterNotFoundError(Exception):
    """Raised when a character is not found."""
    pass


class CharacterValidationError(Exception):
    """Raised when character data validation fails."""
    pass


class CharacterService:
    """Service for character-related business logic."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_character(self, character_data: Dict[str, Any]) -> Character:
        """Create a new character with validation and archetype application."""
        logger.info("Creating new character", name=character_data.get('name'))
        
        try:
            # Apply archetype defaults if archetype_id is provided
            if character_data.get('archetype_id'):
                archetype = await self.get_archetype_by_id(character_data['archetype_id'])
                if archetype and archetype.is_active:
                    character_data = archetype.apply_to_character_data(character_data)
            
            # Create character instance
            character = Character(**character_data)
            
            # Add to session
            self.session.add(character)
            await self.session.flush()  # Get the ID without committing
            
            # Create personality profile if personality traits are provided
            if character_data.get('personality_traits'):
                personality_data = {
                    'character_id': character.id,
                    'dominant_traits': character_data['personality_traits'].get('dominant_traits', [])
                }
                personality = Personality(**personality_data)
                self.session.add(personality)
            
            await self.session.commit()
            
            logger.info("Character created successfully", character_id=str(character.id), name=character.name)
            return character
            
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to create character", error=str(e), name=character_data.get('name'))
            raise CharacterValidationError(f"Failed to create character: {e}")
    
    async def get_character_by_id(self, character_id: uuid.UUID) -> Optional[Character]:
        """Get character by ID with related data."""
        try:
            stmt = (
                select(Character)
                .options(
                    selectinload(Character.personality),
                    selectinload(Character.archetype)
                )
                .where(Character.id == character_id)
            )
            
            result = await self.session.execute(stmt)
            character = result.scalar_one_or_none()
            
            if character:
                logger.debug("Character retrieved", character_id=str(character_id), name=character.name)
            else:
                logger.debug("Character not found", character_id=str(character_id))
            
            return character
            
        except Exception as e:
            logger.error("Failed to retrieve character", character_id=str(character_id), error=str(e))
            raise DatabaseError(f"Failed to retrieve character: {e}")
    
    async def get_characters_by_ids(self, character_ids: List[uuid.UUID]) -> List[Character]:
        """Get multiple characters by IDs."""
        try:
            stmt = (
                select(Character)
                .options(
                    selectinload(Character.personality),
                    selectinload(Character.archetype)
                )
                .where(Character.id.in_(character_ids))
            )
            
            result = await self.session.execute(stmt)
            characters = result.scalars().all()
            
            logger.debug("Retrieved multiple characters", count=len(characters))
            return list(characters)
            
        except Exception as e:
            logger.error("Failed to retrieve characters", error=str(e))
            raise DatabaseError(f"Failed to retrieve characters: {e}")
    
    async def update_character(self, character_id: uuid.UUID, updates: Dict[str, Any]) -> Character:
        """Update character with optimistic locking."""
        logger.info("Updating character", character_id=str(character_id))
        
        try:
            # Get current character
            character = await self.get_character_by_id(character_id)
            if not character:
                raise CharacterNotFoundError(f"Character {character_id} not found")
            
            # Store current version for optimistic locking
            current_version = character.version
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(character, key):
                    setattr(character, key, value)
            
            # Increment version
            character.version = current_version + 1
            character.updated_at = datetime.utcnow()
            
            # Update personality if personality_traits are provided
            if 'personality_traits' in updates:
                if character.personality:
                    character.personality.dominant_traits = updates['personality_traits'].get('dominant_traits', [])
                    character.personality.updated_at = datetime.utcnow()
                else:
                    # Create new personality
                    personality_data = {
                        'character_id': character.id,
                        'dominant_traits': updates['personality_traits'].get('dominant_traits', [])
                    }
                    personality = Personality(**personality_data)
                    self.session.add(personality)
            
            await self.session.commit()
            
            logger.info("Character updated successfully", character_id=str(character_id))
            return character
            
        except CharacterNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to update character", character_id=str(character_id), error=str(e))
            raise CharacterValidationError(f"Failed to update character: {e}")
    
    async def delete_character(self, character_id: uuid.UUID) -> bool:
        """Delete character and related data."""
        logger.info("Deleting character", character_id=str(character_id))
        
        try:
            # Check if character exists
            character = await self.get_character_by_id(character_id)
            if not character:
                return False
            
            # Delete character (cascades to personality and relationships)
            await self.session.delete(character)
            await self.session.commit()
            
            logger.info("Character deleted successfully", character_id=str(character_id))
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to delete character", character_id=str(character_id), error=str(e))
            raise DatabaseError(f"Failed to delete character: {e}")
    
    async def search_characters(
        self,
        query: Optional[str] = None,
        narrative_role: Optional[str] = None,
        personality_traits: Optional[List[str]] = None,
        archetype_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Character]:
        """Search characters with various filters."""
        logger.debug("Searching characters", query=query, narrative_role=narrative_role, limit=limit, offset=offset)
        
        try:
            stmt = select(Character).options(
                selectinload(Character.personality),
                selectinload(Character.archetype)
            )
            
            # Apply filters
            conditions = []
            
            if query:
                # Search in name, nickname, occupation, and backstory
                search_conditions = [
                    Character.name.ilike(f"%{query}%"),
                    Character.nickname.ilike(f"%{query}%"),
                    Character.occupation.ilike(f"%{query}%"),
                    Character.backstory.ilike(f"%{query}%")
                ]
                conditions.append(or_(*search_conditions))
            
            if narrative_role:
                conditions.append(Character.narrative_role == narrative_role)
            
            if archetype_id:
                conditions.append(Character.archetype_id == archetype_id)
            
            if personality_traits:
                # Search in personality traits JSON
                for trait in personality_traits:
                    conditions.append(
                        Character.personality_traits.op('->>')('dominant_traits').ilike(f"%{trait}%")
                    )
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            # Apply ordering, limit, and offset
            stmt = stmt.order_by(Character.created_at.desc()).limit(limit).offset(offset)
            
            result = await self.session.execute(stmt)
            characters = result.scalars().all()
            
            logger.debug("Character search completed", count=len(characters))
            return list(characters)
            
        except Exception as e:
            logger.error("Failed to search characters", error=str(e))
            raise DatabaseError(f"Failed to search characters: {e}")
    
    async def get_character_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get total count of characters matching filters."""
        try:
            stmt = select(func.count(Character.id))
            
            if filters:
                conditions = []
                
                if filters.get('narrative_role'):
                    conditions.append(Character.narrative_role == filters['narrative_role'])
                
                if filters.get('archetype_id'):
                    conditions.append(Character.archetype_id == filters['archetype_id'])
                
                if conditions:
                    stmt = stmt.where(and_(*conditions))
            
            result = await self.session.execute(stmt)
            count = result.scalar()
            
            return count or 0
            
        except Exception as e:
            logger.error("Failed to get character count", error=str(e))
            raise DatabaseError(f"Failed to get character count: {e}")
    
    async def get_archetype_by_id(self, archetype_id: uuid.UUID) -> Optional[Archetype]:
        """Get archetype by ID."""
        try:
            stmt = select(Archetype).where(Archetype.id == archetype_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to retrieve archetype", archetype_id=str(archetype_id), error=str(e))
            return None
    
    async def validate_character_data(self, character_data: Dict[str, Any]) -> List[str]:
        """Validate character data and return list of errors."""
        errors = []
        
        # Required fields
        if not character_data.get('name'):
            errors.append("Character name is required")
        
        # Name length
        if character_data.get('name') and len(character_data['name']) > 100:
            errors.append("Character name cannot exceed 100 characters")
        
        # Age validation
        age = character_data.get('age')
        if age is not None:
            if not isinstance(age, int) or age < 0 or age > 200:
                errors.append("Character age must be between 0 and 200")
        
        # Narrative role validation
        narrative_role = character_data.get('narrative_role')
        if narrative_role:
            valid_roles = [role.value for role in NarrativeRole]
            if narrative_role not in valid_roles:
                errors.append(f"Invalid narrative role. Must be one of: {valid_roles}")
        
        # Archetype validation
        archetype_id = character_data.get('archetype_id')
        if archetype_id:
            try:
                archetype_uuid = uuid.UUID(archetype_id) if isinstance(archetype_id, str) else archetype_id
                archetype = await self.get_archetype_by_id(archetype_uuid)
                if not archetype or not archetype.is_active:
                    errors.append("Invalid or inactive archetype")
            except ValueError:
                errors.append("Invalid archetype ID format")
        
        return errors
