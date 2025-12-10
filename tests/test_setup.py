"""Test basic setup and connectivity."""
import asyncio
import pytest
from core.config import settings
from core.logging import configure_logging, get_logger
from vectorstore.qdrant_manager import qdrant_manager

configure_logging()
logger = get_logger(__name__)


@pytest.mark.asyncio
async def test_setup():
    """Test basic setup."""
    logger.info("Testing Traceback setup")
    
    # Test configuration
    logger.info("Configuration loaded", business_areas=settings.business_areas_list)
    
    # Test Qdrant connection
    try:
        qdrant_manager.initialize_collections()
        logger.info("✓ Qdrant collections initialized")
        
        for business_area in settings.business_areas_list:
            info = qdrant_manager.get_collection_info(business_area)
            logger.info(f"✓ Collection {business_area}", info=info)
    except Exception as e:
        logger.error("✗ Qdrant connection failed", error=str(e))
        return False
    
    logger.info("✓ All tests passed!")
    return True


if __name__ == "__main__":
    asyncio.run(test_setup())
