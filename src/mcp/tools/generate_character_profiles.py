"""
MCP tool for generating character profiles from scene lists and concept briefs.
Implements the Character Creator Agent specification.
"""
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import structlog

from src.services.character_service import CharacterService
from src.services.payload_service import PayloadService
from src.services.prompt_service import PromptService
from src.utils.observability import track_execution_time, emit_metric

logger = structlog.get_logger(__name__)


class GenerateCharacterProfilesTool:
    """MCP tool for generating character profiles from episode breakdown and concept brief."""
    
    def __init__(self):
        self.name = "generate_character_profiles"
        self.character_service = CharacterService()
        self.payload_service = PayloadService()
        self.prompt_service = PromptService()
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool schema for MCP registration."""
        return {
            "name": self.name,
            "description": (
                "Generate lightweight character profiles from scene lists and concept briefs. "
                "Produces 2-4 character profiles with roles, motivations, visual signatures, "
                "relationships, and continuity notes for downstream agents."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "scene_list": {
                        "type": "array",
                        "description": "List of scenes from episode breakdown",
                        "items": {
                            "type": "object",
                            "properties": {
                                "scene_number": {"type": "integer"},
                                "primary_characters": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                },
                                "secondary_characters": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "default": []
                                },
                                "goal": {"type": "string"},
                                "notes": {"type": "string", "default": ""}
                            },
                            "required": ["scene_number", "primary_characters", "goal"]
                        }
                    },
                    "concept_brief": {
                        "type": "object",
                        "description": "Project concept brief for tone and genre context",
                        "properties": {
                            "genre_tags": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "tone_keywords": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "core_conflict": {"type": "string"}
                        },
                        "required": ["genre_tags", "tone_keywords", "core_conflict"]
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Project ID for character registry lookup"
                    }
                },
                "required": ["scene_list", "concept_brief", "project_id"]
            }
        }
    
    def validate_input(self, arguments: Dict[str, Any]) -> None:
        """Validate input arguments against schema."""
        required_fields = ["scene_list", "concept_brief", "project_id"]
        
        for field in required_fields:
            if field not in arguments:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate scene_list
        if not isinstance(arguments["scene_list"], list):
            raise ValueError("scene_list must be an array")
        
        if len(arguments["scene_list"]) == 0:
            raise ValueError("scene_list cannot be empty")
        
        for i, scene in enumerate(arguments["scene_list"]):
            if not isinstance(scene, dict):
                raise ValueError(f"Scene {i} must be an object")
            
            scene_required = ["scene_number", "primary_characters", "goal"]
            for field in scene_required:
                if field not in scene:
                    raise ValueError(f"Scene {i} missing required field: {field}")
        
        # Validate concept_brief
        concept_brief = arguments["concept_brief"]
        if not isinstance(concept_brief, dict):
            raise ValueError("concept_brief must be an object")
        
        concept_required = ["genre_tags", "tone_keywords", "core_conflict"]
        for field in concept_required:
            if field not in concept_brief:
                raise ValueError(f"concept_brief missing required field: {field}")
    
    @track_execution_time("generate_character_profiles")
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute character profile generation."""
        start_time = datetime.utcnow()
        
        try:
            logger.info("Starting character profile generation", 
                       project_id=arguments["project_id"],
                       scene_count=len(arguments["scene_list"]))
            
            # Step 1: Normalize input
            normalized_scenes = self._normalize_scenes(arguments["scene_list"])
            concept_brief = arguments["concept_brief"]
            project_id = arguments["project_id"]
            
            # Step 2: Query character registry from PayloadCMS
            registry_characters = await self.payload_service.get_project_characters(project_id)
            logger.info("Retrieved registry characters", count=len(registry_characters))
            
            # Step 3: Extract and deduplicate characters
            extracted_characters = self._extract_characters_from_scenes(normalized_scenes)
            deduplicated_characters = self._deduplicate_characters(
                extracted_characters, registry_characters
            )
            
            # Step 4: Generate profiles with LLM
            character_profiles = []
            unresolved_references = []
            
            for char_info in deduplicated_characters:
                try:
                    profile = await self._generate_character_profile(
                        char_info, concept_brief, normalized_scenes
                    )
                    
                    # Check for lacking guidance - halt if found
                    if self._has_lacking_guidance(profile):
                        logger.warning("Lacking guidance detected", character=char_info["name"])
                        return {
                            "success": False,
                            "error": "lacking_guidance",
                            "message": f"Insufficient guidance for character: {char_info['name']}",
                            "character_profiles": [],
                            "unresolved_references": [char_info["name"]]
                        }
                    
                    character_profiles.append(profile)
                    
                    # Update registry asynchronously
                    asyncio.create_task(
                        self.payload_service.upsert_character(project_id, profile)
                    )
                    
                except Exception as e:
                    logger.error("Failed to generate profile", 
                               character=char_info["name"], error=str(e))
                    unresolved_references.append(char_info["name"])
            
            # Step 5: Validate output and emit metrics
            total_characters = len(character_profiles)
            unresolved_rate = len(unresolved_references) / max(1, total_characters + len(unresolved_references))
            
            await emit_metric("character_creator.profile_count", total_characters)
            await emit_metric("character_creator.unresolved_reference_rate", unresolved_rate)
            await emit_metric("character_creator.latency_ms", 
                            (datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.info("Character profile generation completed",
                       profile_count=total_characters,
                       unresolved_count=len(unresolved_references))
            
            return {
                "success": True,
                "character_profiles": character_profiles,
                "unresolved_references": unresolved_references
            }
            
        except Exception as e:
            logger.error("Character profile generation failed", error=str(e), exc_info=True)
            await emit_metric("character_creator.error_count", 1)
            
            return {
                "success": False,
                "error": str(e),
                "error_type": "generation_error",
                "character_profiles": [],
                "unresolved_references": []
            }
    
    def _normalize_scenes(self, scene_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize scene data structure."""
        normalized = []
        
        for scene in scene_list:
            normalized_scene = {
                "scene_number": scene["scene_number"],
                "primary_characters": scene["primary_characters"],
                "secondary_characters": scene.get("secondary_characters", []),
                "goal": scene["goal"],
                "notes": scene.get("notes", "")
            }
            normalized.append(normalized_scene)
        
        return normalized
    
    def _extract_characters_from_scenes(self, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique characters from scenes with their context."""
        character_map = {}
        
        for scene in scenes:
            # Process primary characters
            for char_name in scene["primary_characters"]:
                char_name = char_name.strip()
                if char_name:
                    if char_name not in character_map:
                        character_map[char_name] = {
                            "name": char_name,
                            "source_scenes": [],
                            "is_primary": True,
                            "goals": set()
                        }
                    
                    character_map[char_name]["source_scenes"].append(scene["scene_number"])
                    character_map[char_name]["goals"].add(scene["goal"])
            
            # Process secondary characters
            for char_name in scene["secondary_characters"]:
                char_name = char_name.strip()
                if char_name:
                    if char_name not in character_map:
                        character_map[char_name] = {
                            "name": char_name,
                            "source_scenes": [],
                            "is_primary": False,
                            "goals": set()
                        }
                    
                    character_map[char_name]["source_scenes"].append(scene["scene_number"])
                    character_map[char_name]["goals"].add(scene["goal"])
        
        # Convert sets to lists for JSON serialization
        for char_info in character_map.values():
            char_info["goals"] = list(char_info["goals"])
        
        return list(character_map.values())
    
    def _deduplicate_characters(self, extracted_characters: List[Dict[str, Any]], 
                              registry_characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate characters against registry with alphabetical suffixes."""
        registry_names = {char["name"].lower(): char for char in registry_characters}
        deduplicated = []
        name_counters = {}
        
        for char_info in extracted_characters:
            original_name = char_info["name"]
            base_name = original_name.strip()
            lower_name = base_name.lower()
            
            # Check if character exists in registry
            if lower_name in registry_names:
                # Use existing registry character
                registry_char = registry_names[lower_name]
                char_info["registry_id"] = registry_char.get("id")
                char_info["name"] = registry_char["name"]  # Use canonical name
                deduplicated.append(char_info)
                continue
            
            # Handle new characters with potential duplicates
            if lower_name in name_counters:
                # Generate alphabetical suffix
                counter = name_counters[lower_name]
                suffix = chr(ord('A') + counter)
                char_info["name"] = f"{base_name} {suffix}"
                name_counters[lower_name] += 1
            else:
                name_counters[lower_name] = 0
                char_info["name"] = base_name
            
            char_info["registry_id"] = None  # New character
            deduplicated.append(char_info)
        
        return deduplicated
    
    async def _generate_character_profile(self, char_info: Dict[str, Any], 
                                        concept_brief: Dict[str, Any],
                                        scenes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a character profile using LLM prompts."""
        # Determine role based on scene prominence
        role = self._determine_character_role(char_info, scenes)
        
        # Generate motivation and visual signature
        motivation = await self.prompt_service.generate_motivation(
            char_info, concept_brief, role
        )
        
        visual_signature = await self.prompt_service.generate_visual_signature(
            char_info, concept_brief, role
        )
        
        # Generate relationships if data is available
        relationships = self._generate_relationships(char_info, scenes)
        
        # Generate continuity notes
        continuity_notes = self._generate_continuity_notes(char_info, scenes)
        
        profile = {
            "name": char_info["name"],
            "role": role,
            "motivation": motivation[:50] if motivation else "",  # Enforce 50-word limit
            "visual_signature": visual_signature[:40] if visual_signature else "",  # Enforce 40-word limit
            "relationships": relationships,
            "continuity_notes": continuity_notes
        }
        
        return profile
    
    def _determine_character_role(self, char_info: Dict[str, Any], 
                                scenes: List[Dict[str, Any]]) -> str:
        """Determine character role based on scene prominence."""
        scene_count = len(char_info["source_scenes"])
        total_scenes = len(scenes)
        prominence = scene_count / total_scenes
        
        if char_info["is_primary"] and prominence >= 0.5:
            return "protagonist"
        elif prominence >= 0.3:
            return "antagonist"
        else:
            return "support"
    
    def _generate_relationships(self, char_info: Dict[str, Any], 
                              scenes: List[Dict[str, Any]]) -> List[str]:
        """Generate relationship descriptors if data is available."""
        relationships = []
        
        # For now, return empty list unless explicit guidance is available
        # This prevents speculation as per the specification
        
        return relationships
    
    def _generate_continuity_notes(self, char_info: Dict[str, Any], 
                                 scenes: List[Dict[str, Any]]) -> List[str]:
        """Generate continuity notes from scene context."""
        notes = []
        
        # Add scene-based notes
        scene_numbers = sorted(char_info["source_scenes"])
        if len(scene_numbers) > 1:
            notes.append(f"Appears in scenes: {', '.join(map(str, scene_numbers))}")
        
        # Add goal-based notes
        if char_info["goals"]:
            unique_goals = list(set(char_info["goals"]))
            if len(unique_goals) == 1:
                notes.append(f"Primary goal: {unique_goals[0][:30]}...")
            else:
                notes.append(f"Multiple goals across {len(unique_goals)} scenes")
        
        return notes
    
    def _has_lacking_guidance(self, profile: Dict[str, Any]) -> bool:
        """Check if profile contains lacking guidance indicators."""
        lacking_indicators = ["lacking_guidance"]
        
        for field in ["motivation", "visual_signature"]:
            if profile.get(field) in lacking_indicators:
                return True
        
        for note in profile.get("continuity_notes", []):
            if any(indicator in note for indicator in lacking_indicators):
                return True
        
        return False