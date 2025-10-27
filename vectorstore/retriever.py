"""RAG retrieval system with bounded context enforcement."""
from typing import List, Dict, Any, Optional
from vectorstore.hybrid_search import hybrid_search_engine
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class BoundedContextRetriever:
    """Retriever with strict bounded context enforcement."""
    
    def __init__(self):
        """Initialize retriever."""
        logger.info("Bounded context retriever initialized")
    
    async def retrieve(
        self,
        query: str,
        business_area: str,
        top_k: int = None,
        source_filter: Optional[List[str]] = None,
        document_type_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve documents with bounded context enforcement.
        
        Args:
            query: Search query
            business_area: Business area (pharmacy/supply_chain)
            top_k: Number of results to return (default from settings)
            source_filter: Filter by source types (confluence/firestore/gitlab)
            document_type_filter: Filter by document types
            
        Returns:
            Dictionary with results and metadata
        """
        if top_k is None:
            top_k = settings.top_k_retrieval
        
        try:
            logger.info(
                "Retrieving documents",
                query=query[:50],
                business_area=business_area,
                top_k=top_k
            )
            
            # Validate business area
            if business_area not in settings.business_areas_list:
                raise ValueError(
                    f"Invalid business area: {business_area}. "
                    f"Valid options: {settings.business_areas_list}"
                )
            
            # Build metadata filters
            filters = {}
            if source_filter:
                filters['source'] = source_filter
            if document_type_filter:
                filters['document_type'] = document_type_filter
            
            # Perform hybrid search
            results = await hybrid_search_engine.hybrid_search(
                business_area=business_area,
                query=query,
                top_k=top_k,
                filters=filters if filters else None
            )
            
            # Check if results found
            if not results:
                logger.warning(
                    "No results found in bounded context",
                    business_area=business_area,
                    query=query[:50]
                )
                return {
                    "results": [],
                    "count": 0,
                    "business_area": business_area,
                    "message": f"No information found in {business_area} context"
                }
            
            # Group results by source
            results_by_source = self._group_by_source(results)
            
            # Format results
            formatted_results = [
                {
                    "content": r.get("payload", {}).get("content", ""),
                    "title": r.get("payload", {}).get("title", ""),
                    "source": r.get("payload", {}).get("source", ""),
                    "document_type": r.get("payload", {}).get("document_type", ""),
                    "url": r.get("payload", {}).get("url", ""),
                    "score": r.get("rrf_score", 0.0),
                    "metadata": {
                        k: v for k, v in r.get("payload", {}).items()
                        if k not in ["content", "title", "source", "document_type", "url"]
                    }
                }
                for r in results
            ]
            
            logger.info(
                "Retrieved documents",
                business_area=business_area,
                count=len(formatted_results),
                sources=list(results_by_source.keys())
            )
            
            return {
                "results": formatted_results,
                "count": len(formatted_results),
                "business_area": business_area,
                "results_by_source": results_by_source,
                "message": "success"
            }
        
        except Exception as e:
            logger.error(
                "Retrieval failed",
                business_area=business_area,
                error=str(e)
            )
            raise
    
    def _group_by_source(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Group results by source type.
        
        Args:
            results: List of search results
            
        Returns:
            Dictionary mapping source to count
        """
        by_source = {}
        for result in results:
            source = result.get("payload", {}).get("source", "unknown")
            by_source[source] = by_source.get(source, 0) + 1
        return by_source
    
    async def retrieve_multi_source(
        self,
        query: str,
        business_area: str,
        sources: List[str] = None,
        top_k_per_source: int = 3
    ) -> Dict[str, Any]:
        """
        Retrieve from multiple sources ensuring representation from each.
        
        This is useful for queries like "show me requirements + config + code".
        
        Args:
            query: Search query
            business_area: Business area
            sources: List of sources to retrieve from (default: all 3)
            top_k_per_source: Number of results per source
            
        Returns:
            Dictionary with results grouped by source
        """
        if sources is None:
            sources = ["confluence", "firestore", "gitlab"]
        
        try:
            logger.info(
                "Multi-source retrieval",
                query=query[:50],
                business_area=business_area,
                sources=sources
            )
            
            all_results = []
            results_by_source = {}
            
            for source in sources:
                try:
                    # Retrieve from this source
                    source_results = await self.retrieve(
                        query=query,
                        business_area=business_area,
                        top_k=top_k_per_source,
                        source_filter=[source]
                    )
                    
                    results = source_results.get("results", [])
                    if results:
                        results_by_source[source] = results
                        all_results.extend(results)
                    else:
                        logger.warning(
                            f"No results from {source}",
                            business_area=business_area
                        )
                        results_by_source[source] = []
                
                except Exception as e:
                    logger.error(
                        f"Failed to retrieve from {source}",
                        error=str(e)
                    )
                    results_by_source[source] = []
            
            # Check coverage
            missing_sources = [s for s in sources if not results_by_source.get(s)]
            
            message = "success"
            if missing_sources:
                message = f"Partial results: no data found from {', '.join(missing_sources)}"
            
            logger.info(
                "Multi-source retrieval completed",
                business_area=business_area,
                total_results=len(all_results),
                sources_with_results=len([s for s in sources if results_by_source.get(s)])
            )
            
            return {
                "results": all_results,
                "results_by_source": results_by_source,
                "count": len(all_results),
                "business_area": business_area,
                "message": message,
                "missing_sources": missing_sources
            }
        
        except Exception as e:
            logger.error(
                "Multi-source retrieval failed",
                business_area=business_area,
                error=str(e)
            )
            raise


# Global retriever instance
bounded_retriever = BoundedContextRetriever()
