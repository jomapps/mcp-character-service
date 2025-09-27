"""
MCP tool for creating relationships between characters.
"""
import uuid
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field, validator
import structlog

from src.services.relationship_service import RelationshipService, RelationshipValidationError
from src.database.connection import get_database_session

logger = structlog.get_logger(__name__)


class CreateRelationshipInput(BaseModel):
    """Input schema for create_relationship tool."""
    character_a_id: str = Field(..., description="First character ID")
    character_b_id: str = Field(..., description="Second character ID")
    relationship_type: str = Field(..., description="Type of relationship")
    strength: Optional[int] = Field(None, ge=1, le=10, description="Relationship strength (1-10)")
    status: Optional[str] = Field("active", description="Relationship status")
    history: Optional[str] = Field(None, description="Relationship history")
    is_mutual: Optional[bool] = Field(True, description="Whether relationship is bidirectional")
    
    @validator('character_a_id', 'character_b_id')
    def validate_character_ids(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("Invalid character ID format")
        return v
    
    @validator('relationship_type')
    def validate_relationship_type(cls, v):
        valid_types = ["family", "romantic", "friendship", "professional", "adversarial", "mentor"]
        if v not in valid_types:
            raise ValueError(f"Invalid relationship type. Must be one of: {valid_types}")
        return v
    
    @validator('status')
    def validate_status(cls, v):
        if v:
            valid_statuses = ["active", "inactive", "complicated", "developing"]
            if v not in valid_statuses:
                raise ValueError(f"Invalid relationship status. Must be one of: {valid_statuses}")
        return v
    
    @validator('character_b_id')
    def validate_different_characters(cls, v, values):
        """Validate that character IDs are different."""
        if 'character_a_id' in values and v == values['character_a_id']:
            raise ValueError("Characters cannot have relationships with themselves")
        return v
        if self.character_a_id == self.character_b_id:
            raise ValueError("Cannot create relationship between the same character")


class CreateRelationshipOutput(BaseModel):
    """Output schema for create_relationship tool."""
    relationship_id: str = Field(..., description="Created relationship ID")
    character_a_id: str = Field(..., description="First character ID")
    character_b_id: str = Field(..., description="Second character ID")
    relationship_type: str = Field(..., description="Relationship type")
    created_at: str = Field(..., description="Creation timestamp")
    success: bool = Field(..., description="Operation success status")


class CreateRelationshipTool:
    """MCP tool for creating relationships between characters."""
    
    name = "create_relationship"
    description = "Create a relationship between two characters"
    
    inputSchema = {
        "type": "object",
        "properties": {
            "character_a_id": {
                "type": "string",
                "description": "First character ID (UUID format)",
                "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            },
            "character_b_id": {
                "type": "string",
                "description": "Second character ID (UUID format)",
                "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            },
            "relationship_type": {
                "type": "string",
                "description": "Type of relationship",
                "enum": ["family", "romantic", "friendship", "professional", "adversarial", "mentor"]
            },
            "strength": {
                "type": "integer",
                "description": "Relationship strength (1-10, optional)",
                "minimum": 1,
                "maximum": 10
            },
            "status": {
                "type": "string",
                "description": "Relationship status (default: active)",
                "enum": ["active", "inactive", "complicated", "developing"],
                "default": "active"
            },
            "history": {
                "type": "string",
                "description": "Relationship history (optional)"
            },
            "is_mutual": {
                "type": "boolean",
                "description": "Whether relationship is bidirectional (default: true)",
                "default": True
            }
        },
        "required": ["character_a_id", "character_b_id", "relationship_type"]
    }
    
    outputSchema = {
        "type": "object",
        "properties": {
            "relationship_id": {
                "type": "string",
                "description": "Created relationship ID"
            },
            "character_a_id": {
                "type": "string",
                "description": "First character ID"
            },
            "character_b_id": {
                "type": "string",
                "description": "Second character ID"
            },
            "relationship_type": {
                "type": "string",
                "description": "Relationship type"
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
        "required": ["relationship_id", "character_a_id", "character_b_id", "relationship_type", "created_at", "success"]
    }
    
    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        try:
            input_data = CreateRelationshipInput(**data)
            input_data.validate_different_characters()
            return True
        except Exception as e:
            logger.error("Input validation failed", error=str(e))
            raise ValueError(f"Invalid input: {e}")
    
    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute relationship creation."""
        logger.info("Executing create_relationship tool", 
                   character_a=data.get('character_a_id'),
                   character_b=data.get('character_b_id'),
                   type=data.get('relationship_type'))
        
        try:
            # Validate input
            input_data = CreateRelationshipInput(**data)
            input_data.validate_different_characters()
            
            # Convert to dict for service
            relationship_data = input_data.dict(exclude_none=True)
            
            # Convert character IDs to UUIDs
            relationship_data['character_a_id'] = uuid.UUID(relationship_data['character_a_id'])
            relationship_data['character_b_id'] = uuid.UUID(relationship_data['character_b_id'])
            
            # Create relationship using service
            async with get_database_session() as session:
                relationship_service = RelationshipService(session)
                relationship = await relationship_service.create_relationship(relationship_data)
                
                # Prepare response
                response = CreateRelationshipOutput(
                    relationship_id=str(relationship.id),
                    character_a_id=str(relationship.character_a_id),
                    character_b_id=str(relationship.character_b_id),
                    relationship_type=relationship.relationship_type,
                    created_at=relationship.created_at.isoformat(),
                    success=True
                )
                
                logger.info("Relationship created successfully", 
                           relationship_id=str(relationship.id),
                           type=relationship.relationship_type)
                
                return response.dict()
                
        except RelationshipValidationError as e:
            logger.error("Relationship validation failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_type": "validation_error"
            }
        except ValueError as e:
            logger.error("Relationship creation input validation failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_type": "validation_error"
            }
        except Exception as e:
            logger.error("Relationship creation failed", error=str(e))
            return {
                "success": False,
                "error": f"Relationship creation failed: {e}",
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
