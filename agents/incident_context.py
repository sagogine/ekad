"""Incident context agent that orchestrates retrieval across sources."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from core.logging import get_logger
from vectorstore.retrievers.dispatcher import retriever_dispatcher
from .state import IncidentAgentState

# Optional graph retriever import
try:
    from vectorstore.retrievers.graph_retriever import graph_retriever
    GRAPH_AVAILABLE = True
except ImportError:
    GRAPH_AVAILABLE = False
    graph_retriever = None

logger = get_logger(__name__)


class IncidentContextAgent:
    """Agent responsible for collecting incident context from all sources."""

    name = "incident_context"

    async def build_context(self, state: IncidentAgentState) -> IncidentAgentState:
        """Collect context using configured retrievers."""
        query = state.get("query", "")
        business_area = state.get("business_area", "")
        incident_payload = state.get("incident_payload", {})

        logger.info(
            "Incident context agent starting",
            business_area=business_area,
            query=query[:80],
            payload_keys=list(incident_payload.keys())
        )

        # Determine which sources are available
        sources = state.get("retrieval_plan", {}).get("sources")
        if sources is None:
            sources = list(
                retriever_dispatcher.available_retrievers()
            )  # Placeholder; actual source selection happens via dispatcher

        results = await retriever_dispatcher.retrieve(
            query=query,
            business_area=business_area,
            sources=state.get("retrieval_plan", {}).get("sources"),
            limit=state.get("retrieval_plan", {}).get("limit", 5),
            filters=state.get("retrieval_plan", {}).get("filters")
        )

        # Optionally query graph retriever if available and CodeQL enabled
        if GRAPH_AVAILABLE and graph_retriever and graph_retriever.is_available():
            try:
                graph_results = await graph_retriever.retrieve(
                    query=query,
                    business_area=business_area,
                    limit=state.get("retrieval_plan", {}).get("limit", 5),
                    filters=state.get("retrieval_plan", {}).get("filters")
                )
                
                # Add graph results to results dict
                if graph_results.documents:
                    if "codeql" not in results:
                        results["codeql"] = []
                    results["codeql"].append({
                        "retriever_name": "graph",
                        "source": "code_graph",
                        "documents": [
                            {
                                "title": doc.title,
                                "content": doc.content,
                                "url": doc.url,
                                "score": doc.score,
                                "document_type": doc.document_type,
                                "metadata": doc.metadata
                            }
                            for doc in graph_results.documents
                        ],
                        "message": graph_results.message,
                        "error": graph_results.error
                    })
                    logger.info(
                        "Graph context retrieved",
                        business_area=business_area,
                        documents=len(graph_results.documents)
                    )
            except Exception as e:
                logger.warning(
                    "Graph retrieval failed, continuing without graph context",
                    error=str(e)
                )

        logger.info(
            "Incident context retrieval completed",
            business_area=business_area,
            sources=list(results.keys())
        )

        context = self._summarize_results(results)

        return {
            **state,
            "retriever_results": results,
            "incident_context": context,
        }

    def _summarize_results(
        self,
        results: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Create a lightweight summary structure from retriever results.
        """
        summary: Dict[str, Any] = {
            "sources": [],
            "documents": []
        }

        for source, retriever_results in results.items():
            source_entry = {"source": source, "retrievers": []}
            for result in retriever_results:
                status = {
                    "retriever": result["retriever_name"],
                    "message": result["message"],
                    "documents": len(result["documents"]),
                    "error": result.get("error")
                }
                source_entry["retrievers"].append(status)

                for doc in result["documents"]:
                    summary["documents"].append({
                        "source": source,
                        "retriever": result["retriever_name"],
                        "title": doc["title"],
                        "url": doc.get("url"),
                        "score": doc.get("score"),
                        "document_type": doc.get("document_type"),
                        "metadata": doc.get("metadata", {})
                    })

            summary["sources"].append(source_entry)

        return summary


incident_context_agent = IncidentContextAgent()

