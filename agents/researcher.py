"""Researcher agent for retrieving and analyzing information."""
from typing import Dict, Any
from agents.state import AgentState
from vectorstore.retriever import bounded_retriever
from core.llm import llm_service
from core.logging import get_logger

logger = get_logger(__name__)


class ResearcherAgent:
    """Agent responsible for retrieving and analyzing information."""
    
    def __init__(self):
        """Initialize researcher agent."""
        self.system_prompt = """You are a Research Agent for an enterprise knowledge system.

Your role is to analyze user queries and determine what information is needed to answer them.

Given a query, you should:
1. Identify what types of information are needed (requirements, configuration, code, issues)
2. Determine which sources should be consulted (Confluence, Firestore, GitLab)
3. Analyze the retrieved documents and summarize key findings

You must ONLY use information from the provided context. If information is not available, clearly state that.

Format your analysis as:
- **Query Analysis**: What is being asked?
- **Information Needed**: What types of documents are relevant?
- **Key Findings**: Summarize the most relevant information from retrieved documents
- **Coverage**: Which sources provided information? Which are missing?
"""
        logger.info("Researcher agent initialized")
    
    async def research(self, state: AgentState) -> Dict[str, Any]:
        """
        Perform research based on the query.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with research findings
        """
        try:
            query = state["query"]
            business_area = state["business_area"]
            
            logger.info(
                "Researcher starting",
                query=query[:50],
                business_area=business_area
            )
            
            # Retrieve documents from all sources
            retrieval_result = await bounded_retriever.retrieve_multi_source(
                query=query,
                business_area=business_area,
                sources=["confluence", "firestore", "gitlab"],
                top_k_per_source=3
            )
            
            results = retrieval_result.get("results", [])
            results_by_source = retrieval_result.get("results_by_source", {})
            missing_sources = retrieval_result.get("missing_sources", [])
            
            # Check if any results found
            if not results:
                logger.warning(
                    "No documents found",
                    business_area=business_area
                )
                return {
                    **state,
                    "research_findings": {
                        "status": "no_results",
                        "message": f"No information found in {business_area} context",
                        "sources_checked": ["confluence", "firestore", "gitlab"]
                    },
                    "retrieved_documents": [],
                    "error": None
                }
            
            # Build context from retrieved documents
            context = self._build_context(results, results_by_source)
            
            # Analyze with LLM
            analysis_prompt = f"""Query: {query}

Business Area: {business_area}

Retrieved Documents:
{context}

Please analyze this query and the retrieved documents. Provide:
1. Query Analysis: What is being asked?
2. Information Needed: What types of information are relevant?
3. Key Findings: Summarize the most relevant information
4. Coverage: Which sources provided information?
"""
            
            try:
                analysis = await llm_service.generate(
                    prompt=analysis_prompt,
                    system_prompt=self.system_prompt
                )
            except Exception as e:
                logger.error("LLM analysis failed", error=str(e))
                # Fallback: simple summary
                analysis = f"Retrieved {len(results)} documents from {len(results_by_source)} sources."
            
            research_findings = {
                "status": "success",
                "analysis": analysis,
                "document_count": len(results),
                "sources_with_results": list(results_by_source.keys()),
                "missing_sources": missing_sources,
                "results_by_source": {
                    source: len(docs)
                    for source, docs in results_by_source.items()
                }
            }
            
            logger.info(
                "Research completed",
                document_count=len(results),
                sources=len(results_by_source)
            )
            
            return {
                **state,
                "research_findings": research_findings,
                "retrieved_documents": results,
                "error": None
            }
        
        except Exception as e:
            logger.error("Research failed", error=str(e))
            return {
                **state,
                "research_findings": {
                    "status": "error",
                    "message": str(e)
                },
                "retrieved_documents": [],
                "error": str(e)
            }
    
    def _build_context(
        self,
        results: list,
        results_by_source: Dict[str, list]
    ) -> str:
        """
        Build context string from retrieved documents.
        
        Args:
            results: All retrieved documents
            results_by_source: Documents grouped by source
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        for source, docs in results_by_source.items():
            if not docs:
                continue
            
            context_parts.append(f"\n## From {source.upper()}:\n")
            for i, doc in enumerate(docs[:3], 1):  # Limit to top 3 per source
                title = doc.get("title", "Untitled")
                content = doc.get("content", "")[:500]  # Limit content length
                url = doc.get("url", "")
                
                context_parts.append(
                    f"{i}. **{title}**\n"
                    f"   URL: {url}\n"
                    f"   Content: {content}...\n"
                )
        
        return "\n".join(context_parts)


# Global researcher agent instance
researcher_agent = ResearcherAgent()
