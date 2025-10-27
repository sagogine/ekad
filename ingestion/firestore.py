"""Firestore connector for fetching configuration data."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from google.cloud import firestore
from ingestion.base import BaseConnector, Document, DocumentType, SourceType
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class FirestoreConnector(BaseConnector):
    """Connector for Firestore collections."""
    
    def __init__(self, business_area: str, collection_name: str):
        """
        Initialize Firestore connector.
        
        Args:
            business_area: Business area identifier
            collection_name: Firestore collection name
        """
        super().__init__(business_area)
        self.collection_name = collection_name
        
        if not settings.google_cloud_project:
            raise ValueError("Google Cloud Project not configured")
        
        # Initialize Firestore client
        self.client = firestore.Client(project=settings.google_cloud_project)
        self.collection_ref = self.client.collection(collection_name)
        
        logger.info(
            "Firestore connector initialized",
            business_area=business_area,
            collection=collection_name
        )
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """
        Flatten nested dictionary.
        
        Args:
            d: Dictionary to flatten
            parent_key: Parent key for recursion
            sep: Separator for nested keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def _document_to_text(self, doc_data: Dict[str, Any]) -> str:
        """
        Convert Firestore document to text representation.
        
        Args:
            doc_data: Document data
            
        Returns:
            Text representation
        """
        flattened = self._flatten_dict(doc_data)
        lines = [f"{key}: {value}" for key, value in flattened.items()]
        return '\n'.join(lines)
    
    def _parse_document(self, doc_snapshot) -> Document:
        """
        Parse Firestore document to Document.
        
        Args:
            doc_snapshot: Firestore document snapshot
            
        Returns:
            Document object
        """
        doc_id = doc_snapshot.id
        doc_data = doc_snapshot.to_dict()
        
        # Extract metadata
        updated_at = doc_data.get('updated_at') or doc_data.get('updatedAt') or datetime.utcnow()
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        
        # Build content from document fields
        content = self._document_to_text(doc_data)
        
        # Extract title (use 'name' or 'title' field if available, else doc_id)
        title = doc_data.get('name') or doc_data.get('title') or f"Config: {doc_id}"
        
        # Build URL (Firestore console URL)
        url = f"https://console.cloud.google.com/firestore/data/{self.collection_name}/{doc_id}?project={settings.google_cloud_project}"
        
        return Document(
            id=f"firestore_{self.collection_name}_{doc_id}",
            content=content,
            title=title,
            source=SourceType.FIRESTORE,
            document_type=DocumentType.CONFIG,
            business_area=self.business_area,
            last_modified=updated_at,
            url=url,
            metadata={
                "collection": self.collection_name,
                "document_id": doc_id,
                "field_count": len(doc_data)
            }
        )
    
    async def fetch_all(self) -> List[Document]:
        """
        Fetch all documents from Firestore collection.
        
        Returns:
            List of documents
        """
        try:
            logger.info(
                "Fetching all Firestore documents",
                collection=self.collection_name
            )
            
            documents = []
            docs = self.collection_ref.stream()
            
            for doc in docs:
                try:
                    document = self._parse_document(doc)
                    documents.append(document)
                except Exception as e:
                    logger.error(
                        "Failed to parse Firestore document",
                        doc_id=doc.id,
                        error=str(e)
                    )
            
            logger.info(
                "Fetched Firestore documents",
                collection=self.collection_name,
                count=len(documents)
            )
            return documents
        
        except Exception as e:
            logger.error(
                "Failed to fetch Firestore documents",
                collection=self.collection_name,
                error=str(e)
            )
            raise
    
    async def fetch_since(self, timestamp: datetime) -> List[Document]:
        """
        Fetch documents modified since timestamp.
        
        Args:
            timestamp: Last sync timestamp
            
        Returns:
            List of modified documents
        """
        try:
            logger.info(
                "Fetching modified Firestore documents",
                collection=self.collection_name,
                since=timestamp.isoformat()
            )
            
            documents = []
            
            # Try to query by updated_at field
            try:
                query = self.collection_ref.where('updated_at', '>', timestamp)
                docs = query.stream()
                
                for doc in docs:
                    try:
                        document = self._parse_document(doc)
                        documents.append(document)
                    except Exception as e:
                        logger.error(
                            "Failed to parse Firestore document",
                            doc_id=doc.id,
                            error=str(e)
                        )
            except Exception:
                # If updated_at field doesn't exist, try updatedAt
                try:
                    query = self.collection_ref.where('updatedAt', '>', timestamp)
                    docs = query.stream()
                    
                    for doc in docs:
                        try:
                            document = self._parse_document(doc)
                            documents.append(document)
                        except Exception as e:
                            logger.error(
                                "Failed to parse Firestore document",
                                doc_id=doc.id,
                                error=str(e)
                            )
                except Exception:
                    # If no timestamp field, fetch all and filter
                    logger.warning(
                        "No timestamp field found, fetching all documents",
                        collection=self.collection_name
                    )
                    all_docs = await self.fetch_all()
                    documents = [doc for doc in all_docs if doc.last_modified > timestamp]
            
            logger.info(
                "Fetched modified Firestore documents",
                collection=self.collection_name,
                count=len(documents)
            )
            return documents
        
        except Exception as e:
            logger.error(
                "Failed to fetch modified Firestore documents",
                collection=self.collection_name,
                error=str(e)
            )
            raise
    
    async def get_all_document_ids(self) -> List[str]:
        """
        Get all current document IDs.
        
        Returns:
            List of document IDs
        """
        try:
            docs = self.collection_ref.stream()
            document_ids = [
                f"firestore_{self.collection_name}_{doc.id}"
                for doc in docs
            ]
            
            logger.debug(
                "Retrieved Firestore document IDs",
                collection=self.collection_name,
                count=len(document_ids)
            )
            return document_ids
        
        except Exception as e:
            logger.error(
                "Failed to get Firestore document IDs",
                collection=self.collection_name,
                error=str(e)
            )
            raise
