"""CodeQL database builder with commit tracking."""
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from core.config import settings
from core.logging import get_logger
from .cli import get_codeql_cli
from .storage import get_codeql_storage
from .source_registry import code_source_registry

logger = get_logger(__name__)


class CodeQLDatabaseBuilder:
    """Builds and manages CodeQL databases with commit tracking."""

    def __init__(self):
        """Initialize database builder."""
        self._cli = None
        self._storage = None

    @property
    def cli(self):
        """Lazy load CodeQL CLI."""
        if self._cli is None:
            self._cli = get_codeql_cli()
        return self._cli

    @property
    def storage(self):
        """Lazy load storage."""
        if self._storage is None:
            self._storage = get_codeql_storage()
        return self._storage

    def build_database(
        self,
        source_id: str,
        repo_path: str,
        language: str,
        source_code_path: Optional[str] = None,
        build_command: Optional[str] = None
    ) -> Optional[str]:
        """
        Build a CodeQL database for a source.

        Args:
            source_id: Source ID from registry
            repo_path: Repository path (for storage key)
            language: Language to analyze
            source_code_path: Path to source code (if different from repo_path)
            build_command: Optional build command

        Returns:
            Path to stored database or None if failed
        """
        if not self.cli:
            logger.error("CodeQL CLI not available, cannot build database")
            return None

        source = code_source_registry.get(source_id)
        if not source:
            logger.error("Source not found in registry", source_id=source_id)
            return None

        business_area = source.business_area
        source_code = source_code_path or repo_path

        # Check if commit changed
        current_commit = self.cli.get_current_commit(source_code)
        last_commit = source.last_analyzed_commit

        if current_commit == last_commit and current_commit is not None:
            logger.info(
                "Commit unchanged, skipping database build",
                source_id=source_id,
                commit=current_commit
            )
            # Return existing database path if available
            existing_db = self.storage.get_database_path(business_area, repo_path, language)
            if existing_db:
                return existing_db
            # If no existing DB, continue with build

        logger.info(
            "Building CodeQL database",
            source_id=source_id,
            repo_path=repo_path,
            language=language,
            current_commit=current_commit,
            last_commit=last_commit
        )

        # Create temporary directory for database
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / f"{repo_path.replace('/', '_')}_{language}.db"

            try:
                # Build database
                built_db = self.cli.database_create(
                    database_path=str(db_path),
                    source_path=source_code,
                    language=language,
                    command=build_command
                )

                # Store database
                stored_path = self.storage.store_database(
                    database_path=built_db,
                    business_area=business_area,
                    repo_path=repo_path,
                    language=language
                )

                # Update registry with commit hash
                if current_commit:
                    code_source_registry.update_commit_hash(source_id, current_commit)

                logger.info(
                    "CodeQL database built and stored",
                    source_id=source_id,
                    stored_path=stored_path
                )

                return stored_path

            except Exception as e:
                logger.error(
                    "Failed to build CodeQL database",
                    source_id=source_id,
                    error=str(e)
                )
                return None

    def get_database_path(
        self,
        business_area: str,
        repo_path: str,
        language: str
    ) -> Optional[str]:
        """
        Get path to existing database.

        Args:
            business_area: Business area identifier
            repo_path: Repository path
            language: Language

        Returns:
            Database path or None if not found
        """
        return self.storage.get_database_path(business_area, repo_path, language)

    def needs_rebuild(
        self,
        source_id: str,
        repo_path: str
    ) -> bool:
        """
        Check if database needs to be rebuilt (commit changed).

        Args:
            source_id: Source ID
            repo_path: Repository path

        Returns:
            True if rebuild needed
        """
        source = code_source_registry.get(source_id)
        if not source:
            return True  # Source not found, needs initial build

        if not self.cli:
            return False  # Can't check without CLI

        current_commit = self.cli.get_current_commit(repo_path)
        last_commit = source.last_analyzed_commit

        return current_commit != last_commit

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
        self.storage.delete_database(business_area, repo_path, language)
        logger.info(
            "Deleted CodeQL database",
            business_area=business_area,
            repo=repo_path,
            language=language
        )


# Global database builder instance
codeql_database_builder = CodeQLDatabaseBuilder()

