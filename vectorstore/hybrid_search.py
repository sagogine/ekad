"""Hybrid search combining dense (vector) and sparse (BM25) retrieval."""
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from core.embeddings import embedding_service
from vectorstore.qdrant_manager import qdrant_manager
from core.logging import get_logger

logger = get_logger(__name__)


class HybridSearchEngine:
    """Hybrid search engine combining dense and sparse retrieval."""
    
    def __init__(self):
        """Initialize hybrid search engine."""
        # BM25 indexes per business area (in-memory for MVP)
        self.bm25_indexes: Dict[str, BM25Okapi] = {}
        self.bm25_documents: Dict[str, List[Dict[str, Any]]] = {}
        logger.info("Hybrid search engine initialized")
    
    def build_bm25_index(
        self,
        business_area: str,
        documents: List[Dict[str, Any]]
    ) -> None:
        """
        Build BM25 index for a business area.
        
        Args:
            business_area: Business area identifier
            documents: List of documents with 'content' field
        """
        try:
            # Tokenize documents (simple whitespace tokenization)
            tokenized_docs = [
                doc.get("content", "").lower().split()
                for doc in documents
            ]
            
            # Create BM25 index
            self.bm25_indexes[business_area] = BM25Okapi(tokenized_docs)
            self.bm25_documents[business_area] = documents
            
            logger.info(
                "Built BM25 index",
                business_area=business_area,
                doc_count=len(documents)
            )
        except Exception as e:
            logger.error(
                "Failed to build BM25 index",
                business_area=business_area,
                error=str(e)
            )
            raise
    
    def bm25_search(
        self,
        business_area: str,
        query: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25 search.
        
        Args:
            business_area: Business area identifier
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of search results with BM25 scores
        """
        if business_area not in self.bm25_indexes:
            logger.warning("BM25 index not found", business_area=business_area)
            return []
        
        try:
            # Tokenize query
            tokenized_query = query.lower().split()
            
            # Get BM25 scores
            bm25_index = self.bm25_indexes[business_area]
            scores = bm25_index.get_scores(tokenized_query)
            
            # Get top-k documents
            documents = self.bm25_documents[business_area]
            results = [
                {
                    "document": documents[i],
                    "score": float(scores[i]),
                    "rank": i
                }
                for i in range(len(documents))
            ]
            
            # Sort by score and take top-k
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]
            
            logger.debug(
                "BM25 search completed",
                business_area=business_area,
                results_count=len(results)
            )
            
            return results
        except Exception as e:
            logger.error(
                "BM25 search failed",
                business_area=business_area,
                error=str(e)
            )
            raise
    
    async def dense_search(
        self,
        business_area: str,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform dense (vector) search.
        
        Args:
            business_area: Business area identifier
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of search results with similarity scores
        """
        try:
            # Generate query embedding
            query_vector = await embedding_service.embed_query(query)
            
            # Search in Qdrant
            results = qdrant_manager.search(
                business_area=business_area,
                query_vector=query_vector,
                limit=top_k,
                filters=filters
            )
            
            logger.debug(
                "Dense search completed",
                business_area=business_area,
                results_count=len(results)
            )
            
            return results
        except Exception as e:
            logger.error(
                "Dense search failed",
                business_area=business_area,
                error=str(e)
            )
            raise
    
    def reciprocal_rank_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Combine dense and BM25 results using Reciprocal Rank Fusion.
        
        Args:
            dense_results: Results from dense search
            bm25_results: Results from BM25 search
            k: Constant for RRF formula (default: 60)
            
        Returns:
            Fused and re-ranked results
        """
        try:
            # Create score dictionary
            rrf_scores: Dict[str, float] = {}
            document_map: Dict[str, Dict[str, Any]] = {}
            
            # Add dense results
            for rank, result in enumerate(dense_results, start=1):
                doc_id = result.get("id") or result.get("payload", {}).get("document_id")
                if doc_id:
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)
                    document_map[doc_id] = result
            
            # Add BM25 results
            for rank, result in enumerate(bm25_results, start=1):
                doc = result.get("document", {})
                doc_id = doc.get("id") or doc.get("document_id")
                if doc_id:
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)
                    if doc_id not in document_map:
                        document_map[doc_id] = {"payload": doc}
            
            # Sort by RRF score
            fused_results = [
                {
                    "id": doc_id,
                    "rrf_score": score,
                    "payload": document_map[doc_id].get("payload", document_map[doc_id])
                }
                for doc_id, score in rrf_scores.items()
            ]
            fused_results.sort(key=lambda x: x["rrf_score"], reverse=True)
            
            logger.debug(
                "RRF fusion completed",
                dense_count=len(dense_results),
                bm25_count=len(bm25_results),
                fused_count=len(fused_results)
            )
            
            return fused_results
        except Exception as e:
            logger.error("RRF fusion failed", error=str(e))
            raise
    
    async def hybrid_search(
        self,
        business_area: str,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining dense and BM25.
        
        Args:
            business_area: Business area identifier
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            Fused search results
        """
        try:
            # Perform both searches
            dense_results = await self.dense_search(
                business_area=business_area,
                query=query,
                top_k=top_k * 2,  # Get more results for fusion
                filters=filters
            )
            
            bm25_results = self.bm25_search(
                business_area=business_area,
                query=query,
                top_k=top_k * 2
            )
            
            # Fuse results
            fused_results = self.reciprocal_rank_fusion(
                dense_results=dense_results,
                bm25_results=bm25_results
            )
            
            # Return top-k
            final_results = fused_results[:top_k]
            
            logger.info(
                "Hybrid search completed",
                business_area=business_area,
                query=query[:50],
                results_count=len(final_results)
            )
            
            return final_results
        except Exception as e:
            logger.error(
                "Hybrid search failed",
                business_area=business_area,
                error=str(e)
            )
            raise


# Global hybrid search engine instance
hybrid_search_engine = HybridSearchEngine()
