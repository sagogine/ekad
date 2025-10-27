"""Pydantic models for API requests and responses."""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str = Field(..., description="User query", min_length=1, max_length=1000)
    business_area: Literal["pharmacy", "supply_chain"] = Field(..., description="Business area")
    max_iterations: int = Field(default=2, description="Maximum revision iterations", ge=1, le=5)


class Source(BaseModel):
    """Source document model."""
    title: str
    source: str
    document_type: str
    url: str
    score: float


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    response: str
    sources: List[Source]
    metadata: Dict[str, Any]


class IngestionRequest(BaseModel):
    """Request model for ingestion endpoint."""
    business_area: Literal["pharmacy", "supply_chain"] = Field(..., description="Business area")
    sources: Optional[List[Literal["confluence", "firestore", "gitlab"]]] = Field(
        default=None,
        description="Sources to ingest from (default: all)"
    )
    mode: Literal["full", "incremental"] = Field(
        default="incremental",
        description="Sync mode"
    )


class IngestionResponse(BaseModel):
    """Response model for ingestion endpoint."""
    job_id: str
    status: str
    message: str


class IngestionStatus(BaseModel):
    """Status model for ingestion job."""
    job_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    services: Dict[str, Any]


class BusinessAreasResponse(BaseModel):
    """Response model for business areas endpoint."""
    business_areas: List[str]
