"""Tests for incident workflow and agents."""
import asyncio
from typing import Any, Dict
import pytest
from core.config import settings
from core.logging import configure_logging, get_logger
from agents.incident_workflow import incident_workflow


configure_logging()
logger = get_logger(__name__)


async def run_incident_flow(
    query: str,
    incident_payload: Dict[str, Any],
    retrieval_plan: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    business_area = settings.business_areas_list[0] if settings.business_areas_list else "default"
    return await incident_workflow.run(
        query=query,
        business_area=business_area,
        incident_payload=incident_payload,
        retrieval_plan=retrieval_plan
    )


@pytest.mark.asyncio
async def test_incident_flow_no_data():
    """Incident flow should complete with fallback briefing when no data is available."""
    logger.info("Testing incident workflow without configured sources")
    result = await run_incident_flow(
        query="Test pipeline failure",
        incident_payload={"error": "Unit test"}
    )

    assert result["briefing_markdown"] is not None
    assert "No relevant documentation" in result["briefing_markdown"]
    assert result["briefing_summary"] is not None
    logger.info("✓ Incident workflow fallback works as expected")


@pytest.mark.asyncio
async def test_incident_flow_with_plan():
    """Incident flow should accept retrieval plan overrides."""
    logger.info("Testing incident workflow with retrieval plan override")
    result = await run_incident_flow(
        query="Test incident with retrieval plan",
        incident_payload={"error": "Simulated incident"},
        retrieval_plan={"sources": ["confluence"], "limit": 2}
    )

    assert "incident_context" in result
    assert "errors" in result
    logger.info("✓ Incident workflow with plan executed")


if __name__ == "__main__":
    asyncio.run(test_incident_flow_no_data())
    asyncio.run(test_incident_flow_with_plan())

