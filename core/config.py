"""Configuration management using pydantic-settings."""
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Configuration priority (highest to lowest):
    1. Runtime environment variables
    2. .env file (per-tenant)
    3. Defaults in this class
    
    Categories:
    - Infrastructure: Defaults in code, rarely change per tenant
    - Secrets: Required from environment, never hardcoded
    - Tenant Config: String-based per-tenant configuration
    - Service Endpoints: Defaults with environment override
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ============================================
    # SECRETS (Required from environment)
    # ============================================
    google_api_key: SecretStr = Field(
        ...,
        description="[REQUIRED] Google API key for Gemini. Get from Google Cloud Console."
    )

    # ============================================
    # SECRETS MANAGER CONFIGURATION
    # ============================================
    secrets_provider: Literal["none", "gcp"] = Field(
        default="none",
        description=(
            "[OPTIONAL] Secrets provider to use. Options: 'none' (env vars only), 'gcp' (GCP Secret Manager). "
            "When set to 'gcp', secrets will be fetched from GCP Secret Manager if not found in env vars."
        )
    )
    secrets_path_prefix: str | None = Field(
        default=None,
        description=(
            "[OPTIONAL] Prefix for secret names in Secret Manager. "
            "Example: 'traceback/prod' would look for 'traceback/prod/google-api-key'"
        )
    )

    # ============================================
    # INFRASTRUCTURE (Defaults in code)
    # ============================================
    # Qdrant Configuration
    qdrant_host: str = Field(
        default="localhost",
        description="Qdrant vector database hostname"
    )
    qdrant_port: int = Field(
        default=6333,
        description="Qdrant vector database port"
    )
    qdrant_api_key: SecretStr | None = Field(
        default=None,
        description="[OPTIONAL] Qdrant API key for authentication"
    )

    # Embedding Configuration
    embedding_model: str = Field(
        default="models/text-embedding-004",
        description="Google embedding model identifier"
    )
    embedding_dimension: int = Field(
        default=768,
        description="Embedding vector dimension"
    )

    # LLM Configuration
    llm_model: str = Field(
        default="gemini-2.5-flash-lite",
        description="Google Gemini model identifier"
    )
    llm_temperature: float = Field(
        default=0.1,
        description="LLM temperature (0.0-1.0, lower = more deterministic)"
    )
    llm_max_tokens: int = Field(
        default=8192,
        description="Maximum tokens for LLM responses"
    )

    # RAG Configuration
    chunk_size: int = Field(
        default=1000,
        description="Document chunk size for embedding"
    )
    chunk_overlap: int = Field(
        default=200,
        description="Overlap between document chunks"
    )
    top_k_retrieval: int = Field(
        default=10,
        description="Number of documents to retrieve per query"
    )
    rerank_top_k: int = Field(
        default=5,
        description="Number of documents to rerank after initial retrieval"
    )

    # Cache Configuration
    cache_ttl_seconds: int = Field(
        default=3600,
        description="Cache TTL in seconds"
    )
    enable_semantic_cache: bool = Field(
        default=True,
        description="Enable semantic caching for queries"
    )

    # Ingestion Configuration
    ingestion_batch_size: int = Field(
        default=100,
        description="Batch size for document ingestion"
    )
    sync_interval_hours: int = Field(
        default=1,
        description="Interval between incremental syncs (hours)"
    )

    # Application Configuration
    app_name: str = Field(
        default="Traceback",
        description="Application name"
    )
    app_version: str = Field(
        default="0.1.0",
        description="Application version"
    )
    debug: bool = Field(
        default=True,
        description="Enable debug mode"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level"
    )

    # ============================================
    # SERVICE ENDPOINTS (Defaults with env override)
    # ============================================
    # Confluence Configuration
    confluence_url: str | None = Field(
        default=None,
        description="[OPTIONAL] Confluence base URL (e.g., https://company.atlassian.net)"
    )
    confluence_username: str | None = Field(
        default=None,
        description="[OPTIONAL] Confluence username/email (required if using Confluence)"
    )
    confluence_api_token: SecretStr | None = Field(
        default=None,
        description="[OPTIONAL] Confluence API token (required if using Confluence)"
    )

    # Firestore Configuration
    google_cloud_project: str | None = Field(
        default=None,
        description="[OPTIONAL] Google Cloud project ID (required if using Firestore)"
    )
    google_application_credentials: str | None = Field(
        default=None,
        description="[OPTIONAL] Path to Google service account JSON (required if using Firestore)"
    )

    # GitLab Configuration
    gitlab_url: str = Field(
        default="https://gitlab.com",
        description="GitLab instance URL"
    )
    gitlab_token: SecretStr | None = Field(
        default=None,
        description="[OPTIONAL] GitLab personal access token (required if using GitLab/code source)"
    )

    # OpenMetadata Configuration
    openmetadata_url: str = Field(
        default="http://localhost:8585/api/v1",
        description="OpenMetadata API base URL"
    )
    openmetadata_token: SecretStr | None = Field(
        default=None,
        description="[OPTIONAL] OpenMetadata API authentication token (required if using OpenMetadata)"
    )

    # ============================================
    # CODE GRAPH CONFIGURATION (Optional Augmentation)
    # ============================================
    # Neo4j Configuration (for code graph storage)
    neo4j_url: str | None = Field(
        default=None,
        description="[OPTIONAL] Neo4j connection URL (e.g., bolt://localhost:7687). Required if using code graph."
    )
    neo4j_user: str | None = Field(
        default=None,
        description="[OPTIONAL] Neo4j username. Required if using code graph."
    )
    neo4j_password: SecretStr | None = Field(
        default=None,
        description="[OPTIONAL] Neo4j password. Required if using code graph."
    )

    # CodeQL Configuration (for code analysis)
    codeql_enabled: bool = Field(
        default=False,
        description="[OPTIONAL] Enable CodeQL code graph analysis globally. Can be overridden per business area."
    )
    codeql_database_path: str = Field(
        default="/data/codeql-databases",
        description="[OPTIONAL] Path to store CodeQL databases (local filesystem or GCS path)"
    )
    codeql_storage_type: Literal["local", "gcs"] = Field(
        default="local",
        description="[OPTIONAL] Storage type for CodeQL databases: 'local' (filesystem) or 'gcs' (Google Cloud Storage)"
    )
    codeql_gcs_bucket: str | None = Field(
        default=None,
        description="[OPTIONAL] GCS bucket name for CodeQL databases (required if codeql_storage_type=gcs)"
    )
    codeql_analysis_frequency: Literal["webhook", "scheduled", "manual"] = Field(
        default="manual",
        description="[OPTIONAL] When to run CodeQL analysis: 'webhook' (on push), 'scheduled' (periodic), 'manual' (API only)"
    )
    codeql_scheduled_interval_hours: int = Field(
        default=24,
        description="[OPTIONAL] Interval for scheduled CodeQL analysis (hours)"
    )

    # LangSmith Configuration (Optional Observability)
    langchain_tracing_v2: bool = Field(
        default=False,
        description="Enable LangSmith tracing"
    )
    langchain_api_key: SecretStr | None = Field(
        default=None,
        description="[OPTIONAL] LangSmith API key for observability"
    )
    langchain_project: str = Field(
        default="traceback",
        description="LangSmith project name"
    )

    # ============================================
    # TENANT CONFIGURATION (String-based from env)
    # ============================================
    business_areas: str = Field(
        default="default",
        description="[REQUIRED] Comma-separated list of business area identifiers (e.g., 'claims,retail')"
    )
    sources_config: str | None = Field(
        default=None,
        description=(
            "[OPTIONAL] Per-business-area source configuration. "
            "Format: area:source(key=value, key2=value2),area2:source2(key=value)\n"
            "Example: claims:confluence(space=CLM),claims:code(source=gitlab,project_path=org/repo)"
        )
    )
    retriever_overrides: str | None = Field(
        default=None,
        description=(
            "[OPTIONAL] Per-business-area retriever overrides. "
            "Format: area:source=retriever1|retriever2\n"
            "Example: claims:openmetadata=lineage,claims:code=code"
        )
    )

    @property
    def sources_config_map(self) -> dict[str, dict[str, dict[str, str | list[str]]]]:
        """Get per-business-area source configuration."""
        raw = self.sources_config
        if not raw:
            return {}
        # Clean up line continuations (backslashes and newlines)
        # Remove backslashes followed by newlines/whitespace
        cleaned = raw.replace('\\\n', '').replace('\\\r\n', '').replace('\\\r', '')
        # Remove any remaining standalone backslashes that might be from line continuations
        # But preserve backslashes that are part of actual values (like file paths)
        # We do this by removing backslashes that are followed by whitespace or at end of string
        import re
        cleaned = re.sub(r'\\\s+', ' ', cleaned)  # Replace backslash+whitespace with space
        cleaned = re.sub(r'\\$', '', cleaned)  # Remove trailing backslashes
        # Remove extra whitespace and normalize
        cleaned = ' '.join(cleaned.split())
        # Filter out empty segments that might be just backslashes
        return self._parse_sources_config(cleaned)

    @property
    def retriever_overrides_map(self) -> dict[str, dict[str, list[str]]]:
        """Get per-business-area retriever overrides."""
        raw = self.retriever_overrides
        if not raw:
            return {}

        mapping: dict[str, dict[str, list[str]]] = {}

        for entry in self._split_top_level(raw):
            if ":" not in entry or "=" not in entry:
                raise ValueError(
                    f"Invalid retriever override entry '{entry}'. "
                    "Expected format 'area:source=retriever1|retriever2'."
                )

            area_source, retrievers = entry.split("=", 1)
            area, source = (part.strip() for part in area_source.split(":", 1))

            if not area or not source:
                raise ValueError(
                    f"Invalid retriever override entry '{entry}'. "
                    "Business area and source must be specified."
                )

            values = [value.strip() for value in retrievers.split("|") if value.strip()]

            if not values:
                raise ValueError(
                    f"Retriever override for '{area}:{source}' must specify at least one retriever."
                )

            mapping.setdefault(area, {})[source] = values

        return mapping

    @staticmethod
    def _split_top_level(raw: str, delimiter: str = ",") -> list[str]:
        """
        Split a string on a delimiter, respecting parentheses depth.

        Args:
            raw: Input string
            delimiter: Delimiter to split on (default: ",")

        Returns:
            List of split segments
        """
        segments: list[str] = []
        current: list[str] = []
        depth = 0

        for char in raw:
            if char == delimiter and depth == 0:
                segment = "".join(current).strip()
                if segment:
                    segments.append(segment)
                current = []
                continue

            current.append(char)

            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)

        tail = "".join(current).strip()
        if tail:
            segments.append(tail)

        if depth != 0:
            raise ValueError(f"Unbalanced parentheses in '{raw}'.")

        return segments

    @staticmethod
    def _parse_sources_config(raw: str) -> dict[str, dict[str, dict[str, str | list[str]]]]:
        """
        Parse the sources configuration string.

        Format:
            area:source(key=value, key2=value2),area2:source2(key=value)

        Returns:
            Nested mapping: business_area -> source -> config dict
        """
        mapping: dict[str, dict[str, dict[str, str | list[str]]]] = {}

        for entry in Settings._split_top_level(raw):
            # Skip empty entries (might be from line continuation artifacts)
            entry = entry.strip()
            if not entry or entry == '\\':
                continue
            
            if ":" not in entry:
                raise ValueError(
                    f"Invalid sources_config entry '{entry}'. Expected format 'area:source(key=value)'."
                )

            area_part, source_part = entry.split(":", 1)
            business_area = area_part.strip()
            source_part = source_part.strip()

            if not business_area or "(" not in source_part or not source_part.endswith(")"):
                raise ValueError(
                    f"Invalid sources_config entry '{entry}'. Expected format 'area:source(key=value)'."
                )

            source_name, payload = source_part.split("(", 1)
            source_name = source_name.strip()
            payload = payload.rsplit(")", 1)[0].strip()

            if not source_name:
                raise ValueError(
                    f"Invalid sources_config entry '{entry}'. Source name must be provided."
                )

            config: dict[str, str | list[str]] = {}

            if payload:
                for item in Settings._split_top_level(payload, delimiter=","):
                    if "=" not in item:
                        raise ValueError(
                            f"Invalid source config '{item}' in entry '{entry}'. Expected key=value."
                        )
                    key, value = (part.strip() for part in item.split("=", 1))
                    if not key or not value:
                        raise ValueError(
                            f"Invalid source config '{item}' in entry '{entry}'. Key and value required."
                        )
                    if "|" in value:
                        config[key] = [segment.strip() for segment in value.split("|") if segment.strip()]
                    else:
                        config[key] = value

            mapping.setdefault(business_area, {})[source_name] = config

        return mapping

    @property
    def business_areas_list(self) -> list[str]:
        """Get business areas as a list."""
        return [area.strip() for area in self.business_areas.split(",") if area.strip()]

    def validate_tenant_config(self, business_area: str) -> None:
        """
        Validate that required configuration exists for a business area.
        
        Args:
            business_area: Business area identifier to validate
            
        Raises:
            ValueError: If required configuration is missing
        """
        if business_area not in self.business_areas_list:
            raise ValueError(
                f"Business area '{business_area}' not found in BUSINESS_AREAS. "
                f"Available: {self.business_areas_list}"
            )
        
        sources = self.sources_config_map.get(business_area, {})
        if not sources:
            raise ValueError(
                f"No sources configured for business area '{business_area}'. "
                "Configure sources via SOURCES_CONFIG environment variable."
            )

    def _get_secret_name(self, field_name: str) -> str:
        """
        Map a field name to its secret manager name.
        
        Args:
            field_name: Field name (e.g., 'google_api_key')
            
        Returns:
            Secret name in Secret Manager (e.g., 'google-api-key')
        """
        # Convert snake_case to kebab-case
        return field_name.replace("_", "-")

    def get_secret_value(
        self,
        secret_field: SecretStr | None,
        secret_name: str | None = None,
        field_name: str | None = None
    ) -> str | None:
        """
        Safely extract string value from SecretStr field, with optional fallback to secrets manager.
        
        Priority:
        1. Environment variable (from SecretStr field)
        2. Secrets Manager (if configured and secret_name or field_name provided)
        
        Args:
            secret_field: SecretStr field or None
            secret_name: Optional explicit name of secret in Secret Manager
            field_name: Optional field name (used to auto-generate secret_name)
            
        Returns:
            String value or None
        """
        # Get value from env var if available
        env_value = None
        if secret_field is not None:
            env_value = secret_field.get_secret_value()
        
        # If env value exists, use it
        if env_value and env_value.strip():
            return env_value.strip()
        
        # Determine secret name
        if not secret_name and field_name:
            secret_name = self._get_secret_name(field_name)
        
        # If no env value and secret_name available, try secrets manager
        if secret_name:
            from core.secrets.resolver import resolve_secret
            return resolve_secret(env_value, secret_name, use_async=False)
        
        return None


# Global settings instance
settings = Settings()
