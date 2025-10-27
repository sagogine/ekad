"""Agent state definitions for LangGraph workflow."""
from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict):
    """State shared across all agents in the workflow."""
    
    # Input
    query: str
    business_area: str
    
    # Researcher outputs
    research_findings: Optional[Dict[str, Any]]
    retrieved_documents: Optional[List[Dict[str, Any]]]
    
    # Writer outputs
    draft_response: Optional[str]
    
    # Reviewer outputs
    review_feedback: Optional[str]
    review_approved: bool
    
    # Final output
    final_response: Optional[str]
    sources: Optional[List[Dict[str, Any]]]
    
    # Metadata
    iteration_count: int
    max_iterations: int
    error: Optional[str]
