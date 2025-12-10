"""Storage abstraction for CodeQL databases (local filesystem or GCS)."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class CodeQLStorage(ABC):
    """Abstract base class for CodeQL database storage."""

    @abstractmethod
    def store_database(
        self,
        database_path: str,
        business_area: str,
        repo_path: str,
        language: str
    ) -> str:
        """
        Store a CodeQL database.

        Args:
            database_path: Local path to the database
            business_area: Business area identifier
            repo_path: Repository path (e.g., "org/repo")
            language: Language (e.g., "python", "java")

        Returns:
            Storage path/identifier for the database
        """
        pass

    @abstractmethod
    def get_database_path(
        self,
        business_area: str,
        repo_path: str,
        language: str
    ) -> Optional[str]:
        """
        Get path to a CodeQL database.

        Args:
            business_area: Business area identifier
            repo_path: Repository path
            language: Language

        Returns:
            Database path or None if not found
        """
        pass

    @abstractmethod
    def list_databases(self, business_area: Optional[str] = None) -> list[str]:
        """
        List stored databases.

        Args:
            business_area: Optional filter by business area

        Returns:
            List of database paths/identifiers
        """
        pass

    @abstractmethod
    def delete_database(
        self,
        business_area: str,
        repo_path: str,
        language: str
    ) -> None:
        """
        Delete a CodeQL database.

        Args:
            business_area: Business area identifier
            repo_path: Repository path
            language: Language
        """
        pass


class LocalCodeQLStorage(CodeQLStorage):
    """Local filesystem storage for CodeQL databases."""

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize local storage.

        Args:
            base_path: Base path for databases (defaults to settings.codeql_database_path or data/codeql-databases)
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            # Use relative path if absolute path doesn't exist
            default_path = Path(settings.codeql_database_path)
            if default_path.is_absolute() and not default_path.parent.exists():
                # Fallback to relative path
                self.base_path = Path("data") / "codeql-databases"
            else:
                self.base_path = default_path
        
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("Local CodeQL storage initialized", base_path=str(self.base_path))

    def _get_database_dir(self, business_area: str, repo_path: str, language: str) -> Path:
        """Get directory path for a database."""
        safe_repo = repo_path.replace("/", "_").replace("\\", "_")
        return self.base_path / business_area / safe_repo / language

    def store_database(
        self,
        database_path: str,
        business_area: str,
        repo_path: str,
        language: str
    ) -> str:
        """Store database by copying to storage location."""
        source_path = Path(database_path)
        if not source_path.exists():
            raise ValueError(f"Database not found: {database_path}")

        target_dir = self._get_database_dir(business_area, repo_path, language)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy database (CodeQL databases are directories)
        import shutil
        target_path = target_dir / source_path.name
        if target_path.exists():
            shutil.rmtree(target_path)
        shutil.copytree(source_path, target_path)

        logger.info(
            "Stored CodeQL database",
            business_area=business_area,
            repo=repo_path,
            language=language,
            path=str(target_path)
        )

        return str(target_path)

    def get_database_path(
        self,
        business_area: str,
        repo_path: str,
        language: str
    ) -> Optional[str]:
        """Get path to stored database."""
        db_dir = self._get_database_dir(business_area, repo_path, language)
        
        # CodeQL databases are directories - find the database directory
        if not db_dir.exists():
            return None

        # Look for database directory (usually named after the repo or "codeql-database")
        for item in db_dir.iterdir():
            if item.is_dir() and (item.name.endswith(".db") or "codeql" in item.name.lower()):
                return str(item)

        # Fallback: return the directory itself
        return str(db_dir) if db_dir.exists() else None

    def list_databases(self, business_area: Optional[str] = None) -> list[str]:
        """List stored databases."""
        databases = []
        search_path = self.base_path / business_area if business_area else self.base_path

        if not search_path.exists():
            return []

        for area_dir in search_path.iterdir():
            if business_area and area_dir.name != business_area:
                continue
            if not area_dir.is_dir():
                continue

            for repo_dir in area_dir.iterdir():
                if not repo_dir.is_dir():
                    continue
                for lang_dir in repo_dir.iterdir():
                    if lang_dir.is_dir():
                        databases.append(str(lang_dir))

        return databases

    def delete_database(
        self,
        business_area: str,
        repo_path: str,
        language: str
    ) -> None:
        """Delete stored database."""
        db_dir = self._get_database_dir(business_area, repo_path, language)
        if db_dir.exists():
            import shutil
            shutil.rmtree(db_dir)
            logger.info(
                "Deleted CodeQL database",
                business_area=business_area,
                repo=repo_path,
                language=language
            )


class GCSCodeQLStorage(CodeQLStorage):
    """Google Cloud Storage storage for CodeQL databases (for production)."""

    def __init__(self, bucket_name: str):
        """
        Initialize GCS storage.

        Args:
            bucket_name: GCS bucket name
        """
        self.bucket_name = bucket_name
        # TODO: Initialize GCS client when implementing
        logger.info("GCS CodeQL storage initialized", bucket=bucket_name)
        raise NotImplementedError("GCS storage not yet implemented")

    def store_database(
        self,
        database_path: str,
        business_area: str,
        repo_path: str,
        language: str
    ) -> str:
        """Store database to GCS."""
        raise NotImplementedError("GCS storage not yet implemented")

    def get_database_path(
        self,
        business_area: str,
        repo_path: str,
        language: str
    ) -> Optional[str]:
        """Get database from GCS (download to temp location)."""
        raise NotImplementedError("GCS storage not yet implemented")

    def list_databases(self, business_area: Optional[str] = None) -> list[str]:
        """List databases in GCS."""
        raise NotImplementedError("GCS storage not yet implemented")

    def delete_database(
        self,
        business_area: str,
        repo_path: str,
        language: str
    ) -> None:
        """Delete database from GCS."""
        raise NotImplementedError("GCS storage not yet implemented")


def get_codeql_storage() -> CodeQLStorage:
    """
    Get CodeQL storage instance based on configuration.

    Returns:
        CodeQLStorage instance
    """
    storage_type = settings.codeql_storage_type

    if storage_type == "local":
        return LocalCodeQLStorage()

    elif storage_type == "gcs":
        bucket = settings.codeql_gcs_bucket
        if not bucket:
            raise ValueError("codeql_gcs_bucket must be set when using GCS storage")
        return GCSCodeQLStorage(bucket)

    else:
        raise ValueError(f"Unknown storage type: {storage_type}")

