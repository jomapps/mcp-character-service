"""
Unit tests for validation logic in Character Service.
"""
import pytest
import uuid
from datetime import datetime
from typing import Dict, Any

from pydantic import ValidationError

from src.mcp.tools.create_character import CreateCharacterInput
from src.mcp.tools.get_character import GetCharacterInput
from src.mcp.tools.search_characters import SearchCharactersInput
from src.mcp.tools.create_relationship import CreateRelationshipInput
from src.mcp.tools.get_character_relationships import GetCharacterRelationshipsInput
from src.mcp.tools.update_character import UpdateCharacterInput


class TestCreateCharacterValidation:
    """Test validation for create_character tool."""
    
    def test_valid_character_creation(self):
        """Test valid character creation input."""
        valid_data = {
            "name": "Elena Rodriguez",
            "age": 28,
            "occupation": "Detective",
            "personality_traits": {
                "dominant_traits": [
                    {"trait": "determined", "intensity": 9, "manifestation": "Never gives up"}
                ]
            },
            "narrative_role": "protagonist"
        }
        
        input_obj = CreateCharacterInput(**valid_data)
        assert input_obj.name == "Elena Rodriguez"
        assert input_obj.age == 28
        assert input_obj.narrative_role == "protagonist"
    
    def test_empty_name_validation(self):
        """Test that empty names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCharacterInput(name="")
        
        assert "Character name cannot be empty" in str(exc_info.value)
    
    def test_whitespace_name_validation(self):
        """Test that whitespace-only names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCharacterInput(name="   ")
        
        assert "Character name cannot be empty" in str(exc_info.value)
    
    def test_name_trimming(self):
        """Test that names are properly trimmed."""
        input_obj = CreateCharacterInput(name="  Elena Rodriguez  ")
        assert input_obj.name == "Elena Rodriguez"
    
    def test_age_validation(self):
        """Test age validation constraints."""
        # Valid age
        input_obj = CreateCharacterInput(name="Test", age=25)
        assert input_obj.age == 25
        
        # Invalid negative age
        with pytest.raises(ValidationError):
            CreateCharacterInput(name="Test", age=-1)
        
        # Invalid too old age
        with pytest.raises(ValidationError):
            CreateCharacterInput(name="Test", age=201)
    
    def test_invalid_archetype_id(self):
        """Test invalid archetype ID format."""
        with pytest.raises(ValidationError) as exc_info:
            CreateCharacterInput(name="Test", archetype_id="invalid-uuid")
        
        assert "Invalid archetype ID format" in str(exc_info.value)
    
    def test_valid_archetype_id(self):
        """Test valid archetype ID format."""
        valid_uuid = str(uuid.uuid4())
        input_obj = CreateCharacterInput(name="Test", archetype_id=valid_uuid)
        assert input_obj.archetype_id == valid_uuid


class TestGetCharacterValidation:
    """Test validation for get_character tool."""
    
    def test_valid_character_id(self):
        """Test valid character ID format."""
        valid_uuid = str(uuid.uuid4())
        input_obj = GetCharacterInput(character_id=valid_uuid)
        assert input_obj.character_id == valid_uuid
    
    def test_invalid_character_id(self):
        """Test invalid character ID format."""
        with pytest.raises(ValidationError) as exc_info:
            GetCharacterInput(character_id="invalid-uuid")
        
        assert "Invalid character ID format" in str(exc_info.value)


class TestSearchCharactersValidation:
    """Test validation for search_characters tool."""
    
    def test_valid_search_input(self):
        """Test valid search input."""
        input_obj = SearchCharactersInput(
            query="Elena",
            narrative_role="protagonist",
            limit=10,
            offset=0
        )
        assert input_obj.query == "Elena"
        assert input_obj.narrative_role == "protagonist"
        assert input_obj.limit == 10
    
    def test_limit_validation(self):
        """Test limit validation constraints."""
        # Valid limit
        input_obj = SearchCharactersInput(limit=50)
        assert input_obj.limit == 50
        
        # Invalid too small limit
        with pytest.raises(ValidationError):
            SearchCharactersInput(limit=0)
        
        # Invalid too large limit
        with pytest.raises(ValidationError):
            SearchCharactersInput(limit=101)
    
    def test_offset_validation(self):
        """Test offset validation constraints."""
        # Valid offset
        input_obj = SearchCharactersInput(offset=10)
        assert input_obj.offset == 10
        
        # Invalid negative offset
        with pytest.raises(ValidationError):
            SearchCharactersInput(offset=-1)
    
    def test_invalid_narrative_role(self):
        """Test invalid narrative role."""
        with pytest.raises(ValidationError):
            SearchCharactersInput(narrative_role="invalid_role")


