"""Registry for tracking code sources (repos, filesystems) for CodeQL analysis."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CodeSource:
    """Represents a code source for analysis."""
    source_id: str
    business_area: str
    source_type: str  # "gitlab" or "filesystem"
    path: str  # GitLab project path or filesystem path
    languages: List[str]  # ["python", "java", "sql", "shell"]
    name: Optional[str] = None  # Friendly name
    last_analyzed_commit: Optional[str] = None  # Git commit hash
    last_analyzed_time: Optional[datetime] = None
    enabled: bool = True
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.last_analyzed_time:
            data["last_analyzed_time"] = self.last_analyzed_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeSource":
        """Create from dictionary."""
        if "last_analyzed_time" in data and data["last_analyzed_time"]:
            data["last_analyzed_time"] = datetime.fromisoformat(data["last_analyzed_time"])
        return cls(**data)


class CodeSourceRegistry:
    """Registry for managing code sources for CodeQL analysis."""

    def __init__(self, registry_path: Optional[str] = None):
        """
        Initialize source registry.

        Args:
            registry_path: Path to registry JSON file (defaults to data/code_source_registry.json)
        """
        self.registry_path = Path(registry_path or "data/code_source_registry.json")
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._sources: Dict[str, CodeSource] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from file."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, "r") as f:
                    data = json.load(f)
                    self._sources = {
                        source_id: CodeSource.from_dict(source_data)
                        for source_id, source_data in data.items()
                    }
                logger.info(
                    "Loaded code source registry",
                    count=len(self._sources),
                    path=str(self.registry_path)
                )
            except Exception as e:
                logger.error("Failed to load code source registry", error=str(e))
                self._sources = {}
        else:
            logger.info("Code source registry file not found, starting fresh")

    def _save(self) -> None:
        """Save registry to file."""
        try:
            data = {
                source_id: source.to_dict()
                for source_id, source in self._sources.items()
            }
            with open(self.registry_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("Saved code source registry", count=len(self._sources))
        except Exception as e:
            logger.error("Failed to save code source registry", error=str(e))
            raise

    def register(
        self,
        business_area: str,
        source_type: str,
        path: str,
        languages: List[str],
        name: Optional[str] = None,
        source_id: Optional[str] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a new code source.

        Args:
            business_area: Business area identifier
            source_type: "gitlab" or "filesystem"
            path: GitLab project path (e.g., "org/repo") or filesystem path
            languages: List of languages (e.g., ["python", "java"])
            name: Optional friendly name
            source_id: Optional custom source ID (auto-generated if not provided)
            enabled: Whether source is enabled for analysis
            metadata: Optional metadata

        Returns:
            Source ID
        """
        if not source_id:
            # Generate source ID from business_area, type, and path
            safe_path = path.replace("/", "_").replace("\\", "_")
            source_id = f"{business_area}_{source_type}_{safe_path}"

        if source_id in self._sources:
            logger.warning(
                "Source already registered, updating",
                source_id=source_id,
                business_area=business_area
            )

        source = CodeSource(
            source_id=source_id,
            business_area=business_area,
            source_type=source_type,
            path=path,
            languages=languages,
            name=name or path,
            enabled=enabled,
            metadata=metadata or {}
        )

        self._sources[source_id] = source
        self._save()

        logger.info(
            "Registered code source",
            source_id=source_id,
            business_area=business_area,
            source_type=source_type,
            path=path
        )

        return source_id

    def get(self, source_id: str) -> Optional[CodeSource]:
        """Get source by ID."""
        return self._sources.get(source_id)

    def list_sources(
        self,
        business_area: Optional[str] = None,
        source_type: Optional[str] = None,
        enabled_only: bool = False
    ) -> List[CodeSource]:
        """
        List sources with optional filtering.

        Args:
            business_area: Filter by business area
            source_type: Filter by source type
            enabled_only: Only return enabled sources

        Returns:
            List of matching sources
        """
        sources = list(self._sources.values())

        if business_area:
            sources = [s for s in sources if s.business_area == business_area]

        if source_type:
            sources = [s for s in sources if s.source_type == source_type]

        if enabled_only:
            sources = [s for s in sources if s.enabled]

        return sources

    def update_commit_hash(self, source_id: str, commit_hash: str) -> None:
        """Update last analyzed commit hash for a source."""
        if source_id not in self._sources:
            raise ValueError(f"Source not found: {source_id}")

        self._sources[source_id].last_analyzed_commit = commit_hash
        self._sources[source_id].last_analyzed_time = datetime.now()
        self._save()

        logger.debug(
            "Updated commit hash for source",
            source_id=source_id,
            commit_hash=commit_hash
        )

    def get_current_commit(self, source_id: str) -> Optional[str]:
        """Get current commit hash for a source (if Git-based)."""
        source = self.get(source_id)
        if not source:
            return None
        return source.last_analyzed_commit

    def is_codeql_enabled(self, business_area: str) -> bool:
        """
        Check if CodeQL is enabled for a business area.

        Checks both global setting and per-area configuration.

        Args:
            business_area: Business area identifier

        Returns:
            True if CodeQL is enabled for this area
        """
        # Check global setting
        if not settings.codeql_enabled:
            return False

        # Check if business area has codeql source configured
        sources_config = settings.sources_config_map.get(business_area, {})
        codeql_config = sources_config.get("codeql")
        if not codeql_config:
            return False

        # Check if enabled in config
        enabled = codeql_config.get("enabled", "true").lower() == "true"
        return enabled

    def delete(self, source_id: str) -> None:
        """Delete a source from registry."""
        if source_id not in self._sources:
            raise ValueError(f"Source not found: {source_id}")

        del self._sources[source_id]
        self._save()

        logger.info("Deleted code source", source_id=source_id)


# Global registry instance
code_source_registry = CodeSourceRegistry()

