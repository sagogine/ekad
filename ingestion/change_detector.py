"""Change detection and ingestion metadata management."""
import json
from typing import Dict, List, Optional
from datetime import datetime, UTC
from pathlib import Path
from core.logging import get_logger

logger = get_logger(__name__)


class ChangeDetector:
    """Manages ingestion metadata and change detection."""
    
    def __init__(self, metadata_file: str = "data/ingestion_metadata.json"):
        """
        Initialize change detector.
        
        Args:
            metadata_file: Path to metadata file
        """
        self.metadata_file = Path(metadata_file)
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self.metadata = self._load_metadata()
        logger.info("Change detector initialized", metadata_file=str(self.metadata_file))
    
    def _load_metadata(self) -> Dict:
        """
        Load metadata from file.
        
        Returns:
            Metadata dictionary
        """
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to load metadata", error=str(e))
                return {}
        return {}
    
    def _save_metadata(self) -> None:
        """Save metadata to file."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
            logger.debug("Saved metadata", file=str(self.metadata_file))
        except Exception as e:
            logger.error("Failed to save metadata", error=str(e))
    
    def get_last_sync_timestamp(
        self,
        business_area: str,
        source: str
    ) -> Optional[datetime]:
        """
        Get last sync timestamp for a source.
        
        Args:
            business_area: Business area identifier
            source: Source identifier (e.g., 'confluence_SPACE', 'gitlab_project')
            
        Returns:
            Last sync timestamp or None if never synced
        """
        key = f"{business_area}_{source}"
        if key in self.metadata:
            timestamp_str = self.metadata[key].get('last_sync_timestamp')
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
        return None
    
    def get_stored_document_ids(
        self,
        business_area: str,
        source: str
    ) -> List[str]:
        """
        Get stored document IDs for a source.
        
        Args:
            business_area: Business area identifier
            source: Source identifier
            
        Returns:
            List of document IDs
        """
        key = f"{business_area}_{source}"
        if key in self.metadata:
            return self.metadata[key].get('document_ids', [])
        return []
    
    def update_sync_metadata(
        self,
        business_area: str,
        source: str,
        document_ids: List[str],
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Update sync metadata for a source.
        
        Args:
            business_area: Business area identifier
            source: Source identifier
            document_ids: List of current document IDs
            timestamp: Sync timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)
        
        key = f"{business_area}_{source}"
        self.metadata[key] = {
            'last_sync_timestamp': timestamp.isoformat(),
            'document_ids': document_ids,
            'document_count': len(document_ids)
        }
        self._save_metadata()
        
        logger.info(
            "Updated sync metadata",
            business_area=business_area,
            source=source,
            document_count=len(document_ids)
        )
    
    def detect_changes(
        self,
        business_area: str,
        source: str,
        current_document_ids: List[str]
    ) -> Dict[str, List[str]]:
        """
        Detect changes by comparing current and stored document IDs.
        
        Args:
            business_area: Business area identifier
            source: Source identifier
            current_document_ids: Current document IDs from source
            
        Returns:
            Dictionary with 'added', 'deleted', and 'existing' document IDs
        """
        stored_ids = set(self.get_stored_document_ids(business_area, source))
        current_ids = set(current_document_ids)
        
        added = list(current_ids - stored_ids)
        deleted = list(stored_ids - current_ids)
        existing = list(current_ids & stored_ids)
        
        logger.info(
            "Detected changes",
            business_area=business_area,
            source=source,
            added=len(added),
            deleted=len(deleted),
            existing=len(existing)
        )
        
        return {
            'added': added,
            'deleted': deleted,
            'existing': existing
        }


# Global change detector instance
change_detector = ChangeDetector()
