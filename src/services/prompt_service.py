"""
Prompt service for generating character motivations and visual signatures.
Handles LLM interactions using template-based prompts.
"""
import asyncio
import json
import os
from typing import Dict, Any, List, Optional
import httpx
import structlog
from pathlib import Path

from src.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class PromptService:
    """Service for generating character attributes using LLM prompts."""
    
    def __init__(self):
        self.llm_provider_url = settings.LLM_PROVIDER_URL
        self.llm_api_key = settings.LLM_API_KEY
        self.timeout = 60.0  # Higher timeout for LLM requests
        self.client = None
        self.templates = {}
        self._load_prompt_templates()
    
    def _load_prompt_templates(self):
        """Load prompt templates from the prompts directory."""
        prompts_dir = Path(__file__).parent.parent / "prompts"
        
        try:
            # Load master_reference template
            master_ref_path = prompts_dir / "master_reference.prompt"
            if master_ref_path.exists():
                self.templates["master_reference"] = master_ref_path.read_text()
                logger.info("Loaded master_reference prompt template")
            else:
                # Create default template if file doesn't exist
                self.templates["master_reference"] = self._get_default_master_reference_template()
                logger.info("Using default master_reference prompt template")
            
            # Load additional templates if they exist
            for template_file in prompts_dir.glob("*.prompt"):
                template_name = template_file.stem
                if template_name != "master_reference":
                    self.templates[template_name] = template_file.read_text()
                    logger.info(f"Loaded {template_name} prompt template")
                    
        except Exception as e:
            logger.warning("Error loading prompt templates", error=str(e))
            # Fallback to default template
            self.templates["master_reference"] = self._get_default_master_reference_template()
    
    def _get_default_master_reference_template(self) -> str:
        """Get the default master_reference prompt template."""
        return """You are generating a concise character anchor for storyboard and image teams.
Context: {genre_tags}, tone {tone_keywords}, conflict {core_conflict}.
Character: {name}, scenes {scene_numbers}, role {role}.

Based on the character's appearances and goals: {goals}

Provide motivation (<=50 words) and visual signature (<=40 words) using neutral, bias-free descriptors.

If you lack sufficient information to generate meaningful content, respond with exactly "lacking_guidance" for the respective field.

Format your response as JSON:
{
    "motivation": "string (<=50 words or 'lacking_guidance')",
    "visual_signature": "string (<=40 words or 'lacking_guidance')"
}"""
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for LLM requests."""
        if self.client is None:
            headers = {}
            if self.llm_api_key:
                headers["Authorization"] = f"Bearer {self.llm_api_key}"
            headers["Content-Type"] = "application/json"
            
            self.client = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout
            )
        return self.client
    
    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def generate_motivation(self, char_info: Dict[str, Any], 
                                concept_brief: Dict[str, Any], 
                                role: str) -> str:
        """
        Generate character motivation using LLM.
        
        Args:
            char_info: Character information including name, goals, source_scenes
            concept_brief: Project concept brief with genre_tags, tone_keywords, core_conflict
            role: Character role (protagonist, antagonist, support)
            
        Returns:
            Generated motivation string (<=50 words) or "lacking_guidance"
        """
        try:
            result = await self._generate_character_attributes(char_info, concept_brief, role)
            return result.get("motivation", "lacking_guidance")
        except Exception as e:
            logger.error("Error generating motivation", 
                        character=char_info.get("name"), 
                        error=str(e))
            return "lacking_guidance"
    
    async def generate_visual_signature(self, char_info: Dict[str, Any], 
                                      concept_brief: Dict[str, Any], 
                                      role: str) -> str:
        """
        Generate character visual signature using LLM.
        
        Args:
            char_info: Character information including name, goals, source_scenes
            concept_brief: Project concept brief with genre_tags, tone_keywords, core_conflict
            role: Character role (protagonist, antagonist, support)
            
        Returns:
            Generated visual signature string (<=40 words) or "lacking_guidance"
        """
        try:
            result = await self._generate_character_attributes(char_info, concept_brief, role)
            return result.get("visual_signature", "lacking_guidance")
        except Exception as e:
            logger.error("Error generating visual signature", 
                        character=char_info.get("name"), 
                        error=str(e))
            return "lacking_guidance"
    
    async def _generate_character_attributes(self, char_info: Dict[str, Any], 
                                           concept_brief: Dict[str, Any], 
                                           role: str) -> Dict[str, str]:
        """
        Generate both motivation and visual signature in a single LLM call.
        
        Args:
            char_info: Character information
            concept_brief: Project concept brief  
            role: Character role
            
        Returns:
            Dictionary with motivation and visual_signature
        """
        template = self.templates.get("master_reference", self._get_default_master_reference_template())
        
        # Prepare template variables
        template_vars = {
            "genre_tags": ", ".join(concept_brief.get("genre_tags", [])),
            "tone_keywords": ", ".join(concept_brief.get("tone_keywords", [])),
            "core_conflict": concept_brief.get("core_conflict", ""),
            "name": char_info.get("name", ""),
            "scene_numbers": ", ".join(map(str, char_info.get("source_scenes", []))),
            "role": role,
            "goals": "; ".join(char_info.get("goals", []))
        }
        
        # Fill template
        prompt = template.format(**template_vars)
        
        logger.info("Generating character attributes", 
                   character=char_info.get("name"), 
                   role=role)
        
        # Make LLM request
        result = await self._make_llm_request(prompt)
        
        # Parse and validate response
        parsed_result = self._parse_llm_response(result, char_info.get("name", "unknown"))
        
        return parsed_result
    
    async def _make_llm_request(self, prompt: str) -> str:
        """
        Make a request to the LLM provider.
        
        Args:
            prompt: The formatted prompt to send
            
        Returns:
            LLM response text
        """
        if not self.llm_provider_url:
            logger.warning("No LLM provider URL configured, using mock response")
            return self._get_mock_response()
        
        try:
            client = await self._get_client()
            
            # Prepare request payload (adjust based on your LLM provider)
            payload = {
                "model": settings.LLM_MODEL_NAME or "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 200,
                "temperature": 0.7
            }
            
            response = await client.post(self.llm_provider_url, json=payload)
            response.raise_for_status()
            
            response_data = response.json()
            
            # Extract response based on provider format
            if "choices" in response_data and len(response_data["choices"]) > 0:
                content = response_data["choices"][0]["message"]["content"]
                return content.strip()
            else:
                logger.error("Unexpected LLM response format", response=response_data)
                return self._get_mock_response()
                
        except httpx.HTTPError as e:
            logger.error("HTTP error making LLM request", error=str(e))
            return self._get_mock_response()
        except Exception as e:
            logger.error("Unexpected error making LLM request", error=str(e))
            return self._get_mock_response()
    
    def _get_mock_response(self) -> str:
        """Get a mock response for testing or when LLM is unavailable."""
        return json.dumps({
            "motivation": "Character driven by personal goals and external circumstances that shape their journey.",
            "visual_signature": "Distinctive appearance with recognizable features that reflect their personality and role."
        })
    
    def _parse_llm_response(self, response: str, character_name: str) -> Dict[str, str]:
        """
        Parse and validate LLM response.
        
        Args:
            response: Raw LLM response
            character_name: Character name for logging
            
        Returns:
            Parsed response with motivation and visual_signature
        """
        try:
            # Try to parse as JSON
            parsed = json.loads(response)
            
            # Validate structure
            motivation = parsed.get("motivation", "lacking_guidance")
            visual_signature = parsed.get("visual_signature", "lacking_guidance")
            
            # Enforce word limits
            if motivation != "lacking_guidance":
                motivation_words = motivation.split()
                if len(motivation_words) > 50:
                    motivation = " ".join(motivation_words[:50])
                    logger.warning("Truncated motivation to 50 words", character=character_name)
            
            if visual_signature != "lacking_guidance":
                visual_words = visual_signature.split()
                if len(visual_words) > 40:
                    visual_signature = " ".join(visual_words[:40])
                    logger.warning("Truncated visual signature to 40 words", character=character_name)
            
            return {
                "motivation": motivation,
                "visual_signature": visual_signature
            }
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON", 
                         character=character_name, 
                         response=response[:200])
            
            # Try to extract motivation and visual signature from text
            return self._extract_from_text(response)
    
    def _extract_from_text(self, text: str) -> Dict[str, str]:
        """
        Extract motivation and visual signature from unstructured text.
        
        Args:
            text: Unstructured LLM response
            
        Returns:
            Extracted motivation and visual_signature
        """
        # Simple text extraction - look for key patterns
        lines = text.split('\n')
        motivation = "lacking_guidance"
        visual_signature = "lacking_guidance"
        
        for line in lines:
            line = line.strip()
            if line.lower().startswith(('motivation:', 'driven by', 'seeks to')):
                motivation = line.split(':', 1)[-1].strip()
                # Limit to 50 words
                words = motivation.split()
                if len(words) > 50:
                    motivation = " ".join(words[:50])
            
            elif line.lower().startswith(('visual:', 'appearance:', 'looks')):
                visual_signature = line.split(':', 1)[-1].strip()
                # Limit to 40 words
                words = visual_signature.split()
                if len(words) > 40:
                    visual_signature = " ".join(words[:40])
        
        return {
            "motivation": motivation,
            "visual_signature": visual_signature
        }
    
    def get_available_templates(self) -> List[str]:
        """Get list of available prompt templates."""
        return list(self.templates.keys())
    
    def get_template(self, template_name: str) -> Optional[str]:
        """Get a specific prompt template."""
        return self.templates.get(template_name)
    
    def add_template(self, template_name: str, template_content: str):
        """Add or update a prompt template."""
        self.templates[template_name] = template_content
        logger.info(f"Added/updated prompt template: {template_name}")
    
    def __del__(self):
        """Cleanup on destruction."""
        if self.client:
            logger.warning("PromptService destroyed without proper cleanup - call close() method")