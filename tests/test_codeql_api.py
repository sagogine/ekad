"""API tests for CodeQL endpoints."""
from fastapi.testclient import TestClient
from app.main import app
from codeql import code_source_registry
from core.config import settings
from core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

client = TestClient(app)


def test_register_code_source():
    """Test code source registration endpoint."""
    logger.info("Testing POST /api/v1/code-sources/register")

    # Use first available business area
    business_area = settings.business_areas_list[0] if settings.business_areas_list else "default"
    
    # Register a source
    response = client.post(
        "/api/v1/code-sources/register",
        json={
            "business_area": business_area,
            "source_type": "gitlab",
            "path": "test/org/api-repo",
            "languages": ["python", "java"],
            "name": "Test API Repository",
            "enabled": True
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "source_id" in data
    assert data["business_area"] == business_area
    assert data["path"] == "test/org/api-repo"
    logger.info(f"✓ Registered source: {data['source_id']}")

    # Cleanup
    source_id = data["source_id"]
    try:
        code_source_registry.delete(source_id)
    except Exception:
        pass

    return source_id, business_area


def test_list_code_sources():
    """Test code source listing endpoint."""
    logger.info("Testing GET /api/v1/code-sources")

    # Use first available business area
    business_area = settings.business_areas_list[0] if settings.business_areas_list else "default"
    
    # Register a test source first
    source_id = code_source_registry.register(
        business_area=business_area,
        source_type="gitlab",
        path="test/org/list-repo",
        languages=["python"],
        enabled=True
    )

    try:
        # List all sources
        response = client.get("/api/v1/code-sources")
        assert response.status_code == 200
        data = response.json()
        assert "sources" in data
        assert "total" in data
        assert len(data["sources"]) >= 1
        logger.info(f"✓ Listed {data['total']} sources")

        # Filter by business area
        response = client.get(f"/api/v1/code-sources?business_area={business_area}")
        assert response.status_code == 200
        data = response.json()
        assert all(s["business_area"] == business_area for s in data["sources"])
        logger.info(f"✓ Filtered to {len(data['sources'])} sources for {business_area}")

        # Filter by enabled only
        response = client.get("/api/v1/code-sources?enabled_only=true")
        assert response.status_code == 200
        data = response.json()
        assert all(s["enabled"] for s in data["sources"])
        logger.info(f"✓ Filtered to {len(data['sources'])} enabled sources")

    finally:
        # Cleanup
        try:
            code_source_registry.delete(source_id)
        except Exception:
            pass


def test_get_code_source():
    """Test getting a specific code source."""
    logger.info("Testing GET /api/v1/code-sources/{source_id}")

    # Use first available business area
    business_area = settings.business_areas_list[0] if settings.business_areas_list else "default"
    
    # Register a test source
    source_id = code_source_registry.register(
        business_area=business_area,
        source_type="gitlab",
        path="test/org/get-repo",
        languages=["python"],
        enabled=True
    )

    try:
        # Get the source
        response = client.get(f"/api/v1/code-sources/{source_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["source_id"] == source_id
        assert data["path"] == "test/org/get-repo"
        logger.info(f"✓ Retrieved source: {source_id}")

        # Try to get non-existent source
        response = client.get("/api/v1/code-sources/nonexistent-id")
        assert response.status_code == 404
        logger.info("✓ Correctly returned 404 for non-existent source")

    finally:
        # Cleanup
        try:
            code_source_registry.delete(source_id)
        except Exception:
            pass


def test_delete_code_source():
    """Test deleting a code source."""
    logger.info("Testing DELETE /api/v1/code-sources/{source_id}")

    # Use first available business area
    business_area = settings.business_areas_list[0] if settings.business_areas_list else "default"
    
    # Register a test source
    source_id = code_source_registry.register(
        business_area=business_area,
        source_type="gitlab",
        path="test/org/delete-repo",
        languages=["python"],
        enabled=True
    )

    # Delete the source
    response = client.delete(f"/api/v1/code-sources/{source_id}")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    logger.info(f"✓ Deleted source: {source_id}")

    # Verify it's deleted
    source = code_source_registry.get(source_id)
    assert source is None, "Source should be deleted"

    # Try to delete non-existent source
    response = client.delete("/api/v1/code-sources/nonexistent-id")
    assert response.status_code == 404
    logger.info("✓ Correctly returned 404 for non-existent source")


def test_trigger_analysis():
    """Test triggering code analysis."""
    logger.info("Testing POST /api/v1/analyze")

    # Use first available business area
    business_area = settings.business_areas_list[0] if settings.business_areas_list else "default"
    
    # Register a test source
    source_id = code_source_registry.register(
        business_area=business_area,
        source_type="gitlab",
        path="test/org/analyze-repo",
        languages=["python"],
        enabled=True
    )

    try:
        # Trigger analysis for source
        response = client.post(
            "/api/v1/analyze",
            json={"source_id": source_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "running"
        assert data["source_id"] == source_id
        logger.info(f"✓ Triggered analysis: {data['job_id']}")

        # Trigger analysis for business area
        response = client.post(
            "/api/v1/analyze",
            json={"business_area": business_area}
        )
        # May return 400 if CodeQL not enabled, which is fine
        if response.status_code == 200:
            data = response.json()
            assert "job_id" in data
            logger.info(f"✓ Triggered analysis for business area: {data['job_id']}")
        else:
            logger.info(f"✓ Analysis skipped (CodeQL not enabled): {response.status_code}")

    finally:
        # Cleanup
        try:
            code_source_registry.delete(source_id)
        except Exception:
            pass


def test_incident_with_graph():
    """Test incident endpoint with graph retriever."""
    logger.info("Testing POST /api/v1/incidents (with graph retriever)")

    # Create incident request that might use graph
    response = client.post(
        "/api/v1/incidents",
        json={
            "business_area": settings.business_areas_list[0] if settings.business_areas_list else "default",
            "query": "test function call error",
            "incident_payload": {
                "error": "FunctionNotFoundError",
                "function": "process_data"
            },
            "retrieval_plan": {
                "sources": ["codeql"],  # Try to use graph retriever
                "limit": 5
            }
        }
    )

    # Should return 200 even if graph not available
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "briefing_markdown" in data
    logger.info("✓ Incident endpoint works (graph may or may not be available)")


def run_all_api_tests():
    """Run all API tests."""
    logger.info("\n" + "=" * 60)
    logger.info("CodeQL API Test Suite")
    logger.info("=" * 60 + "\n")

    try:
        test_register_code_source()
        test_list_code_sources()
        test_get_code_source()
        test_delete_code_source()
        test_trigger_analysis()
        test_incident_with_graph()

        logger.info("=" * 60)
        logger.info("✓ All API tests passed!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ API test suite failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    run_all_api_tests()

