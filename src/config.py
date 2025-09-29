"""
Configuration module for MCP Character Service.
Handles environment-specific settings and validation.
"""
import os
from typing import List, Optional
from functools import lru_cache
import structlog
from pydantic import BaseSettings, Field, validator

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Application Settings
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    secret_key: str = Field(..., env="SECRET_KEY")
    
    # Database Configuration
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(20, env="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(30, env="DATABASE_POOL_TIMEOUT")
    
    # Redis Configuration
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    redis_pool_size: int = Field(10, env="REDIS_POOL_SIZE")
    redis_timeout: int = Field(5, env="REDIS_TIMEOUT")
    
    # MCP Server Configuration
    mcp_server_host: str = Field("0.0.0.0", env="MCP_SERVER_HOST")
    mcp_server_port: int = Field(8011, env="MCP_SERVER_PORT")
    mcp_server_name: str = Field("character-service", env="MCP_SERVER_NAME")
    
    # PayloadCMS Integration
    payload_cms_url: str = Field(..., env="PAYLOAD_CMS_URL")
    payload_cms_api_key: str = Field(..., env="PAYLOAD_CMS_API_KEY")
    payload_cms_timeout: int = Field(30, env="PAYLOAD_CMS_TIMEOUT")
    
    # LLM Provider Configuration
    llm_provider_url: Optional[str] = Field(None, env="LLM_PROVIDER_URL")
    llm_api_key: Optional[str] = Field(None, env="LLM_API_KEY")
    llm_model_name: str = Field("gpt-3.5-turbo", env="LLM_MODEL_NAME")
    llm_timeout: int = Field(60, env="LLM_TIMEOUT")
    llm_max_tokens: int = Field(200, env="LLM_MAX_TOKENS")
    llm_temperature: float = Field(0.7, env="LLM_TEMPERATURE")
    
    # Performance Settings
    max_concurrent_requests: int = Field(100, env="MAX_CONCURRENT_REQUESTS")
    request_timeout: int = Field(30, env="REQUEST_TIMEOUT")
    character_cache_ttl: int = Field(300, env="CHARACTER_CACHE_TTL")
    
    # Observability
    prometheus_enabled: bool = Field(True, env="PROMETHEUS_ENABLED")
    prometheus_port: int = Field(8012, env="PROMETHEUS_PORT")
    structured_logging: bool = Field(True, env="STRUCTURED_LOGGING")
    log_format: str = Field("json", env="LOG_FORMAT")
    
    # Security
    cors_origins: List[str] = Field(
        ["http://localhost:3000"], 
        env="CORS_ORIGINS"
    )
    
    # Feature Flags
    enable_caching: bool = Field(True, env="ENABLE_CACHING")
    enable_metrics: bool = Field(True, env="ENABLE_METRICS")
    enable_health_checks: bool = Field(True, env="ENABLE_HEALTH_CHECKS")
    enable_payload_integration: bool = Field(True, env="ENABLE_PAYLOAD_INTEGRATION")
    enable_llm_integration: bool = Field(True, env="ENABLE_LLM_INTEGRATION")
    
    # Character Generation Settings
    max_characters_per_request: int = Field(4, env="MAX_CHARACTERS_PER_REQUEST")
    profile_generation_timeout: int = Field(300, env="PROFILE_GENERATION_TIMEOUT")
    motivation_word_limit: int = Field(50, env="MOTIVATION_WORD_LIMIT")
    visual_signature_word_limit: int = Field(40, env="VISUAL_SIGNATURE_WORD_LIMIT")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            # Handle JSON-like string format
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    # Fallback to comma-separated
                    return [origin.strip().strip('"\'') for origin in v.strip("[]").split(",")]
            # Handle comma-separated format
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v.upper()
    
    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment."""
        valid_environments = ["development", "staging", "production", "test"]
        if v.lower() not in valid_environments:
            raise ValueError(f"Invalid environment. Must be one of: {valid_environments}")
        return v.lower()
    
    @validator("payload_cms_url")
    def validate_payload_cms_url(cls, v):
        """Validate PayloadCMS URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("PayloadCMS URL must start with http:// or https://")
        return v.rstrip("/")
    
    @validator("llm_provider_url")
    def validate_llm_provider_url(cls, v):
        """Validate LLM provider URL."""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("LLM provider URL must start with http:// or https://")
        return v.rstrip("/") if v else v
    
    @validator("llm_temperature")
    def validate_llm_temperature(cls, v):
        """Validate LLM temperature."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("LLM temperature must be between 0.0 and 2.0")
        return v
    
    @property
    def database_settings(self) -> dict:
        """Get database connection settings."""
        return {
            "url": self.database_url,
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
            "pool_timeout": self.database_pool_timeout
        }
    
    @property
    def redis_settings(self) -> dict:
        """Get Redis connection settings."""
        return {
            "url": self.redis_url,
            "pool_size": self.redis_pool_size,
            "timeout": self.redis_timeout
        }
    
    @property
    def payload_cms_settings(self) -> dict:
        """Get PayloadCMS settings."""
        return {
            "url": self.payload_cms_url,
            "api_key": self.payload_cms_api_key,
            "timeout": self.payload_cms_timeout
        }
    
    @property
    def llm_settings(self) -> dict:
        """Get LLM provider settings."""
        return {
            "provider_url": self.llm_provider_url,
            "api_key": self.llm_api_key,
            "model_name": self.llm_model_name,
            "timeout": self.llm_timeout,
            "max_tokens": self.llm_max_tokens,
            "temperature": self.llm_temperature
        }
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"
    
    def model_dump_safe(self) -> dict:
        """Dump model with sensitive fields masked."""
        data = self.dict()
        
        # Mask sensitive fields
        sensitive_fields = [
            "secret_key", "database_url", "payload_cms_api_key", 
            "llm_api_key", "redis_url"
        ]
        
        for field in sensitive_fields:
            if field in data and data[field]:
                data[field] = "***masked***"
        
        return data


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        settings = Settings()
        logger.info("Configuration loaded", 
                   environment=settings.environment,
                   debug=settings.debug)
        return settings
    except Exception as e:
        logger.error("Failed to load configuration", error=str(e))
        raise


def get_database_url() -> str:
    """Get database URL from settings."""
    return get_settings().database_url


def get_redis_url() -> str:
    """Get Redis URL from settings."""
    return get_settings().redis_url


def is_feature_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled."""
    settings = get_settings()
    feature_flag = f"enable_{feature_name.lower()}"
    return getattr(settings, feature_flag, False)