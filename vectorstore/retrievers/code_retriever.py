"""Code retriever for searching code-specific documents."""
from typing import Any, Dict, List, Optional
from core.config import settings
from core.logging import get_logger
from vectorstore.hybrid_search import hybrid_search_engine
from .base import RetrievedDocument, RetrievalResult, Retriever

logger = get_logger(__name__)


class CodeRetriever(Retriever):
    """Code-specific retriever that searches code documents with enhanced metadata filtering."""

    name = "code"

    def __init__(self):
        logger.info("Code retriever initialized")

    async def retrieve(
        self,
        query: str,
        business_area: str,
        *,
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        Retrieve code documents using hybrid search with code-specific filters.

        Args:
            query: The search query (e.g., function name, class name, SQL table)
            business_area: The business area to search within
            limit: Maximum number of documents to retrieve
            filters: Optional metadata filters (e.g., unit_type, file_type, language)

        Returns:
            RetrievalResult with code documents
        """
        try:
            # Build filters for code documents
            code_filters = {
                "document_type": "code",
                "source": "code",
                **(filters or {})
            }

            # Perform hybrid search
            results = await hybrid_search_engine.hybrid_search(
                query=query,
                business_area=business_area,
                top_k=limit,
                filters=code_filters
            )

            # Transform results to RetrievedDocument format
            documents: List[RetrievedDocument] = []
            for result in results:
                payload = result.get("payload", {})
                documents.append(
                    RetrievedDocument(
                        content=payload.get("content", ""),
                        title=payload.get("title", ""),
                        source=payload.get("source", "code"),
                        document_type=payload.get("document_type", "code"),
                        url=payload.get("url", ""),
                        score=result.get("rrf_score", 0.0),
                        metadata={
                            "unit_type": payload.get("unit_type"),
                            "unit_name": payload.get("unit_name"),
                            "file_path": payload.get("file_path"),
                            "file_type": payload.get("file_type"),
                            "line_start": payload.get("line_start"),
                            "line_end": payload.get("line_end"),
                            **{k: v for k, v in payload.items() 
                               if k not in ["title", "content", "source", "document_type", "url"]}
                        }
                    )
                )

            return RetrievalResult(
                documents=documents,
                retriever_name="code",
                source="code",
                message=f"Retrieved {len(documents)} code documents"
            )

        except Exception as e:
            logger.error(
                "Code retrieval failed",
                business_area=business_area,
                query=query,
                error=str(e)
            )
            return RetrievalResult(
                documents=[],
                retriever_name="code",
                source="code",
                message="Code retrieval failed",
                error=str(e)
            )


# Global code retriever instance
code_retriever = CodeRetriever()

