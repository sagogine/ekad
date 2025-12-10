"""Dispatcher for selecting and running retrievers based on configuration."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping
from core.config import settings
from core.logging import get_logger
from .base import RetrievalResult, Retriever
from .document_retriever import documentation_retriever
from .code_retriever import code_retriever
from .lineage_retriever import lineage_retriever

# Conditional import for graph retriever
try:
    from .graph_retriever import graph_retriever
    GRAPH_RETRIEVER_AVAILABLE = True
except ImportError:
    GRAPH_RETRIEVER_AVAILABLE = False
    graph_retriever = None

logger = get_logger(__name__)


DEFAULT_SOURCE_RETRIEVERS: Mapping[str, List[str]] = {
    "confluence": ["docs"],
    "firestore": ["docs"],
    "gitlab": ["code"],
    "openmetadata": ["lineage"],
    "codeql": ["graph"],  # Code graph (optional)
}


class RetrieverDispatcher:
    """Dispatch retrievers dynamically per business area and source."""

    def __init__(self):
        self._registry: Dict[str, Retriever] = {}
        self._register_default_retrievers()

    def _register_default_retrievers(self) -> None:
        """Register built-in retrievers."""
        self.register_retriever(documentation_retriever)
        self.register_retriever(code_retriever)
        self.register_retriever(lineage_retriever)
        
        # Conditionally register graph retriever (only if CodeQL enabled and Neo4j available)
        if GRAPH_RETRIEVER_AVAILABLE and graph_retriever:
            if settings.codeql_enabled and graph_retriever.is_available():
                self.register_retriever(graph_retriever)
                logger.info("Graph retriever registered (CodeQL enabled)")
            else:
                logger.debug("Graph retriever not registered (CodeQL disabled or Neo4j unavailable)")

    def register_retriever(self, retriever: Retriever) -> None:
        """Register a retriever by name."""
        self._registry[retriever.name] = retriever

    def available_retrievers(self) -> Iterable[str]:
        """List registered retriever names."""
        return self._registry.keys()

    async def retrieve(
        self,
        query: str,
        business_area: str,
        *,
        limit: int = 5,
        sources: List[str] | None = None,
        filters: Dict[str, Any] | None = None
    ) -> Dict[str, List[RetrievalResult]]:
        """
        Execute retrieval across requested sources.
        """
        if business_area not in settings.business_areas_list:
            raise ValueError(
                f"Invalid business area '{business_area}'. "
                f"Valid options: {settings.business_areas_list}"
            )

        source_configs = settings.sources_config_map.get(business_area, {})

        if not source_configs:
            logger.warning(
                "No sources configured for business area",
                business_area=business_area
            )

        if sources:
            source_configs = {
                source: source_configs[source]
                for source in sources
                if source in source_configs
            }

        overrides = settings.retriever_overrides_map.get(business_area, {})

        results: Dict[str, List[RetrievalResult]] = {}

        for source_name, source_config in source_configs.items():
            retriever_names = overrides.get(
                source_name,
                DEFAULT_SOURCE_RETRIEVERS.get(source_name)
            )

            if not retriever_names:
                logger.error(
                    "No retrievers configured for source",
                    business_area=business_area,
                    source=source_name
                )
                results[source_name] = [
                    RetrievalResult(
                        documents=[],
                        retriever_name="none",
                        source=source_name,
                        message="no_retriever",
                        error=f"No retriever configured for source '{source_name}'"
                    )
                ]
                continue

            source_results: List[RetrievalResult] = []
            for retriever_name in retriever_names:
                retriever = self._registry.get(retriever_name)
                if not retriever:
                    logger.error(
                        "Retriever not registered; skipping",
                        business_area=business_area,
                        source=source_name,
                        retriever=retriever_name
                    )
                    source_results.append(
                        RetrievalResult(
                            documents=[],
                            retriever_name=retriever_name,
                            source=source_name,
                            message="retriever_not_found",
                            error=f"Retriever '{retriever_name}' is not registered."
                        )
                    )
                    continue

                combined_filters = dict(filters or {})
                combined_filters.setdefault("source", source_name)

                result = await retriever.retrieve(
                    query=query,
                    business_area=business_area,
                    limit=limit,
                    filters=combined_filters
                )
                source_results.append(result)

            results[source_name] = source_results

        return results


retriever_dispatcher = RetrieverDispatcher()

