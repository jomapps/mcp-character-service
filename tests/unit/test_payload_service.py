"""
Unit tests for PayloadCMS service.
"""
import pytest
import json
from unittest.mock import AsyncMock, Mock, patch
import httpx

from src.services.payload_service import PayloadService


class TestPayloadService:
    """Test cases for PayloadService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        with patch('src.services.payload_service.get_settings') as mock_settings:
            mock_settings.return_value.PAYLOAD_CMS_URL = "http://test-payload.com"
            mock_settings.return_value.PAYLOAD_CMS_API_KEY = "test-api-key"
            self.service = PayloadService()
    
    @pytest.mark.asyncio
    async def test_get_project_characters_success(self):
        """Test successful character retrieval."""
        # Mock response data
        mock_response_data = {
            "docs": [
                {
                    "id": "char-1",
                    "name": "Alice",
                    "project_id": "project-123",
                    "role": "protagonist",
                    "createdAt": "2023-01-01T00:00:00Z"
                },
                {
                    "id": "char-2", 
                    "name": "Bob",
                    "project_id": "project-123",
                    "role": "antagonist",
                    "createdAt": "2023-01-01T00:00:00Z"
                }
            ]
        }
        
        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service.get_project_characters("project-123")
        
        # Verify
        assert len(result) == 2
        assert result[0]["id"] == "char-1"
        assert result[0]["name"] == "Alice"
        assert result[0]["project_id"] == "project-123"
        assert "attributes" in result[0]
        
        # Check that createdAt was moved to attributes
        assert "role" in result[0]["attributes"]
    
    @pytest.mark.asyncio
    async def test_get_project_characters_http_error(self):
        """Test character retrieval with HTTP error."""
        # Mock HTTP client with error
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Connection failed")
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service.get_project_characters("project-123")
        
        # Should return empty list on error
        assert result == []
    
    @pytest.mark.asyncio
    async def test_upsert_character_create_new(self):
        """Test creating a new character."""
        profile = {
            "name": "Charlie",
            "role": "support",
            "motivation": "Help the heroes",
            "visual_signature": "Tall and friendly"
        }
        
        # Mock finding existing character (returns None)
        self.service._find_character_by_name = AsyncMock(return_value=None)
        
        # Mock HTTP client for POST
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"id": "char-new", "name": "Charlie"}
        mock_client.post.return_value = mock_response
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service.upsert_character("project-123", profile)
        
        # Verify
        assert result is not None
        assert result["id"] == "char-new"
        assert result["name"] == "Charlie"
        
        # Check that POST was called with correct data
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/api/characters"
        assert call_args[1]["json"]["name"] == "Charlie"
        assert call_args[1]["json"]["project_id"] == "project-123"
    
    @pytest.mark.asyncio
    async def test_upsert_character_update_existing(self):
        """Test updating an existing character."""
        profile = {
            "name": "Charlie",
            "role": "support",
            "motivation": "Help the heroes",
            "visual_signature": "Tall and friendly"
        }
        
        # Mock finding existing character
        existing_character = {"id": "char-existing", "name": "Charlie"}
        self.service._find_character_by_name = AsyncMock(return_value=existing_character)
        
        # Mock HTTP client for PATCH
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {"id": "char-existing", "name": "Charlie", "updated": True}
        mock_client.patch.return_value = mock_response
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service.upsert_character("project-123", profile)
        
        # Verify
        assert result is not None
        assert result["id"] == "char-existing"
        assert result.get("updated") == True
        
        # Check that PATCH was called with correct data
        mock_client.patch.assert_called_once()
        call_args = mock_client.patch.call_args
        assert call_args[0][0] == "/api/characters/char-existing"
    
    @pytest.mark.asyncio
    async def test_upsert_character_http_error(self):
        """Test character upsert with HTTP error."""
        profile = {"name": "Charlie", "role": "support"}
        
        # Mock finding existing character (returns None)
        self.service._find_character_by_name = AsyncMock(return_value=None)
        
        # Mock HTTP client with error
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Server error")
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service.upsert_character("project-123", profile)
        
        # Should return None on error
        assert result is None
    
    @pytest.mark.asyncio
    async def test_find_character_by_name_found(self):
        """Test finding character by name when character exists."""
        mock_response_data = {
            "docs": [
                {
                    "id": "char-found",
                    "name": "SearchName",
                    "project_id": "project-123"
                }
            ]
        }
        
        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service._find_character_by_name("project-123", "SearchName")
        
        # Verify
        assert result is not None
        assert result["id"] == "char-found"
        assert result["name"] == "SearchName"
    
    @pytest.mark.asyncio
    async def test_find_character_by_name_not_found(self):
        """Test finding character by name when character doesn't exist."""
        mock_response_data = {"docs": []}
        
        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service._find_character_by_name("project-123", "NonExistent")
        
        # Verify
        assert result is None
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when service is healthy."""
        # Mock HTTP client
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_client.get.return_value = mock_response
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service.health_check()
        
        # Verify
        assert result["status"] == "healthy"
        assert "response_time_ms" in result
        assert result["payload_cms_url"] == "http://test-payload.com"
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self):
        """Test health check when service is unhealthy."""
        # Mock HTTP client with error
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        
        self.service.client = mock_client
        
        # Execute
        result = await self.service.health_check()
        
        # Verify
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert result["payload_cms_url"] == "http://test-payload.com"
    
    @pytest.mark.asyncio
    async def test_close(self):
        """Test service cleanup."""
        # Mock client
        mock_client = AsyncMock()
        self.service.client = mock_client
        
        # Execute
        await self.service.close()
        
        # Verify
        mock_client.aclose.assert_called_once()
        assert self.service.client is None
    
    @pytest.mark.asyncio
    async def test_get_client_creates_new(self):
        """Test that _get_client creates a new client when none exists."""
        # Ensure no client exists
        self.service.client = None
        
        # Execute
        client = await self.service._get_client()
        
        # Verify
        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        assert self.service.client == client
    
    @pytest.mark.asyncio
    async def test_get_client_returns_existing(self):
        """Test that _get_client returns existing client."""
        # Set up existing client
        existing_client = Mock()
        self.service.client = existing_client
        
        # Execute
        client = await self.service._get_client()
        
        # Verify
        assert client == existing_client