"""
MCP tool for retrieving characters.
"""
import uuid
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field, validator
import structlog

from src.services.character_service import CharacterService
from src.database.connection import get_database_session

logger = structlog.get_logger(__name__)


class GetCharacterInput(BaseModel):
    """Input schema for get_character tool."""
    character_id: str = Field(..., description="Character ID to retrieve")
    
    @validator('character_id')
    def validate_character_id(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("Invalid character ID format")
        return v


class GetCharacterOutput(BaseModel):
    """Output schema for get_character tool."""
    character: Optional[Dict[str, Any]] = Field(None, description="Character data")
    success: bool = Field(..., description="Operation success status")


class GetCharacterTool:
    """MCP tool for retrieving characters."""
    
    name = "get_character"
    description = "Retrieve a character by ID with complete profile information"
    
    inputSchema = {
        "type": "object",
        "properties": {
            "character_id": {
                "type": "string",
                "description": "Character ID to retrieve (UUID format)",
                "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            }
        },
        "required": ["character_id"]
    }
    
    outputSchema = {
        "type": "object",
        "properties": {
            "character": {
                "type": "object",
                "description": "Character data",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "nickname": {"type": ["string", "null"]},
                    "age": {"type": ["integer", "null"]},
                    "gender": {"type": ["string", "null"]},
                    "occupation": {"type": ["string", "null"]},
                    "backstory": {"type": ["string", "null"]},
                    "physical_description": {"type": ["string", "null"]},
                    "personality_traits": {"type": ["object", "null"]},
                    "emotional_state": {"type": ["object", "null"]},
                    "narrative_role": {"type": ["string", "null"]},
                    "archetype_id": {"type": ["string", "null"]},
                    "created_at": {"type": "string"},
                    "updated_at": {"type": "string"}
                },
                "required": ["id", "name", "created_at"]
            },
            "success": {
                "type": "boolean",
                "description": "Operation success status"
            }
        },
        "required": ["success"]
    }
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        try:
            GetCharacterInput(**data)
            return True
        except Exception as e:
            logger.error("Input validation failed", error=str(e))
            raise ValueError(f"Invalid input: {e}")
    
    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute character retrieval."""
        logger.info("Executing get_character tool", character_id=data.get('character_id'))
        
        try:
            # Validate input
            input_data = GetCharacterInput(**data)
            character_id = uuid.UUID(input_data.character_id)
            
            # Retrieve character using service
            async with get_database_session() as session:
                character_service = CharacterService(session)
                character = await character_service.get_character_by_id(character_id)
                
                if character:
                    # Convert character to dict
                    character_dict = character.to_dict()
                    
                    # Add personality details if available
                    if character.personality:
                        personality_dict = character.personality.to_dict()
                        character_dict.update({
                            "personality_details": {
                                "dominant_traits": personality_dict.get("dominant_traits"),
                                "secondary_traits": personality_dict.get("secondary_traits"),
                                "motivations": personality_dict.get("motivations"),
                                "fears": personality_dict.get("fears"),
                                "values": personality_dict.get("values"),
                                "behavioral_patterns": personality_dict.get("behavioral_patterns"),
                                "growth_arc": personality_dict.get("growth_arc"),
                                "psychological_profile": personality_dict.get("psychological_profile")
                            }
                        })
                    
                    # Add archetype details if available
                    if character.archetype:
                        archetype_dict = character.archetype.to_dict()
                        character_dict["archetype_details"] = {
                            "name": archetype_dict.get("name"),
                            "description": archetype_dict.get("description"),
                            "narrative_function": archetype_dict.get("narrative_function")
                        }
                    
                    response = GetCharacterOutput(
                        character=character_dict,
                        success=True
                    )
                    
                    logger.info("Character retrieved successfully", 
                               character_id=str(character_id),
                               name=character.name)
                    
                    return response.dict()
                else:
                    logger.info("Character not found", character_id=str(character_id))
                    return {
                        "character": None,
                        "success": False,
                        "error": "Character not found",
                        "error_type": "not_found"
                    }
                    
        except ValueError as e:
            logger.error("Character retrieval validation failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_type": "validation_error"
            }
        except Exception as e:
            logger.error("Character retrieval failed", error=str(e))
            return {
                "success": False,
                "error": f"Character retrieval failed: {e}",
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
