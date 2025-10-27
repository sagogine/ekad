"""Reviewer agent for validating responses."""
from typing import Dict, Any
from agents.state import AgentState
from core.llm import llm_service
from core.logging import get_logger

logger = get_logger(__name__)


class ReviewerAgent:
    """Agent responsible for reviewing and validating responses."""
    
    def __init__(self):
        """Initialize reviewer agent."""
        self.system_prompt = """You are a Reviewer Agent for an enterprise knowledge system.

Your role is to validate responses for accuracy, completeness, and proper citation.

Review criteria:
1. **Accuracy**: Are all claims supported by the source documents?
2. **Completeness**: Does the response fully answer the query?
3. **Citations**: Are all claims properly cited?
4. **Hallucination Check**: Is any information added that's not in the sources?
5. **Clarity**: Is the response clear and well-organized?

Provide your review as:
- **Approved**: Yes/No
- **Issues Found**: List any problems (or "None" if approved)
- **Suggestions**: How to improve the response (if not approved)

Be strict but fair. Approve only if the response meets all criteria.
"""
        logger.info("Reviewer agent initialized")
    
    async def review(self, state: AgentState) -> Dict[str, Any]:
        """
        Review the draft response.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with review results
        """
        try:
            query = state["query"]
            draft_response = state.get("draft_response", "")
            retrieved_documents = state.get("retrieved_documents", [])
            iteration_count = state.get("iteration_count", 0)
            max_iterations = state.get("max_iterations", 2)
            
            logger.info(
                "Reviewer starting",
                iteration=iteration_count,
                max_iterations=max_iterations
            )
            
            # If no draft, cannot review
            if not draft_response:
                logger.error("No draft response to review")
                return {
                    **state,
                    "review_approved": False,
                    "review_feedback": "No draft response available",
                    "error": "No draft response"
                }
            
            # If max iterations reached, approve to avoid infinite loop
            if iteration_count >= max_iterations:
                logger.warning("Max iterations reached, auto-approving")
                return {
                    **state,
                    "review_approved": True,
                    "review_feedback": "Approved (max iterations reached)",
                    "final_response": draft_response,
                    "error": None
                }
            
            # Build context for review
            context = self._build_context(retrieved_documents)
            
            # Review with LLM
            review_prompt = f"""Query: {query}

Draft Response:
{draft_response}

Source Documents:
{context}

Please review this response against the source documents. Check for:
1. Accuracy - are all claims supported?
2. Completeness - is the query fully answered?
3. Citations - are sources properly cited?
4. Hallucinations - any information not in sources?

Provide your review in this format:
Approved: [Yes/No]
Issues: [List issues or "None"]
Suggestions: [How to improve, or "None"]
"""
            
            try:
                review_result = await llm_service.generate(
                    prompt=review_prompt,
                    system_prompt=self.system_prompt
                )
                
                # Parse review result
                approved = self._parse_approval(review_result)
                
            except Exception as e:
                logger.error("LLM review failed", error=str(e))
                # Fallback: simple checks
                approved = self._simple_validation(draft_response, retrieved_documents)
                review_result = f"Simple validation: {'Approved' if approved else 'Issues found'}"
            
            logger.info(
                "Review completed",
                approved=approved,
                iteration=iteration_count
            )
            
            if approved:
                return {
                    **state,
                    "review_approved": True,
                    "review_feedback": review_result,
                    "final_response": draft_response,
                    "iteration_count": iteration_count + 1,
                    "error": None
                }
            else:
                return {
                    **state,
                    "review_approved": False,
                    "review_feedback": review_result,
                    "iteration_count": iteration_count + 1,
                    "error": None
                }
        
        except Exception as e:
            logger.error("Review failed", error=str(e))
            # On error, approve to avoid blocking
            return {
                **state,
                "review_approved": True,
                "review_feedback": f"Review error: {str(e)}. Auto-approved.",
                "final_response": state.get("draft_response", ""),
                "error": str(e)
            }
    
    def _build_context(self, documents: list) -> str:
        """
        Build context from documents for review.
        
        Args:
            documents: Retrieved documents
            
        Returns:
            Formatted context string
        """
        if not documents:
            return "No source documents."
        
        context_parts = []
        for i, doc in enumerate(documents[:5], 1):  # Limit to top 5
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")[:300]  # Limit length
            
            context_parts.append(
                f"{i}. {title}\n"
                f"   {content}...\n"
            )
        
        return "\n".join(context_parts)
    
    def _parse_approval(self, review_text: str) -> bool:
        """
        Parse approval status from review text.
        
        Args:
            review_text: Review text from LLM
            
        Returns:
            True if approved, False otherwise
        """
        review_lower = review_text.lower()
        
        # Look for approval indicators
        if "approved: yes" in review_lower:
            return True
        if "approved: no" in review_lower:
            return False
        
        # Fallback: look for positive indicators
        positive_indicators = ["approved", "looks good", "acceptable", "meets criteria"]
        negative_indicators = ["not approved", "issues found", "needs improvement", "hallucination"]
        
        positive_count = sum(1 for ind in positive_indicators if ind in review_lower)
        negative_count = sum(1 for ind in negative_indicators if ind in review_lower)
        
        return positive_count > negative_count
    
    def _simple_validation(self, response: str, documents: list) -> bool:
        """
        Simple validation if LLM fails.
        
        Args:
            response: Draft response
            documents: Source documents
            
        Returns:
            True if validation passes
        """
        # Basic checks
        if len(response) < 50:
            return False
        
        if not documents:
            # If no documents, response should indicate that
            return "no information" in response.lower() or "not found" in response.lower()
        
        # Check if response has some content
        return len(response) > 100


# Global reviewer agent instance
reviewer_agent = ReviewerAgent()
