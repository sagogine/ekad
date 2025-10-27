"""Base connector interface for data sources."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class DocumentType(str, Enum):
    """Document type enumeration."""
    REQUIREMENT = "requirement"
    CONFIG = "config"
    CODE = "code"
    ISSUE = "issue"
    WIKI = "wiki"
    OTHER = "other"


class SourceType(str, Enum):
    """Source type enumeration."""
    CONFLUENCE = "confluence"
    FIRESTORE = "firestore"
    GITLAB = "gitlab"


@dataclass
class Document:
    """Unified document schema across all sources."""
    id: str
    content: str
    title: str
    source: SourceType
    document_type: DocumentType
    business_area: str
    last_modified: datetime
    url: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "title": self.title,
            "source": self.source.value,
            "document_type": self.document_type.value,
            "business_area": self.business_area,
            "last_modified": self.last_modified.isoformat(),
            "url": self.url,
            **self.metadata
        }


class BaseConnector(ABC):
    """Base connector interface for data sources."""
    
    def __init__(self, business_area: str):
        """
        Initialize connector.
        
        Args:
            business_area: Business area identifier
        """
        self.business_area = business_area
    
    @abstractmethod
    async def fetch_all(self) -> List[Document]:
        """
        Fetch all documents (initial sync).
        
        Returns:
            List of documents
        """
        pass
    
    @abstractmethod
    async def fetch_since(self, timestamp: datetime) -> List[Document]:
        """
        Fetch documents modified since timestamp (incremental sync).
        
        Args:
            timestamp: Last sync timestamp
            
        Returns:
            List of modified documents
        """
        pass
    
    @abstractmethod
    async def get_all_document_ids(self) -> List[str]:
        """
        Get all current document IDs (for deletion detection).
        
        Returns:
            List of document IDs
        """
        pass
    
    def detect_deletions(
        self,
        stored_ids: List[str],
        current_ids: List[str]
    ) -> List[str]:
        """
        Detect deleted documents by comparing stored and current IDs.
        
        Args:
            stored_ids: Previously stored document IDs
            current_ids: Current document IDs from source
            
        Returns:
            List of deleted document IDs
        """
        stored_set = set(stored_ids)
        current_set = set(current_ids)
        deleted_ids = list(stored_set - current_set)
        return deleted_ids
