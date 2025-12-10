"""Base interfaces and models for retrieval plugins."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class RetrievedDocument:
    """Normalized representation of a retrieved document."""

    title: str
    content: str
    source: str
    document_type: str
    score: float
    url: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Aggregate retrieval outcome."""

    documents: List[RetrievedDocument]
    retriever_name: str
    source: str
    message: str = "success"
    error: str | None = None


class Retriever(Protocol):
    """Protocol for retriever implementations."""

    name: str

    async def retrieve(
        self,
        query: str,
        business_area: str,
        *,
        limit: int = 5,
        filters: Dict[str, Any] | None = None
    ) -> RetrievalResult:
        """Execute retrieval."""

