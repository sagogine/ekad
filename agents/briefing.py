"""Incident briefing agent responsible for synthesizing incident summaries."""
from __future__ import annotations

from textwrap import dedent
from typing import Any, Dict, List
from core.llm import llm_service
from core.logging import get_logger
from .state import IncidentAgentState

logger = get_logger(__name__)


BRIEFING_SYSTEM_PROMPT = dedent(
    """
    You are an incident response assistant. Produce a concise incident briefing
    using only the provided context. The briefing should include:
    - Incident summary (what happened, when, where)
    - Impacted systems and teams
    - Relevant code/config references
    - Known lineage or dependencies
    - Next recommended actions
    If information is missing, clearly note the gaps.
    """
)


class BriefingAgent:
    """Agent responsible for generating an incident briefing."""

    name = "incident_briefing"

    async def generate_briefing(self, state: IncidentAgentState) -> IncidentAgentState:
        """Generate a markdown briefing from incident context."""
        incident_context = state.get("incident_context", {})
        retriever_results = state.get("retriever_results", {})

        if not incident_context.get("documents"):
            logger.warning("No incident documents available; using fallback briefing.")
            briefing = self._fallback_briefing(state)
            return {**state, **briefing}

        prompt = self._build_prompt(state, incident_context)

        try:
            response = await llm_service.generate(
                prompt=prompt,
                system_prompt=BRIEFING_SYSTEM_PROMPT
            )
            markdown = response.strip()

        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Briefing generation failed; falling back",
                error=str(exc)
            )
            return {
                **state,
                **self._fallback_briefing(state),
                "errors": state.get("errors", []) + [str(exc)]
            }

        summary = self._extract_summary(markdown)

        return {
            **state,
            "briefing_markdown": markdown,
            "briefing_summary": summary,
            "attachments": self._build_attachments(retriever_results),
        }

    def _build_prompt(
        self,
        state: IncidentAgentState,
        incident_context: Dict[str, Any]
    ) -> str:
        """Construct LLM prompt from incident context."""
        payload = state.get("incident_payload", {})
        lines: List[str] = [
            f"Incident Query: {state.get('query', 'N/A')}",
            f"Business Area: {state.get('business_area', 'N/A')}",
            "Incident Payload:",
            repr(payload),
            "\nRetrieved Documents:"
        ]

        for idx, doc in enumerate(incident_context.get("documents", [])[:20], start=1):
            lines.append(
                dedent(
                    f"""
                    [{idx}] Source: {doc.get('source')}
                        Retriever: {doc.get('retriever')}
                        Title: {doc.get('title')}
                        URL: {doc.get('url') or 'N/A'}
                        Document Type: {doc.get('document_type')}
                        Metadata: {doc.get('metadata')}
                    """
                )
            )

        return "\n".join(lines)

    @staticmethod
    def _fallback_briefing(state: IncidentAgentState) -> Dict[str, Any]:
        """Fallback briefing when no context is available."""
        summary = "Insufficient data to generate a briefing."
        markdown = dedent(
            f"""
            # Incident Briefing

            No relevant documentation or metadata was found for the incident query:
            `{state.get('query', 'N/A')}` in business area `{state.get('business_area', 'N/A')}`.

            ## Next Steps
            1. Verify that ingestion has run for this business area.
            2. Confirm connectors are configured for documentation/code/metadata sources.
            3. Re-run the incident pipeline with additional context if available.
            """
        ).strip()

        return {
            "briefing_markdown": markdown,
            "briefing_summary": summary,
            "attachments": []
        }

    @staticmethod
    def _extract_summary(markdown: str) -> str:
        """Extract a short summary from the briefing markdown."""
        first_line = markdown.strip().splitlines()[0] if markdown else ""
        if first_line.startswith("#"):
            return first_line.lstrip("# ").strip()
        return first_line[:200]

    @staticmethod
    def _build_attachments(
        retriever_results: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Create attachment metadata from retrieval results."""
        attachments: List[Dict[str, Any]] = []

        for source, results in retriever_results.items():
            for result in results:
                if result["documents"]:
                    attachments.append({
                        "source": source,
                        "retriever": result["retriever_name"],
                        "document_count": len(result["documents"]),
                        "message": result["message"]
                    })

        return attachments


briefing_agent = BriefingAgent()

