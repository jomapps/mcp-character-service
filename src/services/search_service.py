"""
Search service with optimized queries for MCP Character Service.
"""
import uuid
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.orm import selectinload
import structlog

from src.models.character import Character
from src.models.relationship import Relationship
from src.models.personality import Personality
from src.models.archetype import Archetype
from src.database.connection import DatabaseError

logger = structlog.get_logger(__name__)


class SearchService:
    """Service for optimized search operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def search_characters(
        self,
        query: Optional[str] = None,
        narrative_role: Optional[str] = None,
        personality_traits: Optional[List[str]] = None,
        archetype_id: Optional[uuid.UUID] = None,
        age_range: Optional[Tuple[int, int]] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Character], int]:
        """Search characters with various filters and return results with total count."""
        logger.debug("Searching characters", 
                    query=query, 
                    narrative_role=narrative_role, 
                    personality_traits=personality_traits,
                    limit=limit, 
                    offset=offset)
        
        try:
            # Build base query
            base_stmt = select(Character).options(
                selectinload(Character.personality),
                selectinload(Character.archetype)
            )
            
            # Build count query
            count_stmt = select(func.count(Character.id))
            
            # Apply filters to both queries
            conditions = self._build_search_conditions(
                query=query,
                narrative_role=narrative_role,
                personality_traits=personality_traits,
                archetype_id=archetype_id,
                age_range=age_range
            )
            
            if conditions:
                base_stmt = base_stmt.where(and_(*conditions))
                count_stmt = count_stmt.where(and_(*conditions))
            
            # Get total count
            count_result = await self.session.execute(count_stmt)
            total_count = count_result.scalar() or 0
            
            # Apply ordering, limit, and offset to main query
            search_stmt = base_stmt.order_by(
                self._get_search_ordering(query)
            ).limit(limit).offset(offset)
            
            # Execute search
            search_result = await self.session.execute(search_stmt)
            characters = list(search_result.scalars().all())
            
            logger.debug("Character search completed", 
                        count=len(characters), 
                        total_count=total_count)
            
            return characters, total_count
            
        except Exception as e:
            logger.error("Failed to search characters", error=str(e))
            raise DatabaseError(f"Failed to search characters: {e}")
    
    async def search_characters_by_relationship(
        self,
        character_id: uuid.UUID,
        relationship_type: Optional[str] = None,
        max_degrees: int = 2,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search characters by relationship connections."""
        logger.debug("Searching characters by relationship", 
                    character_id=str(character_id),
                    relationship_type=relationship_type,
                    max_degrees=max_degrees)
        
        try:
            # Use recursive CTE for relationship traversal
            if max_degrees == 1:
                # Simple one-degree relationship search
                stmt = (
                    select(Character, Relationship)
                    .join(
                        Relationship,
                        or_(
                            and_(Relationship.character_a_id == Character.id, 
                                 Relationship.character_b_id == character_id),
                            and_(Relationship.character_b_id == Character.id, 
                                 Relationship.character_a_id == character_id)
                        )
                    )
                    .where(Character.id != character_id)
                )
                
                if relationship_type:
                    stmt = stmt.where(Relationship.relationship_type == relationship_type)
                
                stmt = stmt.limit(limit)
                
                result = await self.session.execute(stmt)
                results = []
                
                for character, relationship in result:
                    results.append({
                        "character": character.to_dict(),
                        "relationship": relationship.to_dict(character_id),
                        "degrees": 1
                    })
                
                return results
            
            else:
                # For multi-degree searches, use a simpler approach
                # This can be optimized with recursive CTEs in production
                visited = set()
                results = []
                current_level = {character_id}
                
                for degree in range(1, max_degrees + 1):
                    if not current_level or len(results) >= limit:
                        break
                    
                    next_level = set()
                    
                    # Get relationships for current level characters
                    stmt = (
                        select(Character, Relationship)
                        .join(
                            Relationship,
                            or_(
                                and_(Relationship.character_a_id == Character.id,
                                     Relationship.character_b_id.in_(current_level)),
                                and_(Relationship.character_b_id == Character.id,
                                     Relationship.character_a_id.in_(current_level))
                            )
                        )
                        .where(~Character.id.in_(visited))
                    )
                    
                    if relationship_type:
                        stmt = stmt.where(Relationship.relationship_type == relationship_type)
                    
                    level_result = await self.session.execute(stmt)
                    
                    for character, relationship in level_result:
                        if character.id not in visited and len(results) < limit:
                            results.append({
                                "character": character.to_dict(),
                                "relationship": relationship.to_dict(),
                                "degrees": degree
                            })
                            next_level.add(character.id)
                            visited.add(character.id)
                    
                    current_level = next_level
                
                return results
            
        except Exception as e:
            logger.error("Failed to search characters by relationship", 
                        character_id=str(character_id), error=str(e))
            raise DatabaseError(f"Failed to search characters by relationship: {e}")
    
    async def search_similar_characters(
        self,
        character_id: uuid.UUID,
        similarity_factors: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find characters similar to the given character."""
        logger.debug("Searching similar characters", 
                    character_id=str(character_id),
                    similarity_factors=similarity_factors)
        
        try:
            # Get the reference character
            ref_character = await self._get_character_with_details(character_id)
            if not ref_character:
                return []
            
            similarity_factors = similarity_factors or ['narrative_role', 'personality_traits', 'archetype']
            
            # Build similarity conditions
            conditions = []
            
            if 'narrative_role' in similarity_factors and ref_character.narrative_role:
                conditions.append(Character.narrative_role == ref_character.narrative_role)
            
            if 'archetype' in similarity_factors and ref_character.archetype_id:
                conditions.append(Character.archetype_id == ref_character.archetype_id)
            
            if 'age_range' in similarity_factors and ref_character.age:
                age_range = (max(0, ref_character.age - 10), ref_character.age + 10)
                conditions.append(Character.age.between(age_range[0], age_range[1]))
            
            # Base query excluding the reference character
            stmt = (
                select(Character)
                .options(
                    selectinload(Character.personality),
                    selectinload(Character.archetype)
                )
                .where(Character.id != character_id)
            )
            
            if conditions:
                stmt = stmt.where(or_(*conditions))
            
            stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            similar_characters = list(result.scalars().all())
            
            # Calculate similarity scores
            results = []
            for char in similar_characters:
                similarity_score = self._calculate_similarity_score(
                    ref_character, char, similarity_factors
                )
                results.append({
                    "character": char.to_dict(),
                    "similarity_score": similarity_score,
                    "similarity_factors": similarity_factors
                })
            
            # Sort by similarity score
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            logger.debug("Similar characters search completed", 
                        character_id=str(character_id),
                        count=len(results))
            
            return results
            
        except Exception as e:
            logger.error("Failed to search similar characters", 
                        character_id=str(character_id), error=str(e))
            raise DatabaseError(f"Failed to search similar characters: {e}")
    
    async def get_search_suggestions(self, partial_query: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get search suggestions based on partial query."""
        logger.debug("Getting search suggestions", partial_query=partial_query)
        
        try:
            suggestions = []
            
            # Character name suggestions
            name_stmt = (
                select(Character.name)
                .where(Character.name.ilike(f"%{partial_query}%"))
                .distinct()
                .limit(limit // 2)
            )
            
            name_result = await self.session.execute(name_stmt)
            for name in name_result.scalars():
                suggestions.append({
                    "type": "character_name",
                    "value": name,
                    "display": f"Character: {name}"
                })
            
            # Occupation suggestions
            occupation_stmt = (
                select(Character.occupation)
                .where(
                    and_(
                        Character.occupation.ilike(f"%{partial_query}%"),
                        Character.occupation.isnot(None)
                    )
                )
                .distinct()
                .limit(limit // 2)
            )
            
            occupation_result = await self.session.execute(occupation_stmt)
            for occupation in occupation_result.scalars():
                suggestions.append({
                    "type": "occupation",
                    "value": occupation,
                    "display": f"Occupation: {occupation}"
                })
            
            return suggestions[:limit]
            
        except Exception as e:
            logger.error("Failed to get search suggestions", error=str(e))
            return []
    
    def _build_search_conditions(
        self,
        query: Optional[str] = None,
        narrative_role: Optional[str] = None,
        personality_traits: Optional[List[str]] = None,
        archetype_id: Optional[uuid.UUID] = None,
        age_range: Optional[Tuple[int, int]] = None
    ) -> List:
        """Build search conditions for character queries."""
        conditions = []
        
        if query:
            # Full-text search across multiple fields
            search_conditions = [
                Character.name.ilike(f"%{query}%"),
                Character.nickname.ilike(f"%{query}%"),
                Character.occupation.ilike(f"%{query}%"),
                Character.backstory.ilike(f"%{query}%"),
                Character.physical_description.ilike(f"%{query}%")
            ]
            conditions.append(or_(*search_conditions))
        
        if narrative_role:
            conditions.append(Character.narrative_role == narrative_role)
        
        if archetype_id:
            conditions.append(Character.archetype_id == archetype_id)
        
        if age_range:
            conditions.append(Character.age.between(age_range[0], age_range[1]))
        
        if personality_traits:
            # Search in personality traits JSON
            for trait in personality_traits:
                # This is a simplified version - in production, you'd want more sophisticated JSON querying
                conditions.append(
                    Character.personality_traits.op('::text').ilike(f"%{trait}%")
                )
        
        return conditions
    
    def _get_search_ordering(self, query: Optional[str]):
        """Get ordering for search results."""
        if query:
            # Prioritize exact name matches, then partial matches
            return [
                Character.name.ilike(f"{query}%").desc(),  # Starts with query
                Character.name.ilike(f"%{query}%").desc(),  # Contains query
                Character.created_at.desc()  # Most recent
            ]
        else:
            return [Character.created_at.desc()]
    
    async def _get_character_with_details(self, character_id: uuid.UUID) -> Optional[Character]:
        """Get character with all related details."""
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
            return result.scalar_one_or_none()
            
        except Exception:
            return None
    
    def _calculate_similarity_score(
        self,
        ref_character: Character,
        compare_character: Character,
        similarity_factors: List[str]
    ) -> float:
        """Calculate similarity score between two characters."""
        score = 0.0
        max_score = len(similarity_factors)
        
        if 'narrative_role' in similarity_factors:
            if ref_character.narrative_role == compare_character.narrative_role:
                score += 1.0
        
        if 'archetype' in similarity_factors:
            if ref_character.archetype_id == compare_character.archetype_id:
                score += 1.0
        
        if 'age_range' in similarity_factors and ref_character.age and compare_character.age:
            age_diff = abs(ref_character.age - compare_character.age)
            if age_diff <= 5:
                score += 1.0
            elif age_diff <= 10:
                score += 0.5
        
        if 'personality_traits' in similarity_factors:
            # Simplified personality trait comparison
            ref_traits = set()
            compare_traits = set()
            
            if ref_character.personality_traits and ref_character.personality_traits.get('dominant_traits'):
                ref_traits = {trait.get('trait', '').lower() for trait in ref_character.personality_traits['dominant_traits']}
            
            if compare_character.personality_traits and compare_character.personality_traits.get('dominant_traits'):
                compare_traits = {trait.get('trait', '').lower() for trait in compare_character.personality_traits['dominant_traits']}
            
            if ref_traits and compare_traits:
                common_traits = ref_traits.intersection(compare_traits)
                trait_similarity = len(common_traits) / max(len(ref_traits), len(compare_traits))
                score += trait_similarity
        
        return score / max_score if max_score > 0 else 0.0
