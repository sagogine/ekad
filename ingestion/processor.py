"""Document processing: chunking and embedding generation."""
from typing import List, Dict, Any
import hashlib
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ingestion.base import Document
from core.config import settings
from core.embeddings import embedding_service
from core.logging import get_logger

logger = get_logger(__name__)


class DocumentProcessor:
    """Processes documents for ingestion into vector store."""
    
    def __init__(self):
        """Initialize document processor."""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        logger.info(
            "Document processor initialized",
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )
    
    def _generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        """
        Generate unique ID for a chunk.
        
        Args:
            doc_id: Document ID
            chunk_index: Chunk index
            
        Returns:
            Chunk ID
        """
        return f"{doc_id}_chunk_{chunk_index}"
    
    def chunk_document(self, document: Document) -> List[Dict[str, Any]]:
        """
        Chunk a document into smaller pieces.
        
        Args:
            document: Document to chunk
            
        Returns:
            List of chunk dictionaries
        """
        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(document.content)
            
            # Create chunk documents
            chunk_docs = []
            for i, chunk_text in enumerate(chunks):
                chunk_id = self._generate_chunk_id(document.id, i)
                
                chunk_doc = {
                    "id": chunk_id,
                    "content": chunk_text,
                    "title": document.title,
                    "source": document.source.value,
                    "document_type": document.document_type.value,
                    "business_area": document.business_area,
                    "last_modified": document.last_modified.isoformat(),
                    "url": document.url,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "parent_document_id": document.id,
                    **document.metadata
                }
                chunk_docs.append(chunk_doc)
            
            logger.debug(
                "Chunked document",
                doc_id=document.id,
                chunks=len(chunk_docs)
            )
            
            return chunk_docs
        except Exception as e:
            logger.error(
                "Failed to chunk document",
                doc_id=document.id,
                error=str(e)
            )
            raise
    
    async def process_documents(
        self,
        documents: List[Document]
    ) -> tuple[List[Dict[str, Any]], List[List[float]]]:
        """
        Process documents: chunk and generate embeddings.
        
        Args:
            documents: List of documents to process
            
        Returns:
            Tuple of (chunk documents, embeddings)
        """
        try:
            logger.info("Processing documents", count=len(documents))
            
            # Chunk all documents
            all_chunks = []
            for doc in documents:
                chunks = self.chunk_document(doc)
                all_chunks.extend(chunks)
            
            logger.info("Chunked documents", total_chunks=len(all_chunks))
            
            # Generate embeddings in batches
            embeddings = []
            batch_size = settings.ingestion_batch_size
            
            for i in range(0, len(all_chunks), batch_size):
                batch = all_chunks[i:i + batch_size]
                batch_texts = [chunk["content"] for chunk in batch]
                
                try:
                    batch_embeddings = await embedding_service.embed_documents(batch_texts)
                    embeddings.extend(batch_embeddings)
                    
                    logger.info(
                        "Generated embeddings",
                        batch=f"{i // batch_size + 1}/{(len(all_chunks) + batch_size - 1) // batch_size}",
                        count=len(batch_embeddings)
                    )
                except Exception as e:
                    logger.error(
                        "Failed to generate embeddings for batch",
                        batch_start=i,
                        error=str(e)
                    )
                    # Continue with next batch
                    # Add zero vectors as placeholders for failed batch
                    embeddings.extend([[0.0] * settings.embedding_dimension] * len(batch))
            
            logger.info(
                "Processed documents",
                documents=len(documents),
                chunks=len(all_chunks),
                embeddings=len(embeddings)
            )
            
            return all_chunks, embeddings
        except Exception as e:
            logger.error("Failed to process documents", error=str(e))
            raise


# Global document processor instance
document_processor = DocumentProcessor()
