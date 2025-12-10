"""Confluence connector for fetching documentation."""
from typing import List, Optional
from datetime import datetime
from atlassian import Confluence
from bs4 import BeautifulSoup
from ingestion.base import BaseConnector, Document, DocumentType, SourceType
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class ConfluenceConnector(BaseConnector):
    """Connector for Confluence pages."""
    
    def __init__(self, business_area: str, space_key: str):
        """
        Initialize Confluence connector.
        
        Args:
            business_area: Business area identifier
            space_key: Confluence space key
        """
        super().__init__(business_area)
        self.space_key = space_key
        
        confluence_token = settings.get_secret_value(settings.confluence_api_token, field_name="confluence_api_token")
        if not all([settings.confluence_url, settings.confluence_username, confluence_token]):
            raise ValueError("Confluence credentials not configured")
        
        self.client = Confluence(
            url=settings.confluence_url,
            username=settings.confluence_username,
            password=confluence_token,
            cloud=True
        )
        logger.info(
            "Confluence connector initialized",
            business_area=business_area,
            space_key=space_key
        )
    
    def _clean_html(self, html_content: str) -> str:
        """
        Clean HTML content to plain text.
        
        Args:
            html_content: HTML content
            
        Returns:
            Plain text content
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator='\n', strip=True)
        return text
    
    def _parse_page(self, page: dict) -> Document:
        """
        Parse Confluence page to Document.
        
        Args:
            page: Confluence page data
            
        Returns:
            Document object
        """
        page_id = page['id']
        title = page['title']
        
        # Extract body content
        body_html = page.get('body', {}).get('storage', {}).get('value', '')
        content = self._clean_html(body_html)
        
        # Extract metadata
        version = page.get('version', {})
        last_modified_str = version.get('when', datetime.utcnow().isoformat())
        last_modified = datetime.fromisoformat(last_modified_str.replace('Z', '+00:00'))
        
        author = version.get('by', {}).get('displayName', 'Unknown')
        
        # Build URL
        url = f"{settings.confluence_url}/wiki/spaces/{self.space_key}/pages/{page_id}"
        
        # Extract labels
        labels = [label['name'] for label in page.get('metadata', {}).get('labels', {}).get('results', [])]
        
        return Document(
            id=f"confluence_{self.space_key}_{page_id}",
            content=content,
            title=title,
            source=SourceType.CONFLUENCE,
            document_type=DocumentType.REQUIREMENT,
            business_area=self.business_area,
            last_modified=last_modified,
            url=url,
            metadata={
                "author": author,
                "labels": labels,
                "space_key": self.space_key,
                "page_id": page_id
            }
        )
    
    async def fetch_all(self) -> List[Document]:
        """
        Fetch all pages from Confluence space.
        
        Returns:
            List of documents
        """
        try:
            logger.info("Fetching all Confluence pages", space_key=self.space_key)
            
            documents = []
            start = 0
            limit = 50
            
            while True:
                # Fetch pages with pagination
                pages = self.client.get_all_pages_from_space(
                    space=self.space_key,
                    start=start,
                    limit=limit,
                    expand='body.storage,version,metadata.labels'
                )
                
                if not pages:
                    break
                
                for page in pages:
                    try:
                        doc = self._parse_page(page)
                        documents.append(doc)
                    except Exception as e:
                        logger.error(
                            "Failed to parse page",
                            page_id=page.get('id'),
                            error=str(e)
                        )
                
                if len(pages) < limit:
                    break
                
                start += limit
            
            logger.info(
                "Fetched Confluence pages",
                space_key=self.space_key,
                count=len(documents)
            )
            return documents
        
        except Exception as e:
            logger.error(
                "Failed to fetch Confluence pages",
                space_key=self.space_key,
                error=str(e)
            )
            raise
    
    async def fetch_since(self, timestamp: datetime) -> List[Document]:
        """
        Fetch pages modified since timestamp.
        
        Args:
            timestamp: Last sync timestamp
            
        Returns:
            List of modified documents
        """
        try:
            logger.info(
                "Fetching modified Confluence pages",
                space_key=self.space_key,
                since=timestamp.isoformat()
            )
            
            # Fetch all pages and filter by modification date
            # Note: Confluence API doesn't have a direct "modified since" filter
            # So we fetch all and filter client-side (for MVP)
            all_pages = self.client.get_all_pages_from_space(
                space=self.space_key,
                expand='body.storage,version,metadata.labels'
            )
            
            documents = []
            for page in all_pages:
                try:
                    doc = self._parse_page(page)
                    if doc.last_modified > timestamp:
                        documents.append(doc)
                except Exception as e:
                    logger.error(
                        "Failed to parse page",
                        page_id=page.get('id'),
                        error=str(e)
                    )
            
            logger.info(
                "Fetched modified Confluence pages",
                space_key=self.space_key,
                count=len(documents)
            )
            return documents
        
        except Exception as e:
            logger.error(
                "Failed to fetch modified Confluence pages",
                space_key=self.space_key,
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
            pages = self.client.get_all_pages_from_space(
                space=self.space_key,
                expand='version'
            )
            
            document_ids = [
                f"confluence_{self.space_key}_{page['id']}"
                for page in pages
            ]
            
            logger.debug(
                "Retrieved Confluence document IDs",
                space_key=self.space_key,
                count=len(document_ids)
            )
            return document_ids
        
        except Exception as e:
            logger.error(
                "Failed to get Confluence document IDs",
                space_key=self.space_key,
                error=str(e)
            )
            raise
