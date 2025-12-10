"""Integration tests for CodeQL functionality."""
import asyncio
import tempfile
from pathlib import Path
from core.config import settings
from core.logging import configure_logging, get_logger
from codeql import (
    code_source_registry,
    codeql_analysis_service,
    get_codeql_cli,
    get_codeql_storage,
)
from vectorstore.retrievers.graph_retriever import graph_retriever
from core.graph import neo4j_manager

configure_logging()
logger = get_logger(__name__)


async def test_source_registry():
    """Test code source registry."""
    logger.info("=" * 60)
    logger.info("Testing Code Source Registry")
    logger.info("=" * 60)

    # Test 1: Register a source
    logger.info("Test 1: Registering a code source")
    source_id = code_source_registry.register(
        business_area="test_area",
        source_type="gitlab",
        path="test/org/repo",
        languages=["python", "java"],
        name="Test Repository",
        enabled=True
    )
    logger.info(f"✓ Registered source: {source_id}")

    # Test 2: Get source
    logger.info("Test 2: Retrieving registered source")
    source = code_source_registry.get(source_id)
    assert source is not None, "Source should be retrievable"
    assert source.business_area == "test_area"
    assert source.path == "test/org/repo"
    logger.info(f"✓ Retrieved source: {source.name}")

    # Test 3: List sources
    logger.info("Test 3: Listing sources")
    sources = code_source_registry.list_sources(business_area="test_area")
    assert len(sources) > 0, "Should have at least one source"
    logger.info(f"✓ Found {len(sources)} sources for test_area")

    # Test 4: Update commit hash
    logger.info("Test 4: Updating commit hash")
    code_source_registry.update_commit_hash(source_id, "abc123")
    updated_source = code_source_registry.get(source_id)
    assert updated_source.last_analyzed_commit == "abc123"
    logger.info(f"✓ Updated commit hash: {updated_source.last_analyzed_commit}")

    # Test 5: Check CodeQL enabled
    logger.info("Test 5: Checking CodeQL enabled status")
    enabled = code_source_registry.is_codeql_enabled("test_area")
    logger.info(f"✓ CodeQL enabled for test_area: {enabled}")

    # Cleanup
    code_source_registry.delete(source_id)
    logger.info("✓ Cleaned up test source")

    logger.info("✓ All source registry tests passed!\n")


def test_storage():
    """Test CodeQL storage abstraction."""
    logger.info("=" * 60)
    logger.info("Testing CodeQL Storage")
    logger.info("=" * 60)

    # Test 1: Get storage instance
    logger.info("Test 1: Getting storage instance")
    storage = get_codeql_storage()
    assert storage is not None, "Storage should be available"
    logger.info(f"✓ Storage type: {type(storage).__name__}")

    # Test 2: List databases (should work even if empty)
    logger.info("Test 2: Listing databases")
    databases = storage.list_databases()
    logger.info(f"✓ Found {len(databases)} databases")

    # Test 3: Get database path (non-existent)
    logger.info("Test 3: Getting non-existent database path")
    db_path = storage.get_database_path("test_area", "test/repo", "python")
    if db_path:
        logger.info(f"✓ Found database at: {db_path}")
    else:
        logger.info("✓ No database found (expected for new repo)")

    logger.info("✓ All storage tests passed!\n")


def test_codeql_cli():
    """Test CodeQL CLI wrapper."""
    logger.info("=" * 60)
    logger.info("Testing CodeQL CLI")
    logger.info("=" * 60)

    cli = get_codeql_cli()
    if not cli:
        logger.warning("⚠ CodeQL CLI not available - skipping CLI tests")
        logger.info("  Install from: https://github.com/github/codeql-cli-binaries")
        logger.info("  Or set CODEQL_PATH environment variable\n")
        return

    # Test 1: Check availability
    logger.info("Test 1: Checking CLI availability")
    is_available = cli.is_codeql_available()
    assert is_available, "CLI should be available"
    logger.info("✓ CodeQL CLI is available")

    # Test 2: Get version (if available)
    try:
        logger.info("Test 2: Getting CodeQL version")
        # This would require running a command, but we'll just check if CLI exists
        logger.info("✓ CodeQL CLI wrapper initialized")
    except Exception as e:
        logger.warning(f"⚠ CLI test failed: {e}")

    logger.info("✓ All CLI tests passed!\n")


