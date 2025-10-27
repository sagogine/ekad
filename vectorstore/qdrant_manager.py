"""Qdrant vector store manager with multi-tenant collections."""
from typing import List, Dict, Any, Optional
from datetime import datetime
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class QdrantManager:
    """Manager for Qdrant vector store with multi-tenant support."""
    
    def __init__(self):
        """Initialize Qdrant client."""
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key,
            prefer_grpc=False,  # Use HTTP instead of gRPC
            https=False,  # Use HTTP not HTTPS
        )
        logger.info(
            "Qdrant client initialized",
            host=settings.qdrant_host,
            port=settings.qdrant_port
        )
    
    def get_collection_name(self, business_area: str) -> str:
        """
        Get collection name for a business area.
        
        Args:
            business_area: Business area identifier
            
        Returns:
            Collection name
        """
        return f"{business_area}_knowledge"
    
    def create_collection(self, business_area: str) -> None:
        """
        Create a collection for a business area if it doesn't exist.
        
        Args:
            business_area: Business area identifier
        """
        collection_name = self.get_collection_name(business_area)
        
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            if any(col.name == collection_name for col in collections):
                logger.info("Collection already exists", collection=collection_name)
                return
            
            # Create collection
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE
                ),
            )
            
            # Create payload indexes for efficient filtering
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="source",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="document_type",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name="business_area",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            
            logger.info("Created collection", collection=collection_name)
        except Exception as e:
            logger.error("Failed to create collection", collection=collection_name, error=str(e))
            raise
    
    def initialize_collections(self) -> None:
        """Initialize collections for all business areas."""
        for business_area in settings.business_areas_list:
            self.create_collection(business_area)
        logger.info("Initialized all collections", business_areas=settings.business_areas_list)
    
    def upsert_documents(
        self,
        business_area: str,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> None:
        """
        Upsert documents into a collection.
        
        Args:
            business_area: Business area identifier
            documents: List of document metadata
            embeddings: List of embedding vectors
        """
        collection_name = self.get_collection_name(business_area)
        
        try:
            points = [
                PointStruct(
                    id=doc["id"],
                    vector=embedding,
                    payload={
                        **doc,
                        "indexed_at": datetime.utcnow().isoformat()
                    }
                )
                for doc, embedding in zip(documents, embeddings)
            ]
            
            self.client.upsert(
                collection_name=collection_name,
                points=points
            )
            
            logger.info(
                "Upserted documents",
                collection=collection_name,
                count=len(documents)
            )
        except Exception as e:
            logger.error(
                "Failed to upsert documents",
                collection=collection_name,
                error=str(e)
            )
            raise
    
    def search(
        self,
        business_area: str,
        query_vector: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents in a collection.
        
        Args:
            business_area: Business area identifier
            query_vector: Query embedding vector
            limit: Maximum number of results
            filters: Optional metadata filters
            
        Returns:
            List of search results with scores
        """
        collection_name = self.get_collection_name(business_area)
        
        try:
            # Build filter conditions
            query_filter = None
            if filters:
                must_conditions = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        # Multiple values - use should (OR)
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchAny(any=value)
                            )
                        )
                    else:
                        # Single value - use must (AND)
                        must_conditions.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchValue(value=value)
                            )
                        )
                
                if must_conditions:
                    query_filter = models.Filter(must=must_conditions)
            
            # Perform search
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter
            )
            
            # Format results
            formatted_results = [
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload
                }
                for result in results
            ]
            
            logger.debug(
                "Search completed",
                collection=collection_name,
                results_count=len(formatted_results)
            )
            
            return formatted_results
        except Exception as e:
            logger.error(
                "Search failed",
                collection=collection_name,
                error=str(e)
            )
            raise
    
    def delete_documents(
        self,
        business_area: str,
        document_ids: List[str]
    ) -> None:
        """
        Delete documents from a collection.
        
        Args:
            business_area: Business area identifier
            document_ids: List of document IDs to delete
        """
        collection_name = self.get_collection_name(business_area)
        
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    points=document_ids
                )
            )
            
            logger.info(
                "Deleted documents",
                collection=collection_name,
                count=len(document_ids)
            )
        except Exception as e:
            logger.error(
                "Failed to delete documents",
                collection=collection_name,
                error=str(e)
            )
            raise
    
    def get_collection_info(self, business_area: str) -> Dict[str, Any]:
        """
        Get information about a collection.
        
        Args:
            business_area: Business area identifier
            
        Returns:
            Collection information
        """
        collection_name = self.get_collection_name(business_area)
        
        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status
            }
        except Exception as e:
            logger.error(
                "Failed to get collection info",
                collection=collection_name,
                error=str(e)
            )
            raise


# Global Qdrant manager instance
qdrant_manager = QdrantManager()
