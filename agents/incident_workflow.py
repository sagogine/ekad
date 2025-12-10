"""Incident workflow orchestrating context collection and briefing generation."""
from __future__ import annotations

from typing import Dict, Any
from core.logging import get_logger
from .state import IncidentAgentState
from .incident_context import incident_context_agent
from .briefing import briefing_agent

logger = get_logger(__name__)


class IncidentWorkflow:
    """Linear workflow: incident context → briefing."""

    async def run(
        self,
        query: str,
        business_area: str,
        incident_payload: Dict[str, Any] | None = None,
        retrieval_plan: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Execute the incident workflow."""
        state: IncidentAgentState = {
            "query": query,
            "business_area": business_area,
            "incident_payload": incident_payload or {},
            "retrieval_plan": retrieval_plan or {},
            "retriever_results": {},
            "incident_context": {},
            "briefing_markdown": None,
            "briefing_summary": None,
            "attachments": [],
            "errors": [],
        }

        try:
            state = await incident_context_agent.build_context(state)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Incident context agent failed",
                error=str(exc)
            )
            state["errors"].append(str(exc))
            return state

        try:
            state = await briefing_agent.generate_briefing(state)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Briefing agent failed",
                error=str(exc)
            )
            state["errors"].append(str(exc))

        return state


incident_workflow = IncidentWorkflow()

