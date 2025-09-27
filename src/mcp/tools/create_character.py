"""
MCP tool for creating characters.
"""
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field, validator
import structlog

from src.services.character_service import CharacterService, CharacterValidationError
from src.database.connection import get_database_session

logger = structlog.get_logger(__name__)


class CreateCharacterInput(BaseModel):
    """Input schema for create_character tool."""
    name: str = Field(..., min_length=1, max_length=100, description="Character name")
    nickname: Optional[str] = Field(None, max_length=50, description="Character nickname")
    age: Optional[int] = Field(None, ge=0, le=200, description="Character age")
    gender: Optional[str] = Field(None, max_length=50, description="Character gender")
    occupation: Optional[str] = Field(None, max_length=100, description="Character occupation")
    backstory: Optional[str] = Field(None, description="Character backstory")
    physical_description: Optional[str] = Field(None, description="Physical description")
    personality_traits: Optional[Dict[str, Any]] = Field(None, description="Personality traits structure")
    emotional_state: Optional[Dict[str, Any]] = Field(None, description="Current emotional state")
    narrative_role: Optional[str] = Field(None, description="Narrative role in story")
    archetype_id: Optional[str] = Field(None, description="Archetype template ID")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Character name cannot be empty")
        return v.strip()
    
    @validator('archetype_id')
    def validate_archetype_id(cls, v):
        if v:
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError("Invalid archetype ID format")
        return v


class CreateCharacterOutput(BaseModel):
    """Output schema for create_character tool."""
    character_id: str = Field(..., description="Created character ID")
    name: str = Field(..., description="Character name")
    created_at: str = Field(..., description="Creation timestamp")
    success: bool = Field(..., description="Operation success status")


class CreateCharacterTool:
    """MCP tool for creating characters."""
    
    name = "create_character"
    description = "Create a new character with specified attributes"
    
    inputSchema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Character name (required)",
                "minLength": 1,
                "maxLength": 100
            },
            "nickname": {
                "type": "string",
                "description": "Character nickname (optional)",
                "maxLength": 50
            },
            "age": {
                "type": "integer",
                "description": "Character age (optional)",
                "minimum": 0,
                "maximum": 200
            },
            "gender": {
                "type": "string",
                "description": "Character gender (optional)",
                "maxLength": 50
            },
            "occupation": {
                "type": "string",
                "description": "Character occupation (optional)",
                "maxLength": 100
            },
            "backstory": {
                "type": "string",
                "description": "Character backstory (optional)"
            },
            "physical_description": {
                "type": "string",
                "description": "Physical description (optional)"
            },
            "personality_traits": {
                "type": "object",
                "description": "Personality traits structure (optional)",
                "properties": {
                    "dominant_traits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "trait": {"type": "string"},
                                "intensity": {"type": "integer", "minimum": 1, "maximum": 10},
                                "manifestation": {"type": "string"}
                            },
                            "required": ["trait", "intensity", "manifestation"]
                        }
                    }
                }
            },
            "emotional_state": {
                "type": "object",
                "description": "Current emotional state (optional)",
                "properties": {
                    "current_mood": {"type": "string"},
                    "stress_level": {"type": "integer", "minimum": 0, "maximum": 10},
                    "dominant_emotion": {"type": "string"}
                }
            },
            "narrative_role": {
                "type": "string",
                "description": "Narrative role (optional)",
                "enum": ["protagonist", "antagonist", "mentor", "ally", "neutral", "comic_relief"]
            },
            "archetype_id": {
                "type": "string",
                "description": "Archetype template ID (optional)"
            }
        },
        "required": ["name"]
    }
    
    outputSchema = {
        "type": "object",
        "properties": {
            "character_id": {
                "type": "string",
                "description": "Created character ID"
            },
            "name": {
                "type": "string",
                "description": "Character name"
            },
            "created_at": {
                "type": "string",
                "description": "Creation timestamp in ISO format"
            },
            "success": {
                "type": "boolean",
                "description": "Operation success status"
            }
        },
        "required": ["character_id", "name", "created_at", "success"]
    }
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        try:
            CreateCharacterInput(**data)
            return True
        except Exception as e:
            logger.error("Input validation failed", error=str(e))
            raise ValueError(f"Invalid input: {e}")
    
    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute character creation."""
        logger.info("Executing create_character tool", name=data.get('name'))
        
        try:
            # Validate input
            input_data = CreateCharacterInput(**data)
            
            # Convert to dict for service
            character_data = input_data.dict(exclude_none=True)
            
            # Convert archetype_id to UUID if provided
            if character_data.get('archetype_id'):
                character_data['archetype_id'] = uuid.UUID(character_data['archetype_id'])
            
            # Create character using service
            async with get_database_session() as session:
                character_service = CharacterService(session)
                character = await character_service.create_character(character_data)
                
                # Prepare response
                response = CreateCharacterOutput(
                    character_id=str(character.id),
                    name=character.name,
                    created_at=character.created_at.isoformat(),
                    success=True
                )
                
                logger.info("Character created successfully", 
                           character_id=str(character.id), 
                           name=character.name)
                
                return response.dict()
                
        except CharacterValidationError as e:
            logger.error("Character validation failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_type": "validation_error"
            }
        except Exception as e:
            logger.error("Character creation failed", error=str(e))
            return {
                "success": False,
                "error": f"Character creation failed: {e}",
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
