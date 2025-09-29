"""
PayloadCMS service for character registry integration.
Handles character CRUD operations with Auto-Menu PayloadCMS.
"""
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
import httpx
import structlog
from datetime import datetime

from src.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class PayloadService:
    """Service for interacting with PayloadCMS character registry."""
    
    def __init__(self):
        self.base_url = settings.PAYLOAD_CMS_URL
        self.api_key = settings.PAYLOAD_CMS_API_KEY
        self.timeout = 30.0
        self.client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout
            )
        return self.client
    
    async def close(self):
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def get_project_characters(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all characters for a specific project from PayloadCMS.
        
        Args:
            project_id: The project ID to filter characters by
            
        Returns:
            List of character dictionaries with at least 'name' and 'project_id'
        """
        try:
            client = await self._get_client()
            
            # Query characters collection filtered by project_id
            params = {
                "where": {
                    "project_id": {
                        "equals": project_id
                    }
                },
                "limit": 100  # Reasonable limit for characters per project
            }
            
            logger.info("Querying PayloadCMS for characters", project_id=project_id)
            
            response = await client.get("/api/characters", params={"where": json.dumps(params["where"])})
            response.raise_for_status()
            
            data = response.json()
            characters = data.get("docs", [])
            
            logger.info("Retrieved characters from PayloadCMS", 
                       project_id=project_id, 
                       count=len(characters))
            
            # Normalize character data structure
            normalized_characters = []
            for char in characters:
                normalized_char = {
                    "id": char.get("id"),
                    "name": char.get("name", ""),
                    "project_id": char.get("project_id"),
                    "attributes": {
                        k: v for k, v in char.items() 
                        if k not in ["id", "name", "project_id", "createdAt", "updatedAt"]
                    }
                }
                normalized_characters.append(normalized_char)
            
            return normalized_characters
            
        except httpx.HTTPError as e:
            logger.error("HTTP error querying PayloadCMS", 
                        project_id=project_id, 
                        error=str(e),
                        exc_info=True)
            # Return empty list to allow processing to continue
            return []
            
        except Exception as e:
            logger.error("Unexpected error querying PayloadCMS", 
                        project_id=project_id, 
                        error=str(e),
                        exc_info=True)
            # Return empty list to allow processing to continue
            return []
    
    async def upsert_character(self, project_id: str, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create or update a character in PayloadCMS.
        
        Args:
            project_id: The project ID
            profile: Character profile data
            
        Returns:
            Created/updated character data or None if failed
        """
        try:
            client = await self._get_client()
            
            character_data = {
                "name": profile["name"],
                "project_id": project_id,
                "role": profile.get("role"),
                "motivation": profile.get("motivation"),
                "visual_signature": profile.get("visual_signature"),
                "relationships": profile.get("relationships", []),
                "continuity_notes": profile.get("continuity_notes", [])
            }
            
            # Check if character already exists
            existing_character = await self._find_character_by_name(project_id, profile["name"])
            
            if existing_character:
                # Update existing character
                character_id = existing_character["id"]
                logger.info("Updating existing character", 
                           character_id=character_id, 
                           name=profile["name"])
                
                response = await client.patch(f"/api/characters/{character_id}", 
                                            json=character_data)
                response.raise_for_status()
                
                updated_character = response.json()
                logger.info("Character updated successfully", 
                           character_id=character_id, 
                           name=profile["name"])
                
                return updated_character
            else:
                # Create new character
                logger.info("Creating new character", name=profile["name"])
                
                response = await client.post("/api/characters", json=character_data)
                response.raise_for_status()
                
                new_character = response.json()
                logger.info("Character created successfully", 
                           character_id=new_character.get("id"), 
                           name=profile["name"])
                
                return new_character
                
        except httpx.HTTPError as e:
            logger.error("HTTP error upserting character", 
                        name=profile["name"], 
                        error=str(e),
                        status_code=getattr(e.response, 'status_code', None),
                        exc_info=True)
            return None
            
        except Exception as e:
            logger.error("Unexpected error upserting character", 
                        name=profile["name"], 
                        error=str(e),
                        exc_info=True)
            return None
    
    async def _find_character_by_name(self, project_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a character by name within a project.
        
        Args:
            project_id: The project ID
            name: Character name to search for
            
        Returns:
            Character data if found, None otherwise
        """
        try:
            client = await self._get_client()
            
            params = {
                "where": {
                    "and": [
                        {
                            "project_id": {
                                "equals": project_id
                            }
                        },
                        {
                            "name": {
                                "equals": name
                            }
                        }
                    ]
                },
                "limit": 1
            }
            
            response = await client.get("/api/characters", 
                                      params={"where": json.dumps(params["where"])})
            response.raise_for_status()
            
            data = response.json()
            characters = data.get("docs", [])
            
            if characters:
                return characters[0]
            
            return None
            
        except Exception as e:
            logger.error("Error finding character by name", 
                        project_id=project_id, 
                        name=name, 
                        error=str(e))
            return None
    
    async def create_character_collection_if_not_exists(self):
        """
        Ensure the characters collection exists in PayloadCMS with proper schema.
        This is a utility method for initial setup.
        """
        try:
            client = await self._get_client()
            
            # Check if collection exists by attempting to query it
            response = await client.get("/api/characters", params={"limit": 1})
            
            if response.status_code == 200:
                logger.info("Characters collection already exists")
                return True
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Characters collection does not exist - manual setup required")
                return False
            else:
                logger.error("Error checking characters collection", error=str(e))
                return False
        except Exception as e:
            logger.error("Unexpected error checking characters collection", error=str(e))
            return False
        
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on PayloadCMS connection.
        
        Returns:
            Health check results
        """
        try:
            client = await self._get_client()
            
            start_time = datetime.utcnow()
            response = await client.get("/api/characters", params={"limit": 1})
            end_time = datetime.utcnow()
            
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "response_time_ms": response_time_ms,
                    "payload_cms_url": self.base_url
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "response_time_ms": response_time_ms,
                    "payload_cms_url": self.base_url
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "payload_cms_url": self.base_url
            }
    
    def __del__(self):
        """Cleanup on destruction."""
        if self.client:
            # Note: This won't work in async context, but provides cleanup hint
            logger.warning("PayloadService destroyed without proper cleanup - call close() method")