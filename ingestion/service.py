"""Ingestion service orchestrating connectors, processing, and vector store."""
from typing import List, Dict, Any
from datetime import datetime
from enum import Enum
from ingestion.base import Document, SourceType
from ingestion.confluence import ConfluenceConnector
from ingestion.firestore import FirestoreConnector
from ingestion.gitlab import GitLabConnector
from ingestion.code_connector import CodeConnector
from ingestion.openmetadata import OpenMetadataConnector
from ingestion.processor import document_processor
from ingestion.change_detector import change_detector
from vectorstore.qdrant_manager import qdrant_manager
from vectorstore.hybrid_search import hybrid_search_engine
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class SyncMode(str, Enum):
    """Sync mode enumeration."""
    FULL = "full"
    INCREMENTAL = "incremental"


class IngestionService:
    """Service for ingesting documents from various sources."""
    
    def __init__(self):
        """Initialize ingestion service."""
        logger.info("Ingestion service initialized")
    
    def _get_connector(
        self,
        source: SourceType,
        business_area: str,
        config: Dict[str, Any]
    ):
        """
        Get connector instance for a source.
        
        Args:
            source: Source type
            business_area: Business area identifier
            config: Source-specific configuration
            
        Returns:
            Connector instance
        """
        if source == SourceType.CONFLUENCE:
            space_key = config.get('space_key')
            if not space_key:
                raise ValueError("Confluence space_key required")
            return ConfluenceConnector(business_area, space_key)
        
        elif source == SourceType.FIRESTORE:
            collection_name = config.get('collection_name')
            if not collection_name:
                raise ValueError("Firestore collection_name required")
            return FirestoreConnector(business_area, collection_name)
        
        elif source == SourceType.GITLAB:
            project_path = config.get('project_path')
            if not project_path:
                raise ValueError("GitLab project_path required")
            return GitLabConnector(business_area, project_path)
        
        elif source == SourceType.CODE:
            # Code connector needs source type and config
            source_type = config.get('source', 'gitlab')
            code_config = {
                "source": source_type,
                "project_path": config.get('project_path'),
                "languages": config.get('languages', 'python|java|sql')
            }
            return CodeConnector(business_area, code_config)
        
        elif source == SourceType.OPENMETADATA:
            service_name = config.get('service')
            if not service_name:
                raise ValueError("OpenMetadata service name required")
            api_url = config.get('api_url')
            api_token = config.get('api_token')
            return OpenMetadataConnector(business_area, service_name, api_url, api_token)
        
        elif source == SourceType.CODEQL:
            # CodeQL is not an ingestion source - it's handled by code graph analysis service
            raise ValueError(
                "CODEQL is not an ingestion source. "
                "Use the code graph analysis API endpoints instead."
            )
        
        else:
            raise ValueError(f"Unsupported source: {source}")
    
    async def ingest(
        self,
        business_area: str,
        source: SourceType,
        config: Dict[str, Any],
        mode: SyncMode = SyncMode.INCREMENTAL
    ) -> Dict[str, Any]:
        """
        Ingest documents from a source.
        
        Args:
            business_area: Business area identifier
            source: Source type
            config: Source-specific configuration
            mode: Sync mode (full or incremental)
            
        Returns:
            Ingestion results
        """
        try:
            start_time = datetime.utcnow()
            logger.info(
                "Starting ingestion",
                business_area=business_area,
                source=source.value,
                mode=mode.value
            )
            
            # Get connector
            connector = self._get_connector(source, business_area, config)
            source_id = f"{source.value}_{config.get('space_key') or config.get('collection_name') or config.get('project_path')}"
            
            # Fetch documents
            documents: List[Document] = []
            
            if mode == SyncMode.FULL:
                documents = await connector.fetch_all()
            else:
                # Incremental sync
                last_sync = change_detector.get_last_sync_timestamp(business_area, source_id)
                if last_sync:
                    documents = await connector.fetch_since(last_sync)
                else:
                    # First sync - do full sync
                    logger.info("No previous sync found, performing full sync")
                    documents = await connector.fetch_all()
            
            if not documents:
                logger.info("No documents to ingest")
                return {
                    "status": "success",
                    "documents_processed": 0,
                    "chunks_created": 0,
                    "documents_deleted": 0,
                    "duration_seconds": (datetime.utcnow() - start_time).total_seconds()
                }
            
            # Process documents (chunk and embed)
            chunks, embeddings = await document_processor.process_documents(documents)
            
            # Upsert into vector store
            qdrant_manager.upsert_documents(
                business_area=business_area,
                documents=chunks,
                embeddings=embeddings
            )
            
            # Build BM25 index for hybrid search
            # First, get all chunks from this business area
            # For MVP, we'll rebuild the index with new chunks
            # In production, you'd want incremental index updates
            hybrid_search_engine.build_bm25_index(business_area, chunks)
            
            # Detect deletions
            current_doc_ids = await connector.get_all_document_ids()
            changes = change_detector.detect_changes(
                business_area=business_area,
                source=source_id,
                current_document_ids=current_doc_ids
            )
            
            # Delete removed documents from vector store
            if changes['deleted']:
                for doc_id in changes['deleted']:
                    # TODO: Implement chunk deletion for documents removed from source
                    logger.debug(
                        "Chunk deletion pending implementation",
                        business_area=business_area,
                        document_id=doc_id
                    )
                
                logger.info(
                    "Deleted documents",
                    business_area=business_area,
                    count=len(changes['deleted'])
                )
            
            # Update sync metadata
            change_detector.update_sync_metadata(
                business_area=business_area,
                source=source_id,
                document_ids=current_doc_ids
            )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "status": "success",
                "documents_processed": len(documents),
                "chunks_created": len(chunks),
                "documents_deleted": len(changes['deleted']),
                "duration_seconds": duration
            }
            
            logger.info(
                "Ingestion completed",
                business_area=business_area,
                source=source.value,
                **result
            )
            
            return result
        
        except Exception as e:
            logger.error(
                "Ingestion failed",
                business_area=business_area,
                source=source.value,
                error=str(e)
            )
            raise
    
    async def ingest_all_sources(
        self,
        business_area: str,
        mode: SyncMode = SyncMode.INCREMENTAL
    ) -> Dict[str, Any]:
        """
        Ingest from all configured sources for a business area.
        
        Args:
            business_area: Business area identifier
            mode: Sync mode
            
        Returns:
            Aggregated ingestion results
        """
        results = {}
        
        # Get source configurations based on business area
        sources_config = self._get_sources_config(business_area)
        
        for source_type, config in sources_config.items():
            try:
                result = await self.ingest(
                    business_area=business_area,
                    source=source_type,
                    config=config,
                    mode=mode
                )
                results[source_type.value] = result
            except Exception as e:
                logger.error(
                    "Failed to ingest from source",
                    business_area=business_area,
                    source=source_type.value,
                    error=str(e)
                )
                results[source_type.value] = {
                    "status": "error",
                    "error": str(e)
                }
        
        return results
    
    def _get_sources_config(self, business_area: str) -> Dict[SourceType, Dict[str, Any]]:
        """
        Get source configurations for a business area.
        
        Args:
            business_area: Business area identifier
            
        Returns:
            Dictionary of source configurations
        """
        config: Dict[SourceType, Dict[str, Any]] = {}

        # Preferred: use new sources_config mapping
        raw_sources = settings.sources_config_map.get(business_area, {})
        for source_name, source_config in raw_sources.items():
            source_type = self._resolve_source_type(source_name)
            if not source_type:
                logger.warning(
                    "Skipping unsupported source",
                    business_area=business_area,
                    source=source_name
                )
                continue

            # Skip CODEQL - it's not an ingestion source, handled separately
            if source_type == SourceType.CODEQL:
                logger.debug(
                    "Skipping CODEQL from ingestion (handled by code graph analysis)",
                    business_area=business_area
                )
                continue
            
            translated = self._translate_source_config(
                business_area=business_area,
                source_type=source_type,
                source_config=source_config
            )
            if translated:
                config[source_type] = translated

        return config

    def _resolve_source_type(self, source_name: str) -> SourceType | None:
        """
        Resolve a source type string to SourceType enum.

        Args:
            source_name: Source identifier from config

        Returns:
            Matching SourceType or None if unsupported
        """
        normalized = source_name.strip().lower()
        try:
            return SourceType(normalized)
        except ValueError:
            return None

    def _translate_source_config(
        self,
        business_area: str,
        source_type: SourceType,
        source_config: Dict[str, Any]
    ) -> Dict[str, Any] | None:
        """
        Translate parsed source configuration into connector arguments.
        """
        if source_type == SourceType.CONFLUENCE:
            space_key = (
                source_config.get("space")
                or source_config.get("space_key")
                or source_config.get("space_id")
            )
            if not space_key:
                logger.error(
                    "Confluence source missing space configuration",
                    business_area=business_area,
                    config=source_config
                )
                return None
            labels = source_config.get("labels")
            if isinstance(labels, str):
                labels = [labels]
            return {
                "space_key": space_key,
                "labels": labels or []
            }

        if source_type == SourceType.FIRESTORE:
            collection_name = (
                source_config.get("collection")
                or source_config.get("collection_name")
            )
            if not collection_name:
                logger.error(
                    "Firestore source missing collection configuration",
                    business_area=business_area,
                    config=source_config
                )
                return None
            return {"collection_name": collection_name}

        if source_type == SourceType.GITLAB:
            project = source_config.get("project") or source_config.get("project_path")
            projects = (
                source_config.get("projects")
                if isinstance(source_config.get("projects"), list)
                else None
            )

            if projects:
                project = projects[0]
                if len(projects) > 1:
                    logger.warning(
                        "Multiple GitLab projects configured; using first project for ingestion",
                        business_area=business_area,
                        selected_project=project,
                        skipped_projects=projects[1:]
                    )

            if not project:
                logger.error(
                    "GitLab source missing project configuration",
                    business_area=business_area,
                    config=source_config
                )
                return None

            return {"project_path": project}

        if source_type == SourceType.CODE:
            # Code connector configuration
            source = source_config.get("source", "gitlab")
            project_path = source_config.get("project_path") or source_config.get("project")
            languages = source_config.get("languages", "python|java|sql")
            
            if source == "gitlab" and not project_path:
                logger.error(
                    "Code source (gitlab) missing project_path configuration",
                    business_area=business_area,
                    config=source_config
                )
                return None
            
            return {
                "source": source,
                "project_path": project_path,
                "languages": languages
            }

        if source_type == SourceType.OPENMETADATA:
            service = source_config.get("service") or source_config.get("service_name")
            if not service:
                logger.error(
                    "OpenMetadata source missing service configuration",
                    business_area=business_area,
                    config=source_config
                )
                return None
            
            return {
                "service": service,
                "api_url": source_config.get("api_url"),
                "api_token": source_config.get("api_token")
            }

        if source_type == SourceType.CODEQL:
            # CodeQL is not an ingestion source - it's for code graph analysis
            # This config is used by the code graph analysis service, not ingestion
            enabled = source_config.get("enabled", "true").lower() == "true"
            if not enabled:
                logger.info(
                    "CodeQL disabled for business area",
                    business_area=business_area
                )
                return None
            
            repos = source_config.get("repos")
            if repos:
                # Handle pipe-separated list of repos
                if isinstance(repos, str):
                    repos = [r.strip() for r in repos.split("|") if r.strip()]
                elif isinstance(repos, list):
                    repos = repos
            else:
                repos = []
            
            return {
                "enabled": True,
                "repos": repos,
                "business_area": business_area
            }

        logger.warning(
            "No ingestion connector implemented for source type; skipping",
            business_area=business_area,
            source=source_type.value
        )
        return None

# Global ingestion service instance
ingestion_service = IngestionService()
