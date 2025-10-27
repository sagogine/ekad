"""Configuration management using pydantic-settings."""
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Google Gemini API
    google_api_key: str = Field(..., description="Google API key for Gemini")
    
    # LangSmith Configuration
    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str | None = None
    langchain_project: str = "ekap"
    
    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None
    
    # Confluence Configuration
    confluence_url: str | None = None
    confluence_username: str | None = None
    confluence_api_token: str | None = None
    confluence_spaces: str = "PHARMACY,SUPPLY_CHAIN"
    
    # Firestore Configuration
    google_cloud_project: str | None = None
    firestore_collection_pharmacy: str = "pharmacy_configs"
    firestore_collection_supply_chain: str = "supply_chain_configs"
    google_application_credentials: str | None = None
    
    # GitLab Configuration
    gitlab_url: str = "https://gitlab.com"
    gitlab_token: str | None = None
    gitlab_projects_pharmacy: str | None = None
    gitlab_projects_supply_chain: str | None = None
    
    # Application Configuration
    app_name: str = "EKAP"
    app_version: str = "0.1.0"
    debug: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    
    # Business Areas
    business_areas: str = "pharmacy,supply_chain"
    
    # Embedding Configuration
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768
    
    # LLM Configuration
    llm_model: str = "gemini-2.5-flash-lite"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 8192
    
    # RAG Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k_retrieval: int = 10
    rerank_top_k: int = 5
    
    # Cache Configuration
    cache_ttl_seconds: int = 3600
    enable_semantic_cache: bool = True
    
    # Ingestion Configuration
    ingestion_batch_size: int = 100
    sync_interval_hours: int = 1
    
    @property
    def business_areas_list(self) -> list[str]:
        """Get business areas as a list."""
        return [area.strip() for area in self.business_areas.split(",")]
    
    @property
    def confluence_spaces_list(self) -> list[str]:
        """Get Confluence spaces as a list."""
        return [space.strip() for space in self.confluence_spaces.split(",")]


# Global settings instance
settings = Settings()
