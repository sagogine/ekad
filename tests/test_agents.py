"""Test multi-agent workflow."""
import asyncio
from agents.graph import knowledge_workflow
from core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


async def test_workflow():
    """Test the multi-agent workflow."""
    logger.info("Testing multi-agent workflow")
    
    # Test query (will fail without data, but tests the flow)
    query = "What is the adjudication process?"
    business_area = "pharmacy"
    
    logger.info(f"Running workflow with query: {query}")
    
    try:
        result = await knowledge_workflow.run(
            query=query,
            business_area=business_area,
            max_iterations=2
        )
        
        logger.info("✓ Workflow completed successfully")
        logger.info(f"Response: {result['response'][:200]}...")
        logger.info(f"Sources: {len(result['sources'])}")
        logger.info(f"Metadata: {result['metadata']}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Workflow failed: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_workflow())
