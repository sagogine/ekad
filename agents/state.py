"""Agent state definitions for incident workflow."""
from typing import TypedDict, List, Dict, Any, Optional


class IncidentAgentState(TypedDict, total=False):
    """State structure for incident-focused workflow."""

    # Inputs
    query: str
    business_area: str
    incident_payload: Dict[str, Any]

    # Retrieval phase
    retrieval_plan: Dict[str, Any]
    retriever_results: Dict[str, List[Dict[str, Any]]]
    incident_context: Dict[str, Any]

    # Briefing phase
    briefing_markdown: Optional[str]
    briefing_summary: Optional[str]
    attachments: List[Dict[str, Any]]

    # Metadata
    errors: List[str]
