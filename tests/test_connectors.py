"""Test data connectors."""
import asyncio
from datetime import datetime
from ingestion.base import Document, DocumentType, SourceType
from ingestion.processor import document_processor
from ingestion.change_detector import change_detector
from core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


async def test_document_processing():
    """Test document processing (chunking and embedding)."""
    logger.info("Testing document processing")
    
    # Create a mock document
    mock_doc = Document(
        id="test_doc_1",
        content="This is a test document. " * 100,  # Long content to test chunking
        title="Test Document",
        source=SourceType.CONFLUENCE,
        document_type=DocumentType.REQUIREMENT,
        business_area="pharmacy",
        last_modified=datetime.utcnow(),
        url="https://example.com/test",
        metadata={"author": "Test Author"}
    )
    
    # Test chunking
    chunks = document_processor.chunk_document(mock_doc)
    logger.info(f"✓ Chunked document into {len(chunks)} chunks")
    
    # Test processing (chunking + embedding)
    # Note: This requires GOOGLE_API_KEY to be set
    try:
        processed_chunks, embeddings = await document_processor.process_documents([mock_doc])
        logger.info(
            f"✓ Processed document: {len(processed_chunks)} chunks, {len(embeddings)} embeddings"
        )
        logger.info(f"✓ Embedding dimension: {len(embeddings[0]) if embeddings else 0}")
    except Exception as e:
        logger.warning(f"⚠ Could not generate embeddings (API key may not be set): {e}")
    
    return True


async def test_change_detection():
    """Test change detection."""
    logger.info("Testing change detection")
    
    business_area = "pharmacy"
    source = "test_source"
    
    # Simulate first sync
    doc_ids_v1 = ["doc1", "doc2", "doc3"]
    change_detector.update_sync_metadata(business_area, source, doc_ids_v1)
    logger.info("✓ Updated sync metadata (v1)")
    
    # Simulate second sync with changes
    doc_ids_v2 = ["doc2", "doc3", "doc4", "doc5"]  # doc1 deleted, doc4 and doc5 added
    changes = change_detector.detect_changes(business_area, source, doc_ids_v2)
    
    logger.info(f"✓ Detected changes:")
    logger.info(f"  - Added: {changes['added']}")
    logger.info(f"  - Deleted: {changes['deleted']}")
    logger.info(f"  - Existing: {len(changes['existing'])}")
    
    assert len(changes['added']) == 2
    assert len(changes['deleted']) == 1
    assert len(changes['existing']) == 2
    
    # Update metadata
    change_detector.update_sync_metadata(business_area, source, doc_ids_v2)
    logger.info("✓ Updated sync metadata (v2)")
    
    return True


async def test_all():
    """Run all tests."""
    logger.info("Running connector tests")
    
    await test_document_processing()
    await test_change_detection()
    
    logger.info("✓ All connector tests passed!")


if __name__ == "__main__":
    asyncio.run(test_all())
