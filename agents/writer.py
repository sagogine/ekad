"""Writer agent for synthesizing responses."""
from typing import Dict, Any
from agents.state import AgentState
from core.llm import llm_service
from core.logging import get_logger

logger = get_logger(__name__)


class WriterAgent:
    """Agent responsible for synthesizing coherent responses."""
    
    def __init__(self):
        """Initialize writer agent."""
        self.system_prompt = """You are a Writer Agent for an enterprise knowledge system.

Your role is to synthesize information from multiple sources into a coherent, well-structured response.

Guidelines:
1. Create a clear, organized response with appropriate sections
2. Cite sources for all claims using the format: [Source: {source_type} - {title}]({url})
3. If information spans multiple sources (requirements, config, code), organize by category
4. Use markdown formatting for readability
5. Be concise but comprehensive
6. ONLY use information from the provided documents - do not add external knowledge
7. If information is incomplete, clearly state what is missing

Format your response with:
- Clear section headers
- Bullet points or numbered lists where appropriate
- Inline citations
- A "Sources" section at the end
"""
        logger.info("Writer agent initialized")
    
    async def write(self, state: AgentState) -> Dict[str, Any]:
        """
        Write a response based on research findings.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with draft response
        """
        try:
            query = state["query"]
            business_area = state["business_area"]
            research_findings = state.get("research_findings", {})
            retrieved_documents = state.get("retrieved_documents", [])
            
            logger.info(
                "Writer starting",
                query=query[:50],
                document_count=len(retrieved_documents)
            )
            
            # Check if research was successful
            if research_findings.get("status") == "no_results":
                draft = f"""# No Information Found

I could not find any information about "{query}" in the **{business_area}** knowledge base.

The following sources were checked:
- Confluence (requirements and documentation)
- Firestore (configuration data)
- GitLab (code and issues)

**Suggestion**: Please verify:
1. The query is relevant to the {business_area} business area
2. The information exists in one of the connected sources
3. The data has been ingested into the system
"""
                logger.info("Generated 'no results' response")
                return {
                    **state,
                    "draft_response": draft,
                    "error": None
                }
            
            if research_findings.get("status") == "error":
                error_msg = research_findings.get("message", "Unknown error")
                draft = f"""# Error

An error occurred while researching your query: {error_msg}

Please try again or contact support if the issue persists.
"""
                logger.error("Research error, generated error response")
                return {
                    **state,
                    "draft_response": draft,
                    "error": error_msg
                }
            
            # Build context for writer
            context = self._build_detailed_context(retrieved_documents)
            research_analysis = research_findings.get("analysis", "")
            
            # Generate response
            writing_prompt = f"""Query: {query}

Business Area: {business_area}

Research Analysis:
{research_analysis}

Retrieved Documents:
{context}

Please write a comprehensive response to the query. Include:
1. Direct answer to the question
2. Supporting details from the documents
3. Citations for all information
4. Clear organization with sections if needed

Remember to cite sources using: [Source: {{source}} - {{title}}]({{url}})
"""
            
            try:
                draft_response = await llm_service.generate(
                    prompt=writing_prompt,
                    system_prompt=self.system_prompt
                )
            except Exception as e:
                logger.error("LLM generation failed", error=str(e))
                # Fallback: simple response
                draft_response = self._create_fallback_response(
                    query,
                    retrieved_documents,
                    research_findings
                )
            
            logger.info("Draft response generated")
            
            return {
                **state,
                "draft_response": draft_response,
                "error": None
            }
        
        except Exception as e:
            logger.error("Writing failed", error=str(e))
            return {
                **state,
                "draft_response": f"Error generating response: {str(e)}",
                "error": str(e)
            }
    
    def _build_detailed_context(self, documents: list) -> str:
        """
        Build detailed context from documents.
        
        Args:
            documents: Retrieved documents
            
        Returns:
            Formatted context string
        """
        if not documents:
            return "No documents available."
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")
            source = doc.get("source", "unknown")
            doc_type = doc.get("document_type", "unknown")
            url = doc.get("url", "")
            
            context_parts.append(
                f"\n### Document {i}: {title}\n"
                f"- **Source**: {source}\n"
                f"- **Type**: {doc_type}\n"
                f"- **URL**: {url}\n"
                f"- **Content**:\n{content}\n"
            )
        
        return "\n".join(context_parts)
    
    def _create_fallback_response(
        self,
        query: str,
        documents: list,
        research_findings: dict
    ) -> str:
        """
        Create a simple fallback response if LLM fails.
        
        Args:
            query: User query
            documents: Retrieved documents
            research_findings: Research findings
            
        Returns:
            Fallback response string
        """
        response_parts = [
            f"# Response to: {query}\n",
            f"Found {len(documents)} relevant documents:\n"
        ]
        
        for i, doc in enumerate(documents[:5], 1):
            title = doc.get("title", "Untitled")
            source = doc.get("source", "unknown")
            url = doc.get("url", "")
            content = doc.get("content", "")[:200]
            
            response_parts.append(
                f"\n## {i}. {title}\n"
                f"**Source**: {source}\n"
                f"{content}...\n"
                f"[View full document]({url})\n"
            )
        
        return "\n".join(response_parts)


# Global writer agent instance
writer_agent = WriterAgent()
