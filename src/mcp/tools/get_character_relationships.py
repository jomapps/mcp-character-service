"""
MCP tool for retrieving character relationships.
"""
import uuid
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, validator
import structlog

from src.services.relationship_service import RelationshipService
from src.database.connection import get_database_session

logger = structlog.get_logger(__name__)


class GetCharacterRelationshipsInput(BaseModel):
    """Input schema for get_character_relationships tool."""
    character_id: str = Field(..., description="Character ID to get relationships for")
    relationship_type: Optional[str] = Field(None, description="Filter by relationship type")
    
    @validator('character_id')
    def validate_character_id(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("Invalid character ID format")
        return v
    
    @validator('relationship_type')
    def validate_relationship_type(cls, v):
        if v is not None:
            valid_types = ["family", "romantic", "friendship", "professional", "adversarial", "mentor"]
            if v not in valid_types:
                raise ValueError(f"Invalid relationship type. Must be one of: {valid_types}")
        return v


class GetCharacterRelationshipsOutput(BaseModel):
    """Output schema for get_character_relationships tool."""
    relationships: List[Dict[str, Any]] = Field(..., description="List of character relationships")
    success: bool = Field(..., description="Operation success status")


class GetCharacterRelationshipsTool:
    """MCP tool for retrieving character relationships."""
    
    name = "get_character_relationships"
    description = "Get all relationships for a specific character with optional filtering"
    
    inputSchema = {
        "type": "object",
        "properties": {
            "character_id": {
                "type": "string",
                "description": "Character ID to get relationships for (UUID format)",
                "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            },
            "relationship_type": {
                "type": "string",
                "description": "Optional filter by relationship type",
                "enum": ["family", "romantic", "friendship", "professional", "adversarial", "mentor"]
            }
        },
        "required": ["character_id"]
    }
    
    outputSchema = {
        "type": "object",
        "properties": {
            "relationships": {
                "type": "array",
                "description": "List of character relationships",
                "items": {
                    "type": "object",
                    "properties": {
                        "relationship_id": {
                            "type": "string",
                            "description": "Unique relationship identifier"
                        },
                        "related_character": {
                            "type": "object",
                            "description": "Information about the related character",
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "nickname": {"type": "string"}
                            }
                        },
                        "relationship_type": {
                            "type": "string",
                            "description": "Type of relationship"
                        },
                        "strength": {
                            "type": "integer",
                            "description": "Relationship strength (1-10)"
                        },
                        "status": {
                            "type": "string",
                            "description": "Current relationship status"
                        },
                        "history": {
                            "type": "string",
                            "description": "Relationship development history"
                        },
                        "is_mutual": {
                            "type": "boolean",
                            "description": "Whether relationship is bidirectional"
                        },
                        "created_at": {
                            "type": "string",
                            "description": "Relationship creation timestamp"
                        }
                    }
                }
            },
            "success": {
                "type": "boolean",
                "description": "Operation success status"
            }
        },
        "required": ["relationships", "success"]
    }
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        try:
            GetCharacterRelationshipsInput(**data)
            return True
        except Exception as e:
            logger.error("Input validation failed", error=str(e))
            raise ValueError(f"Invalid input: {e}")
    
    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute character relationships retrieval."""
        logger.info("Executing get_character_relationships tool", 
                   character_id=data.get('character_id'))
        
        try:
            # Validate input
            input_data = GetCharacterRelationshipsInput(**data)
            character_id = uuid.UUID(input_data.character_id)
            
            # Get relationships using service
            async with get_database_session() as session:
                relationship_service = RelationshipService(session)
                relationships = await relationship_service.get_character_relationships(
                    character_id=character_id,
                    relationship_type=input_data.relationship_type
                )
                
                # Format relationships for response
                formatted_relationships = []
                for rel in relationships:
                    # Determine which character is the "other" character
                    if rel.character_a_id == character_id:
                        other_character = rel.character_b
                    else:
                        other_character = rel.character_a
                    
                    formatted_rel = {
                        "relationship_id": str(rel.id),
                        "related_character": {
                            "id": str(other_character.id),
                            "name": other_character.name,
                            "nickname": other_character.nickname
                        },
                        "relationship_type": rel.relationship_type,
                        "strength": rel.strength,
                        "status": rel.status,
                        "history": rel.history,
                        "is_mutual": rel.is_mutual,
                        "created_at": rel.created_at.isoformat()
                    }
                    formatted_relationships.append(formatted_rel)
                
                # Prepare response
                response = GetCharacterRelationshipsOutput(
                    relationships=formatted_relationships,
                    success=True
                )
                
                logger.info("Character relationships retrieved successfully", 
                           character_id=str(character_id),
                           relationship_count=len(formatted_relationships))
                
                return response.dict()
                
        except Exception as e:
            logger.error("Character relationships retrieval failed", error=str(e))
            return {
                "relationships": [],
                "success": False,
                "error": f"Relationships retrieval failed: {e}",
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
