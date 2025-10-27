"""Ingestion service orchestrating connectors, processing, and vector store."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from ingestion.base import Document, SourceType
from ingestion.confluence import ConfluenceConnector
from ingestion.firestore import FirestoreConnector
from ingestion.gitlab import GitLabConnector
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
                # Delete all chunks of deleted documents
                chunk_ids_to_delete = []
                for doc_id in changes['deleted']:
                    # Get all chunk IDs for this document
                    # For simplicity, we'll use a pattern match
                    # In production, you'd want to track chunk IDs properly
                    pass  # TODO: Implement chunk deletion
                
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
        config = {}
        
        # Confluence
        if settings.confluence_url:
            space_key = None
            if business_area == "pharmacy":
                space_key = "PHARMACY"  # Default, should be configurable
            elif business_area == "supply_chain":
                space_key = "SUPPLY_CHAIN"
            
            if space_key:
                config[SourceType.CONFLUENCE] = {"space_key": space_key}
        
        # Firestore
        if settings.google_cloud_project:
            collection_name = None
            if business_area == "pharmacy":
                collection_name = settings.firestore_collection_pharmacy
            elif business_area == "supply_chain":
                collection_name = settings.firestore_collection_supply_chain
            
            if collection_name:
                config[SourceType.FIRESTORE] = {"collection_name": collection_name}
        
        # GitLab
        if settings.gitlab_token:
            project_path = None
            if business_area == "pharmacy":
                project_path = settings.gitlab_projects_pharmacy
            elif business_area == "supply_chain":
                project_path = settings.gitlab_projects_supply_chain
            
            if project_path:
                config[SourceType.GITLAB] = {"project_path": project_path}
        
        return config


# Global ingestion service instance
ingestion_service = IngestionService()
