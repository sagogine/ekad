"""Embedding generation using Google Gemini."""
from typing import List
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Service for generating embeddings using Google Gemini."""
    
    def __init__(self):
        """Initialize the embedding service."""
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key,
        )
        logger.info("Embedding service initialized", model=settings.embedding_model)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def embed_query(self, text: str) -> List[float]:
        """
        Generate embedding for a query text.
        
        Args:
            text: Query text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            embedding = await self.embeddings.aembed_query(text)
            logger.debug("Generated query embedding", text_length=len(text))
            return embedding
        except Exception as e:
            logger.error("Failed to generate query embedding", error=str(e))
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple documents.
        
        Args:
            texts: List of document texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            embeddings = await self.embeddings.aembed_documents(texts)
            logger.debug("Generated document embeddings", count=len(texts))
            return embeddings
        except Exception as e:
            logger.error("Failed to generate document embeddings", error=str(e))
            raise
    
    def embed_query_sync(self, text: str) -> List[float]:
        """
        Generate embedding for a query text (synchronous).
        
        Args:
            text: Query text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            embedding = self.embeddings.embed_query(text)
            logger.debug("Generated query embedding (sync)", text_length=len(text))
            return embedding
        except Exception as e:
            logger.error("Failed to generate query embedding (sync)", error=str(e))
            raise
    
    def embed_documents_sync(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple documents (synchronous).
        
        Args:
            texts: List of document texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            embeddings = self.embeddings.embed_documents(texts)
            logger.debug("Generated document embeddings (sync)", count=len(texts))
            return embeddings
        except Exception as e:
            logger.error("Failed to generate document embeddings (sync)", error=str(e))
            raise


# Global embedding service instance
embedding_service = EmbeddingService()