class TestCreateRelationshipValidation:
    """Test validation for create_relationship tool."""
    
    def test_valid_relationship_creation(self):
        """Test valid relationship creation input."""
        char_a_id = str(uuid.uuid4())
        char_b_id = str(uuid.uuid4())
        
        input_obj = CreateRelationshipInput(
            character_a_id=char_a_id,
            character_b_id=char_b_id,
            relationship_type="mentor",
            strength=8
        )
        
        assert input_obj.character_a_id == char_a_id
        assert input_obj.character_b_id == char_b_id
        assert input_obj.relationship_type == "mentor"
        assert input_obj.strength == 8
    
    def test_same_character_validation(self):
        """Test that same character relationships are rejected."""
        same_id = str(uuid.uuid4())
        
        with pytest.raises(ValidationError) as exc_info:
            CreateRelationshipInput(
                character_a_id=same_id,
                character_b_id=same_id,
                relationship_type="mentor"
            )
        
        assert "Characters cannot have relationships with themselves" in str(exc_info.value)
    
    def test_strength_validation(self):
        """Test relationship strength validation."""
        char_a_id = str(uuid.uuid4())
        char_b_id = str(uuid.uuid4())
        
        # Valid strength
        input_obj = CreateRelationshipInput(
            character_a_id=char_a_id,
            character_b_id=char_b_id,
            relationship_type="mentor",
            strength=5
        )
        assert input_obj.strength == 5
        
        # Invalid too low strength
        with pytest.raises(ValidationError):
            CreateRelationshipInput(
                character_a_id=char_a_id,
                character_b_id=char_b_id,
                relationship_type="mentor",
                strength=0
            )
        
        # Invalid too high strength
        with pytest.raises(ValidationError):
            CreateRelationshipInput(
                character_a_id=char_a_id,
                character_b_id=char_b_id,
                relationship_type="mentor",
                strength=11
            )
    
    def test_invalid_relationship_type(self):
        """Test invalid relationship type."""
        char_a_id = str(uuid.uuid4())
        char_b_id = str(uuid.uuid4())
        
        with pytest.raises(ValidationError):
            CreateRelationshipInput(
                character_a_id=char_a_id,
                character_b_id=char_b_id,
                relationship_type="invalid_type"
            )


class TestGetCharacterRelationshipsValidation:
    """Test validation for get_character_relationships tool."""
    
    def test_valid_input(self):
        """Test valid input."""
        char_id = str(uuid.uuid4())
        input_obj = GetCharacterRelationshipsInput(
            character_id=char_id,
            relationship_type="mentor"
        )
        
        assert input_obj.character_id == char_id
        assert input_obj.relationship_type == "mentor"
    
    def test_invalid_character_id(self):
        """Test invalid character ID."""
        with pytest.raises(ValidationError):
            GetCharacterRelationshipsInput(character_id="invalid-uuid")
    
    def test_invalid_relationship_type(self):
        """Test invalid relationship type filter."""
        char_id = str(uuid.uuid4())
        
        with pytest.raises(ValidationError):
            GetCharacterRelationshipsInput(
                character_id=char_id,
                relationship_type="invalid_type"
            )


class TestUpdateCharacterValidation:
    """Test validation for update_character tool."""
    
    def test_valid_update(self):
        """Test valid character update."""
        char_id = str(uuid.uuid4())
        updates = {
            "name": "Updated Name",
            "age": 30,
            "narrative_role": "mentor"
        }
        
        input_obj = UpdateCharacterInput(
            character_id=char_id,
            updates=updates
        )
        
        assert input_obj.character_id == char_id
        assert input_obj.updates["name"] == "Updated Name"
        assert input_obj.updates["age"] == 30
    
    def test_empty_updates_validation(self):
        """Test that empty updates are rejected."""
        char_id = str(uuid.uuid4())
        
        with pytest.raises(ValidationError) as exc_info:
            UpdateCharacterInput(character_id=char_id, updates={})
        
        assert "Updates dictionary cannot be empty" in str(exc_info.value)
    
    def test_invalid_update_fields(self):
        """Test that invalid update fields are rejected."""
        char_id = str(uuid.uuid4())
        
        with pytest.raises(ValidationError) as exc_info:
            UpdateCharacterInput(
                character_id=char_id,
                updates={"invalid_field": "value"}
            )
        
        assert "Invalid update fields" in str(exc_info.value)
    
    def test_empty_name_update_validation(self):
        """Test that empty name updates are rejected."""
        char_id = str(uuid.uuid4())
        
        with pytest.raises(ValidationError) as exc_info:
            UpdateCharacterInput(
                character_id=char_id,
                updates={"name": ""}
            )
        
        assert "Name cannot be empty" in str(exc_info.value)
    
    def test_invalid_age_update_validation(self):
        """Test age update validation."""
        char_id = str(uuid.uuid4())
        
        # Invalid negative age
        with pytest.raises(ValidationError):
            UpdateCharacterInput(
                character_id=char_id,
                updates={"age": -1}
            )
        
        # Invalid too old age
        with pytest.raises(ValidationError):
            UpdateCharacterInput(
                character_id=char_id,
                updates={"age": 201}
            )
    
    def test_invalid_narrative_role_update(self):
        """Test invalid narrative role update."""
        char_id = str(uuid.uuid4())
        
        with pytest.raises(ValidationError):
            UpdateCharacterInput(
                character_id=char_id,
                updates={"narrative_role": "invalid_role"}
            )
