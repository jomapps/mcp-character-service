"""
MCP tool for updating characters.
"""
import uuid
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, validator
import structlog

from src.services.character_service import CharacterService, CharacterValidationError, CharacterNotFoundError
from src.database.connection import get_database_session

logger = structlog.get_logger(__name__)


class UpdateCharacterInput(BaseModel):
    """Input schema for update_character tool."""
    character_id: str = Field(..., description="Character ID to update")
    updates: Dict[str, Any] = Field(..., description="Fields to update")
    
    @validator('character_id')
    def validate_character_id(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("Invalid character ID format")
        return v
    
    @validator('updates')
    def validate_updates(cls, v):
        if not v:
            raise ValueError("Updates dictionary cannot be empty")
        
        # Validate allowed update fields
        allowed_fields = {
            'name', 'nickname', 'age', 'gender', 'occupation', 
            'backstory', 'physical_description', 'personality_traits', 
            'emotional_state', 'narrative_role'
        }
        
        invalid_fields = set(v.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Invalid update fields: {invalid_fields}")
        
        # Validate specific field constraints
        if 'name' in v and (not v['name'] or not v['name'].strip()):
            raise ValueError("Name cannot be empty")
        
        if 'age' in v and (v['age'] < 0 or v['age'] > 200):
            raise ValueError("Age must be between 0 and 200")
        
        if 'narrative_role' in v:
            valid_roles = ["protagonist", "antagonist", "mentor", "ally", "neutral", "comic_relief"]
            if v['narrative_role'] not in valid_roles:
                raise ValueError(f"Invalid narrative role. Must be one of: {valid_roles}")
        
        return v


class UpdateCharacterOutput(BaseModel):
    """Output schema for update_character tool."""
    character_id: str = Field(..., description="Updated character ID")
    updated_fields: List[str] = Field(..., description="List of fields that were updated")
    updated_at: str = Field(..., description="Update timestamp")
    success: bool = Field(..., description="Operation success status")


class UpdateCharacterTool:
    """MCP tool for updating characters."""
    
    name = "update_character"
    description = "Update character attributes while preserving relationships and consistency"
    
    inputSchema = {
        "type": "object",
        "properties": {
            "character_id": {
                "type": "string",
                "description": "Character ID to update (UUID format)",
                "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            },
            "updates": {
                "type": "object",
                "description": "Fields to update with new values",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Character name",
                        "minLength": 1,
                        "maxLength": 100
                    },
                    "nickname": {
                        "type": "string",
                        "description": "Character nickname",
                        "maxLength": 50
                    },
                    "age": {
                        "type": "integer",
                        "description": "Character age",
                        "minimum": 0,
                        "maximum": 200
                    },
                    "gender": {
                        "type": "string",
                        "description": "Character gender",
                        "maxLength": 50
                    },
                    "occupation": {
                        "type": "string",
                        "description": "Character occupation",
                        "maxLength": 100
                    },
                    "backstory": {
                        "type": "string",
                        "description": "Character backstory",
                        "maxLength": 2000
                    },
                    "physical_description": {
                        "type": "string",
                        "description": "Physical description",
                        "maxLength": 1000
                    },
                    "personality_traits": {
                        "type": "object",
                        "description": "Personality traits structure"
                    },
                    "emotional_state": {
                        "type": "object",
                        "description": "Current emotional state"
                    },
                    "narrative_role": {
                        "type": "string",
                        "description": "Narrative role",
                        "enum": ["protagonist", "antagonist", "mentor", "ally", "neutral", "comic_relief"]
                    }
                },
                "minProperties": 1
            }
        },
        "required": ["character_id", "updates"]
    }
    
    outputSchema = {
        "type": "object",
        "properties": {
            "character_id": {
                "type": "string",
                "description": "Updated character ID"
            },
            "updated_fields": {
                "type": "array",
                "description": "List of fields that were updated",
                "items": {"type": "string"}
            },
            "updated_at": {
                "type": "string",
                "description": "Update timestamp in ISO format"
            },
            "success": {
                "type": "boolean",
                "description": "Operation success status"
            }
        },
        "required": ["character_id", "updated_fields", "updated_at", "success"]
    }
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        try:
            UpdateCharacterInput(**data)
            return True
        except Exception as e:
            logger.error("Input validation failed", error=str(e))
            raise ValueError(f"Invalid input: {e}")
    
    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute character update."""
        logger.info("Executing update_character tool", 
                   character_id=data.get('character_id'))
        
        try:
            # Validate input
            input_data = UpdateCharacterInput(**data)
            character_id = uuid.UUID(input_data.character_id)
            
            # Update character using service
            async with get_database_session() as session:
                character_service = CharacterService(session)
                
                # Perform update
                updated_character = await character_service.update_character(
                    character_id=character_id,
                    updates=input_data.updates
                )
                
                # Prepare response
                response = UpdateCharacterOutput(
                    character_id=str(updated_character.id),
                    updated_fields=list(input_data.updates.keys()),
                    updated_at=updated_character.updated_at.isoformat(),
                    success=True
                )
                
                logger.info("Character updated successfully", 
                           character_id=str(character_id),
                           updated_fields=list(input_data.updates.keys()))
                
                return response.dict()
                
        except CharacterNotFoundError as e:
            logger.error("Character not found", character_id=data.get('character_id'))
            return {
                "success": False,
                "error": str(e),
                "error_type": "not_found_error"
            }
        except CharacterValidationError as e:
            logger.error("Character validation failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_type": "validation_error"
            }
        except Exception as e:
            logger.error("Character update failed", error=str(e))
            return {
                "success": False,
                "error": f"Character update failed: {e}",
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
