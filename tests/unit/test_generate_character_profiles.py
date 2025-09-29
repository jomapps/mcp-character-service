"""
Unit tests for generate_character_profiles tool.
"""
import pytest
import json
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any, List

from src.mcp.tools.generate_character_profiles import GenerateCharacterProfilesTool


class TestGenerateCharacterProfilesTool:
    """Test cases for GenerateCharacterProfilesTool."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.tool = GenerateCharacterProfilesTool()
        
        # Mock services
        self.tool.payload_service = AsyncMock()
        self.tool.prompt_service = AsyncMock()
        
        # Sample input data
        self.sample_scene_list = [
            {
                "scene_number": 1,
                "primary_characters": ["Rhea", "Marcus"],
                "secondary_characters": ["Guard"],
                "goal": "Escape from prison"
            },
            {
                "scene_number": 2,
                "primary_characters": ["Rhea"],
                "goal": "Find the hidden treasure"
            }
        ]
        
        self.sample_concept_brief = {
            "genre_tags": ["action", "adventure"],
            "tone_keywords": ["dramatic", "suspenseful"],
            "core_conflict": "Fight against corruption"
        }
        
        self.sample_arguments = {
            "scene_list": self.sample_scene_list,
            "concept_brief": self.sample_concept_brief,
            "project_id": "test-project-123"
        }
    
    def test_get_schema(self):
        """Test tool schema definition."""
        schema = self.tool.get_schema()
        
        assert schema["name"] == "generate_character_profiles"
        assert "description" in schema
        assert "inputSchema" in schema
        
        # Check required fields
        required_fields = schema["inputSchema"]["required"]
        assert "scene_list" in required_fields
        assert "concept_brief" in required_fields
        assert "project_id" in required_fields
    
    def test_validate_input_valid(self):
        """Test input validation with valid data."""
        # Should not raise any exception
        self.tool.validate_input(self.sample_arguments)
    
    def test_validate_input_missing_required_field(self):
        """Test input validation with missing required field."""
        invalid_args = self.sample_arguments.copy()
        del invalid_args["scene_list"]
        
        with pytest.raises(ValueError, match="Missing required field: scene_list"):
            self.tool.validate_input(invalid_args)
    
    def test_validate_input_empty_scene_list(self):
        """Test input validation with empty scene list."""
        invalid_args = self.sample_arguments.copy()
        invalid_args["scene_list"] = []
        
        with pytest.raises(ValueError, match="scene_list cannot be empty"):
            self.tool.validate_input(invalid_args)
    
    def test_validate_input_invalid_scene_structure(self):
        """Test input validation with invalid scene structure."""
        invalid_args = self.sample_arguments.copy()
        invalid_args["scene_list"] = [{"scene_number": 1}]  # Missing required fields
        
        with pytest.raises(ValueError, match="Scene 0 missing required field"):
            self.tool.validate_input(invalid_args)
    
    def test_normalize_scenes(self):
        """Test scene normalization."""
        normalized = self.tool._normalize_scenes(self.sample_scene_list)
        
        assert len(normalized) == 2
        assert normalized[0]["scene_number"] == 1
        assert normalized[0]["primary_characters"] == ["Rhea", "Marcus"]
        assert normalized[0]["secondary_characters"] == ["Guard"]
        assert normalized[1]["secondary_characters"] == []  # Default empty array
    
    def test_extract_characters_from_scenes(self):
        """Test character extraction from scenes."""
        normalized_scenes = self.tool._normalize_scenes(self.sample_scene_list)
        characters = self.tool._extract_characters_from_scenes(normalized_scenes)
        
        # Should extract 3 unique characters
        assert len(characters) == 3
        
        # Check character data structure
        character_names = [char["name"] for char in characters]
        assert "Rhea" in character_names
        assert "Marcus" in character_names
        assert "Guard" in character_names
        
        # Check Rhea appears in both scenes
        rhea = next(char for char in characters if char["name"] == "Rhea")
        assert len(rhea["source_scenes"]) == 2
        assert rhea["is_primary"] == True
    
    def test_deduplicate_characters_no_registry(self):
        """Test character deduplication with no existing registry."""
        extracted_chars = [
            {"name": "Rhea", "source_scenes": [1, 2], "is_primary": True, "goals": ["goal1"]},
            {"name": "Marcus", "source_scenes": [1], "is_primary": True, "goals": ["goal1"]}
        ]
        registry_chars = []
        
        deduplicated = self.tool._deduplicate_characters(extracted_chars, registry_chars)
        
        assert len(deduplicated) == 2
        assert all(char["registry_id"] is None for char in deduplicated)
        assert deduplicated[0]["name"] == "Rhea"
        assert deduplicated[1]["name"] == "Marcus"
    
    def test_deduplicate_characters_with_registry_match(self):
        """Test character deduplication with existing registry match."""
        extracted_chars = [
            {"name": "Rhea", "source_scenes": [1], "is_primary": True, "goals": ["goal1"]}
        ]
        registry_chars = [
            {"id": "reg-123", "name": "Rhea", "project_id": "test-project"}
        ]
        
        deduplicated = self.tool._deduplicate_characters(extracted_chars, registry_chars)
        
        assert len(deduplicated) == 1
        assert deduplicated[0]["registry_id"] == "reg-123"
        assert deduplicated[0]["name"] == "Rhea"  # Uses canonical name from registry
    
    def test_deduplicate_characters_with_duplicates(self):
        """Test character deduplication with duplicate names."""
        extracted_chars = [
            {"name": "John", "source_scenes": [1], "is_primary": True, "goals": ["goal1"]},
            {"name": "John", "source_scenes": [2], "is_primary": False, "goals": ["goal2"]},
            {"name": "John", "source_scenes": [3], "is_primary": False, "goals": ["goal3"]}
        ]
        registry_chars = []
        
        deduplicated = self.tool._deduplicate_characters(extracted_chars, registry_chars)
        
        assert len(deduplicated) == 3
        assert deduplicated[0]["name"] == "John"
        assert deduplicated[1]["name"] == "John A"
        assert deduplicated[2]["name"] == "John B"
    
    def test_determine_character_role(self):
        """Test character role determination logic."""
        scenes = [{"scene_number": i} for i in range(1, 11)]  # 10 scenes
        
        # Protagonist: primary character in >=50% scenes
        protagonist_info = {
            "source_scenes": list(range(1, 6)),  # 5 scenes = 50%
            "is_primary": True
        }
        role = self.tool._determine_character_role(protagonist_info, scenes)
        assert role == "protagonist"
        
        # Antagonist: >=30% scenes
        antagonist_info = {
            "source_scenes": list(range(1, 4)),  # 3 scenes = 30%
            "is_primary": False
        }
        role = self.tool._determine_character_role(antagonist_info, scenes)
        assert role == "antagonist"
        
        # Support: <30% scenes
        support_info = {
            "source_scenes": [1, 2],  # 2 scenes = 20%
            "is_primary": False
        }
        role = self.tool._determine_character_role(support_info, scenes)
        assert role == "support"
    
    def test_generate_relationships(self):
        """Test relationship generation (should be empty by default)."""
        char_info = {"name": "Test", "source_scenes": [1, 2]}
        scenes = [{"scene_number": 1}, {"scene_number": 2}]
        
        relationships = self.tool._generate_relationships(char_info, scenes)
        
        # Should be empty to avoid speculation per specification
        assert relationships == []
    
    def test_generate_continuity_notes(self):
        """Test continuity notes generation."""
        char_info = {
            "name": "Test",
            "source_scenes": [1, 3, 5],
            "goals": ["Save the city", "Find the truth"]
        }
        scenes = [{"scene_number": i} for i in range(1, 6)]
        
        notes = self.tool._generate_continuity_notes(char_info, scenes)
        
        assert len(notes) >= 1
        assert any("Appears in scenes: 1, 3, 5" in note for note in notes)
        assert any("Multiple goals" in note for note in notes)
    
    def test_has_lacking_guidance_true(self):
        """Test lacking guidance detection."""
        profile = {
            "motivation": "lacking_guidance",
            "visual_signature": "Some description",
            "continuity_notes": []
        }
        
        result = self.tool._has_lacking_guidance(profile)
        assert result == True
    
    def test_has_lacking_guidance_false(self):
        """Test lacking guidance detection with valid data."""
        profile = {
            "motivation": "Character wants to save the world",
            "visual_signature": "Tall person with dark hair",
            "continuity_notes": []
        }
        
        result = self.tool._has_lacking_guidance(profile)
        assert result == False
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful execution of character profile generation."""
        # Mock services
        self.tool.payload_service.get_project_characters.return_value = []
        self.tool.prompt_service.generate_motivation.return_value = "Seeks justice"
        self.tool.prompt_service.generate_visual_signature.return_value = "Tall, athletic build"
        
        with patch('src.utils.observability.emit_metric', new_callable=AsyncMock) as mock_metric:
            result = await self.tool.execute(self.sample_arguments)
        
        assert result["success"] == True
        assert "character_profiles" in result
        assert len(result["character_profiles"]) > 0
        
        # Check profile structure
        profile = result["character_profiles"][0]
        assert "name" in profile
        assert "role" in profile
        assert "motivation" in profile
        assert "visual_signature" in profile
        assert "relationships" in profile
        assert "continuity_notes" in profile
    
    @pytest.mark.asyncio
    async def test_execute_lacking_guidance(self):
        """Test execution with lacking guidance scenario."""
        # Mock services to return lacking guidance
        self.tool.payload_service.get_project_characters.return_value = []
        self.tool.prompt_service.generate_motivation.return_value = "lacking_guidance"
        self.tool.prompt_service.generate_visual_signature.return_value = "lacking_guidance"
        
        result = await self.tool.execute(self.sample_arguments)
        
        assert result["success"] == False
        assert result["error"] == "lacking_guidance"
        assert len(result["unresolved_references"]) > 0
    
    @pytest.mark.asyncio
    async def test_execute_validation_error(self):
        """Test execution with validation error."""
        invalid_args = {"scene_list": []}  # Missing required fields
        
        result = await self.tool.execute(invalid_args)
        
        assert result["success"] == False
        assert "error" in result
        assert result["error_type"] == "generation_error"