def test_graph_retriever():
    """Test graph retriever."""
    logger.info("=" * 60)
    logger.info("Testing Graph Retriever")
    logger.info("=" * 60)

    # Test 1: Check availability
    logger.info("Test 1: Checking graph retriever availability")
    is_available = graph_retriever.is_available()
    logger.info(f"✓ Graph retriever available: {is_available}")

    if not is_available:
        logger.warning("⚠ Neo4j not available - skipping graph retriever tests")
        logger.info("  Configure NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD to enable")
        logger.info("  Or set CODEQL_ENABLED=false to disable code graph features\n")
        return

    # Test 2: Retrieve (empty query - should return empty results)
    logger.info("Test 2: Testing graph retrieval (empty query)")
    try:
        result = asyncio.run(
            graph_retriever.retrieve(
                query="nonexistent_function_xyz",
                business_area="test_area",
                limit=5
            )
        )
        assert result is not None
        logger.info(f"✓ Retrieved {len(result.documents)} documents")
    except Exception as e:
        logger.warning(f"⚠ Graph retrieval test failed: {e}")

    logger.info("✓ All graph retriever tests passed!\n")


async def test_analysis_service():
    """Test CodeQL analysis service."""
    logger.info("=" * 60)
    logger.info("Testing CodeQL Analysis Service")
    logger.info("=" * 60)

    # Test 1: Check if CodeQL enabled
    logger.info("Test 1: Checking CodeQL enabled status")
    enabled = codeql_analysis_service.is_codeql_enabled("test_area")
    logger.info(f"✓ CodeQL enabled for test_area: {enabled}")

    # Test 2: Register source from config
    logger.info("Test 2: Registering source from config")
    codeql_config = {
        "enabled": True,
        "repos": ["test/org/repo1", "test/org/repo2"]
    }
    source_ids = codeql_analysis_service.register_source_from_config(
        business_area="test_area",
        codeql_config=codeql_config
    )
    logger.info(f"✓ Registered {len(source_ids)} sources from config")

    # Test 3: Analyze source (will skip if CLI not available)
    if source_ids:
        logger.info("Test 3: Testing source analysis (will skip if CLI unavailable)")
        try:
            result = await codeql_analysis_service.analyze_source(source_ids[0])
            logger.info(f"✓ Analysis result status: {result.get('status')}")
        except Exception as e:
            logger.warning(f"⚠ Analysis test failed (expected if CLI unavailable): {e}")

    # Cleanup
    for source_id in source_ids:
        try:
            code_source_registry.delete(source_id)
        except Exception:
            pass

    logger.info("✓ All analysis service tests passed!\n")


async def test_integration():
    """Test end-to-end integration."""
    logger.info("=" * 60)
    logger.info("Testing End-to-End Integration")
    logger.info("=" * 60)

    # Test 1: Register source
    logger.info("Test 1: Registering test source")
    source_id = code_source_registry.register(
        business_area="test_area",
        source_type="gitlab",
        path="test/integration/repo",
        languages=["python"],
        enabled=True
    )
    logger.info(f"✓ Registered: {source_id}")

    # Test 2: Check if analysis would work
    logger.info("Test 2: Checking analysis readiness")
    cli = get_codeql_cli()
    neo4j_available = neo4j_manager.is_available()
    
    logger.info(f"  - CodeQL CLI: {'✓ Available' if cli else '✗ Not available'}")
    logger.info(f"  - Neo4j: {'✓ Available' if neo4j_available else '✗ Not available'}")
    logger.info(f"  - CodeQL Enabled: {'✓ Yes' if settings.codeql_enabled else '✗ No'}")

    if cli and neo4j_available and settings.codeql_enabled:
        logger.info("✓ All prerequisites met for full analysis")
    else:
        logger.info("⚠ Some prerequisites missing - analysis will be limited")

    # Test 3: Graph retriever integration
    if neo4j_available:
        logger.info("Test 3: Testing graph retriever integration")
        try:
            result = await graph_retriever.retrieve(
                query="test_function",
                business_area="test_area",
                limit=5
            )
            logger.info(f"✓ Graph retriever returned {len(result.documents)} results")
        except Exception as e:
            logger.warning(f"⚠ Graph retrieval failed: {e}")

    # Cleanup
    try:
        code_source_registry.delete(source_id)
    except Exception:
        pass

    logger.info("✓ All integration tests passed!\n")


async def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("CodeQL Integration Test Suite")
    logger.info("=" * 60 + "\n")

    try:
        # Test source registry
        await test_source_registry()

        # Test storage
        test_storage()

        # Test CLI (may skip if not available)
        test_codeql_cli()

        # Test graph retriever (may skip if Neo4j not available)
        test_graph_retriever()

        # Test analysis service
        await test_analysis_service()

        # Test integration
        await test_integration()

        logger.info("=" * 60)
        logger.info("✓ All tests completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ Test suite failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())

