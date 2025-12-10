"""Lineage retriever for searching data lineage and relationships."""
from typing import Any, Dict, List, Optional
from core.config import settings
from core.logging import get_logger
from vectorstore.hybrid_search import hybrid_search_engine
from .base import RetrievedDocument, RetrievalResult, Retriever

logger = get_logger(__name__)


class LineageRetriever(Retriever):
    """Lineage-specific retriever that searches lineage documents and relationships."""

    name = "lineage"

    def __init__(self):
        logger.info("Lineage retriever initialized")

    async def retrieve(
        self,
        query: str,
        business_area: str,
        *,
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        Retrieve lineage documents using hybrid search with lineage-specific filters.

        Args:
            query: The search query (e.g., table name, pipeline name, entity FQN)
            business_area: The business area to search within
            limit: Maximum number of documents to retrieve
            filters: Optional metadata filters (e.g., asset_type, service)

        Returns:
            RetrievalResult with lineage documents
        """
        try:
            # Build filters for lineage documents
            lineage_filters = {
                "source": "openmetadata",
                **(filters or {})
            }

            # First, search for assets matching the query
            results = await hybrid_search_engine.hybrid_search(
                query=query,
                business_area=business_area,
                top_k=limit,
                filters=lineage_filters
            )

            # Transform results to RetrievedDocument format
            documents: List[RetrievedDocument] = []
            seen_entities: set[str] = set()

            for result in results:
                payload = result.get("payload", {})
                entity_fqn = payload.get("fully_qualified_name") or payload.get("entity_fqn")
                
                if entity_fqn and entity_fqn in seen_entities:
                    continue
                
                if entity_fqn:
                    seen_entities.add(entity_fqn)

                documents.append(
                    RetrievedDocument(
                        content=payload.get("content", ""),
                        title=payload.get("title", ""),
                        source=payload.get("source", "openmetadata"),
                        document_type=payload.get("asset_type", "lineage"),
                        url=payload.get("url", ""),
                        score=result.get("rrf_score", 0.0),
                        metadata={
                            "asset_type": payload.get("asset_type"),
                            "fully_qualified_name": entity_fqn,
                            "service": payload.get("service"),
                            "upstream_count": payload.get("upstream_count"),
                            "downstream_count": payload.get("downstream_count"),
                            **{k: v for k, v in payload.items() 
                               if k not in ["title", "content", "source", "asset_type", "fully_qualified_name", "url"]}
                        }
                    )
                )

            # If we found lineage documents, try to expand with related entities
            if documents and len(documents) < limit:
                # Extract entity FQNs from lineage content
                related_entities = self._extract_related_entities(documents)
                
                if related_entities:
                    # Search for related entities
                    for entity in related_entities[:limit - len(documents)]:
                        if entity in seen_entities:
                            continue
                        
                        related_results = await hybrid_search_engine.hybrid_search(
                            query=entity,
                            business_area=business_area,
                            top_k=1,
                            filters=lineage_filters
                        )
                        
                        for result in related_results:
                            payload = result.get("payload", {})
                            entity_fqn = payload.get("fully_qualified_name") or payload.get("entity_fqn")
                            
                            if entity_fqn and entity_fqn not in seen_entities:
                                seen_entities.add(entity_fqn)
                                documents.append(
                                    RetrievedDocument(
                                        content=payload.get("content", ""),
                                        title=payload.get("title", ""),
                                        source=payload.get("source", "openmetadata"),
                                        document_type=payload.get("asset_type", "lineage"),
                                        url=payload.get("url", ""),
                                        score=result.get("rrf_score", 0.0) * 0.8,  # Lower score for related
                                        metadata={
                                            "asset_type": payload.get("asset_type"),
                                            "fully_qualified_name": entity_fqn,
                                            "service": payload.get("service"),
                                            "is_related": True,
                                            **{k: v for k, v in payload.items() 
                                               if k not in ["title", "content", "source", "asset_type", "fully_qualified_name", "url"]}
                                        }
                                    )
                                )

            return RetrievalResult(
                documents=documents,
                retriever_name="lineage",
                source="openmetadata",
                message=f"Retrieved {len(documents)} lineage documents"
            )

        except Exception as e:
            logger.error(
                "Lineage retrieval failed",
                business_area=business_area,
                query=query,
                error=str(e)
            )
            return RetrievalResult(
                documents=[],
                retriever_name="lineage",
                source="openmetadata",
                message="Lineage retrieval failed",
                error=str(e)
            )

    def _extract_related_entities(self, documents: List[RetrievedDocument]) -> List[str]:
        """
        Extract related entity FQNs from lineage document content.
        
        Args:
            documents: Retrieved lineage documents
            
        Returns:
            List of entity FQNs mentioned in the documents
        """
        entities = []
        for doc in documents:
            # Look for FQNs in content (simplified extraction)
            content = doc.content
            # Extract lines that look like entity references
            lines = content.split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("- ") and ("." in line or "/" in line):
                    # Potential entity FQN
                    entity = line[2:].strip()
                    if len(entity) > 3 and entity not in entities:
                        entities.append(entity)
        return entities


# Global lineage retriever instance
lineage_retriever = LineageRetriever()

