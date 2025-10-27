"""LangGraph workflow orchestrating all agents."""
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.researcher import researcher_agent
from agents.writer import writer_agent
from agents.reviewer import reviewer_agent
from core.logging import get_logger

logger = get_logger(__name__)


class KnowledgeAgentWorkflow:
    """Workflow orchestrating Researcher, Writer, and Reviewer agents."""
    
    def __init__(self):
        """Initialize the workflow."""
        self.graph = self._build_graph()
        logger.info("Knowledge agent workflow initialized")
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow.
        
        Returns:
            Compiled StateGraph
        """
        # Create graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("researcher", self._researcher_node)
        workflow.add_node("writer", self._writer_node)
        workflow.add_node("reviewer", self._reviewer_node)
        
        # Set entry point
        workflow.set_entry_point("researcher")
        
        # Add edges
        workflow.add_edge("researcher", "writer")
        workflow.add_edge("writer", "reviewer")
        
        # Conditional edge from reviewer
        workflow.add_conditional_edges(
            "reviewer",
            self._should_revise,
            {
                "revise": "writer",  # Go back to writer for revision
                "end": END  # Approved, end workflow
            }
        )
        
        # Compile graph
        return workflow.compile()
    
    async def _researcher_node(self, state: AgentState) -> AgentState:
        """
        Researcher node.
        
        Args:
            state: Current state
            
        Returns:
            Updated state
        """
        logger.info("Executing researcher node")
        return await researcher_agent.research(state)
    
    async def _writer_node(self, state: AgentState) -> AgentState:
        """
        Writer node.
        
        Args:
            state: Current state
            
        Returns:
            Updated state
        """
        logger.info("Executing writer node")
        return await writer_agent.write(state)
    
    async def _reviewer_node(self, state: AgentState) -> AgentState:
        """
        Reviewer node.
        
        Args:
            state: Current state
            
        Returns:
            Updated state
        """
        logger.info("Executing reviewer node")
        return await reviewer_agent.review(state)
    
    def _should_revise(self, state: AgentState) -> str:
        """
        Determine if response should be revised.
        
        Args:
            state: Current state
            
        Returns:
            "revise" or "end"
        """
        approved = state.get("review_approved", False)
        iteration_count = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 2)
        
        if approved:
            logger.info("Review approved, ending workflow")
            return "end"
        
        if iteration_count >= max_iterations:
            logger.warning("Max iterations reached, ending workflow")
            return "end"
        
        logger.info(f"Review not approved, revising (iteration {iteration_count})")
        return "revise"
    
    async def run(
        self,
        query: str,
        business_area: str,
        max_iterations: int = 2
    ) -> Dict[str, Any]:
        """
        Run the workflow.
        
        Args:
            query: User query
            business_area: Business area
            max_iterations: Maximum revision iterations
            
        Returns:
            Final response and metadata
        """
        try:
            logger.info(
                "Starting workflow",
                query=query[:50],
                business_area=business_area
            )
            
            # Initialize state
            initial_state: AgentState = {
                "query": query,
                "business_area": business_area,
                "research_findings": None,
                "retrieved_documents": None,
                "draft_response": None,
                "review_feedback": None,
                "review_approved": False,
                "final_response": None,
                "sources": None,
                "iteration_count": 0,
                "max_iterations": max_iterations,
                "error": None
            }
            
            # Run workflow
            final_state = await self.graph.ainvoke(initial_state)
            
            # Extract results
            final_response = final_state.get("final_response", "")
            retrieved_documents = final_state.get("retrieved_documents", [])
            research_findings = final_state.get("research_findings", {})
            error = final_state.get("error")
            
            # Format sources
            sources = []
            if retrieved_documents:
                for doc in retrieved_documents:
                    sources.append({
                        "title": doc.get("title", ""),
                        "source": doc.get("source", ""),
                        "document_type": doc.get("document_type", ""),
                        "url": doc.get("url", ""),
                        "score": doc.get("score", 0.0)
                    })
            
            logger.info(
                "Workflow completed",
                iterations=final_state.get("iteration_count", 0),
                sources_count=len(sources)
            )
            
            return {
                "response": final_response or "No response generated",
                "sources": sources,
                "metadata": {
                    "business_area": business_area,
                    "iterations": final_state.get("iteration_count", 0),
                    "research_status": research_findings.get("status", "unknown"),
                    "document_count": len(retrieved_documents) if retrieved_documents else 0,
                    "sources_consulted": research_findings.get("sources_with_results", []),
                    "review_approved": final_state.get("review_approved", False),
                    "error": error
                }
            }
        
        except Exception as e:
            logger.error("Workflow failed", error=str(e))
            return {
                "response": f"An error occurred: {str(e)}",
                "sources": [],
                "metadata": {
                    "business_area": business_area,
                    "error": str(e)
                }
            }


# Global workflow instance
knowledge_workflow = KnowledgeAgentWorkflow()
