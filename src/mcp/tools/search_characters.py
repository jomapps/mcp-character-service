"""
MCP tool for searching characters.
"""
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, validator
import structlog

from src.services.search_service import SearchService
from src.database.connection import get_database_session

logger = structlog.get_logger(__name__)


class SearchCharactersInput(BaseModel):
    """Input schema for search_characters tool."""
    query: Optional[str] = Field(None, max_length=200, description="Search query")
    narrative_role: Optional[str] = Field(None, description="Filter by narrative role")
    personality_traits: Optional[List[str]] = Field(None, description="Filter by personality traits")
    limit: Optional[int] = Field(20, ge=1, le=100, description="Maximum results to return")
    offset: Optional[int] = Field(0, ge=0, description="Results offset for pagination")
    
    @validator('narrative_role')
    def validate_narrative_role(cls, v):
        if v:
            valid_roles = ["protagonist", "antagonist", "mentor", "ally", "neutral", "comic_relief"]
            if v not in valid_roles:
                raise ValueError(f"Invalid narrative role. Must be one of: {valid_roles}")
        return v
    
    @validator('personality_traits')
    def validate_personality_traits(cls, v):
        if v:
            if len(v) > 10:
                raise ValueError("Too many personality traits specified (max 10)")
            for trait in v:
                if not trait or len(trait) > 50:
                    raise ValueError("Each personality trait must be 1-50 characters")
        return v


class SearchCharactersOutput(BaseModel):
    """Output schema for search_characters tool."""
    characters: List[Dict[str, Any]] = Field(..., description="List of matching characters")
    total_count: int = Field(..., description="Total number of matching characters")
    success: bool = Field(..., description="Operation success status")


class SearchCharactersTool:
    """MCP tool for searching characters."""
    
    name = "search_characters"
    description = "Search characters with various filters and return paginated results"
    
    inputSchema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (searches name, nickname, occupation, backstory)",
                "maxLength": 200
            },
            "narrative_role": {
                "type": "string",
                "description": "Filter by narrative role",
                "enum": ["protagonist", "antagonist", "mentor", "ally", "neutral", "comic_relief"]
            },
            "personality_traits": {
                "type": "array",
                "description": "Filter by personality traits",
                "items": {
                    "type": "string",
                    "maxLength": 50
                },
                "maxItems": 10
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default: 20)",
                "minimum": 1,
                "maximum": 100,
                "default": 20
            },
            "offset": {
                "type": "integer",
                "description": "Results offset for pagination (default: 0)",
                "minimum": 0,
                "default": 0
            }
        }
    }
    
    outputSchema = {
        "type": "object",
        "properties": {
            "characters": {
                "type": "array",
                "description": "List of matching characters",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "nickname": {"type": ["string", "null"]},
                        "narrative_role": {"type": ["string", "null"]},
                        "personality_summary": {"type": ["string", "null"]},
                        "occupation": {"type": ["string", "null"]},
                        "age": {"type": ["integer", "null"]}
                    },
                    "required": ["id", "name"]
                }
            },
            "total_count": {
                "type": "integer",
                "description": "Total number of matching characters"
            },
            "success": {
                "type": "boolean",
                "description": "Operation success status"
            }
        },
        "required": ["characters", "total_count", "success"]
    }
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        try:
            SearchCharactersInput(**data)
            return True
        except Exception as e:
            logger.error("Input validation failed", error=str(e))
            raise ValueError(f"Invalid input: {e}")
    
    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute character search."""
        logger.info("Executing search_characters tool", 
                   query=data.get('query'),
                   narrative_role=data.get('narrative_role'),
                   limit=data.get('limit', 20))
        
        try:
            # Validate input
            input_data = SearchCharactersInput(**data)
            
            # Search characters using service
            async with get_database_session() as session:
                search_service = SearchService(session)
                
                characters, total_count = await search_service.search_characters(
                    query=input_data.query,
                    narrative_role=input_data.narrative_role,
                    personality_traits=input_data.personality_traits,
                    limit=input_data.limit,
                    offset=input_data.offset
                )
                
                # Convert characters to simplified format for search results
                character_results = []
                for character in characters:
                    # Generate personality summary
                    personality_summary = None
                    if character.personality_traits and character.personality_traits.get('dominant_traits'):
                        traits = character.personality_traits['dominant_traits']
                        if traits:
                            top_traits = sorted(traits, key=lambda x: x.get('intensity', 0), reverse=True)[:3]
                            trait_names = [trait.get('trait', '') for trait in top_traits]
                            personality_summary = f"Key traits: {', '.join(trait_names)}"
                    
                    character_result = {
                        "id": str(character.id),
                        "name": character.name,
                        "nickname": character.nickname,
                        "narrative_role": character.narrative_role,
                        "personality_summary": personality_summary,
                        "occupation": character.occupation,
                        "age": character.age
                    }
                    character_results.append(character_result)
                
                response = SearchCharactersOutput(
                    characters=character_results,
                    total_count=total_count,
                    success=True
                )
                
                logger.info("Character search completed successfully", 
                           count=len(character_results),
                           total_count=total_count)
                
                return response.dict()
                
        except ValueError as e:
            logger.error("Character search validation failed", error=str(e))
            return {
                "characters": [],
                "total_count": 0,
                "success": False,
                "error": str(e),
                "error_type": "validation_error"
            }
        except Exception as e:
            logger.error("Character search failed", error=str(e))
            return {
                "characters": [],
                "total_count": 0,
                "success": False,
                "error": f"Character search failed: {e}",
                "error_type": "internal_error"
            }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for MCP registration."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema,
            "outputSchema": self.outputSchema
        }
