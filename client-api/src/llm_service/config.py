from typing import List, Optional
from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # App
    app_name: str = "llm_service"
    environment: str = "development"
    log_level: str = "INFO"

    # CORS
    cors_allow_origins: List[str] = ["*"]

    # ORDERS API
    orders_api_base_url: Optional[AnyHttpUrl] = None
    restaurants_api_base_url: Optional[AnyHttpUrl] = None
    orders_api_token: Optional[str] = Field(None, description="Bearer token for orders API auth")
    orders_api_timeout: float = Field(default=30.0, description="Default request timeout (seconds)")
    orders_api_timeout_connect: float = Field(default=5.0, description="Connection timeout (seconds)")

    # LLM / provider
    llm_provider: str = "local" # or "other"; determine which API/endpoint to use based on this
    local_api_key: Optional[str] = None
    local_endpoint: Optional[AnyHttpUrl] = None
    local_endpoint_openai: Optional[AnyHttpUrl] = None
    local_model: str = "your_local_model"
    other_api_key: Optional[str] = None
    other_endpoint: Optional[AnyHttpUrl] = None
    other_endpoint_openai: Optional[AnyHttpUrl] = None
    other_model: str = "your_model"

    # Timeouts / limits
    llm_timeout_seconds: int = 30
    max_tokens: int = 8192
    temperature: float = 0.2

    # Tooling / behavior
    enforce_json_response: bool = True
    response_schema_path: Optional[str] = None

    # Runtime
    host: str = "0.0.0.0"
    port: int = 8001

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_ignore_empty": True,
        "extra": "ignore",
        "case_sensitive": False,
    }
    
# Global singleton instance
settings = Settings()

def get_settings() -> Settings:
    """FastAPI dependency factory."""
    return settings