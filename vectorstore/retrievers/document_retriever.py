"""Documentation retriever backed by hybrid search."""
from __future__ import annotations

from typing import Any, Dict
from vectorstore.hybrid_search import hybrid_search_engine
from core.config import settings
from core.logging import get_logger
from .base import Retriever, RetrievalResult, RetrievedDocument

logger = get_logger(__name__)


class DocumentationRetriever(Retriever):
    """Retriever that uses hybrid search for documentation sources."""

    name = "docs"

    async def retrieve(
        self,
        query: str,
        business_area: str,
        *,
        limit: int = 5,
        filters: Dict[str, Any] | None = None
    ) -> RetrievalResult:
        if business_area not in settings.business_areas_list:
            raise ValueError(
                f"Invalid business area '{business_area}'. "
                f"Valid options: {settings.business_areas_list}"
            )

        try:
            logger.info(
                "Documentation retrieval",
                query=query[:50],
                business_area=business_area,
                limit=limit,
                filters=filters
            )

            results = await hybrid_search_engine.hybrid_search(
                business_area=business_area,
                query=query,
                top_k=limit,
                filters=filters
            )

            documents = [
                RetrievedDocument(
                    title=result.get("payload", {}).get("title", ""),
                    content=result.get("payload", {}).get("content", ""),
                    source=result.get("payload", {}).get("source", ""),
                    document_type=result.get("payload", {}).get("document_type", ""),
                    score=result.get("rrf_score", 0.0),
                    url=result.get("payload", {}).get("url"),
                    metadata={
                        key: value
                        for key, value in result.get("payload", {}).items()
                        if key not in {"title", "content", "source", "document_type", "url"}
                    }
                )
                for result in results
            ]

            if not documents:
                logger.warning(
                    "Documentation retriever found no results",
                    business_area=business_area
                )

            return RetrievalResult(
                documents=documents,
                retriever_name=self.name,
                source=filters.get("source") if filters else "all",
                message="success" if documents else "no_results"
            )

        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Documentation retrieval failed",
                business_area=business_area,
                error=str(exc)
            )
            return RetrievalResult(
                documents=[],
                retriever_name=self.name,
                source=filters.get("source") if filters else "all",
                message="error",
                error=str(exc)
            )


documentation_retriever = DocumentationRetriever()

