"""Pydantic models for API requests and responses."""
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from core.config import settings
from ingestion.base import SourceType


class IngestionRequest(BaseModel):
    """Request model for ingestion endpoint."""
    business_area: str = Field(..., description="Business area identifier")
    sources: Optional[List[str]] = Field(
        default=None,
        description="Sources to ingest from (default: all)",
        examples=[["confluence", "firestore", "gitlab"]]
    )
    mode: Literal["full", "incremental"] = Field(
        default="incremental",
        description="Sync mode"
    )

    @field_validator("business_area")
    @classmethod
    def validate_ingestion_business_area(cls, value: str) -> str:
        if value not in settings.business_areas_list:
            raise ValueError(
                f"Invalid business area '{value}'. Valid options: {settings.business_areas_list}"
            )
        return value

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if not value:
            return value

        valid_sources = {source.value for source in SourceType}
        invalid = [item for item in value if item not in valid_sources]
        if invalid:
            raise ValueError(
                f"Invalid sources {invalid}. Valid options: {sorted(valid_sources)}"
            )
        return value


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


class IncidentRetrievalPlan(BaseModel):
    """Optional overrides for incident retrieval."""
    sources: Optional[List[str]] = Field(
        default=None,
        description="Sources to target (default: all configured sources)"
    )
    limit: int = Field(
        default=5,
        description="Max documents per retriever",
        ge=1,
        le=50
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional filters passed to retrievers"
    )


class IncidentRequest(BaseModel):
    """Request model for incident endpoint."""
    business_area: str = Field(..., description="Business area identifier")
    query: str = Field(..., description="Incident description or key error message")
    incident_payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw incident metadata/log payload"
    )
    retrieval_plan: Optional[IncidentRetrievalPlan] = Field(
        default=None,
        description="Optional overrides for retriever dispatcher"
    )

    @field_validator("business_area")
    @classmethod
    def validate_incident_business_area(cls, value: str) -> str:
        if value not in settings.business_areas_list:
            raise ValueError(
                f"Invalid business area '{value}'. Valid options: {settings.business_areas_list}"
            )
        return value


class IncidentAttachment(BaseModel):
    """Attachment metadata for incident response."""
    source: str
    retriever: str
    document_count: int
    message: str


class IncidentResponse(BaseModel):
    """Response model for incident endpoint."""
    briefing_summary: Optional[str] = Field(
        default=None,
        description="Short summary for ticket title or overview"
    )
    briefing_markdown: Optional[str] = Field(
        default=None,
        description="Full incident briefing in markdown"
    )
    incident_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw retrieval context (sources, documents, metadata)"
    )
    attachments: List[IncidentAttachment] = Field(
        default_factory=list,
        description="Attachment metadata (documents available per retriever)"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during workflow execution"
    )


# ============================================
# Code Source Management Models
# ============================================
class CodeSourceRegisterRequest(BaseModel):
    """Request model for registering a code source."""
    business_area: str = Field(..., description="Business area identifier")
    source_type: Literal["gitlab", "filesystem"] = Field(..., description="Source type")
    path: str = Field(..., description="GitLab project path (e.g., 'org/repo') or filesystem path")
    languages: List[str] = Field(
        default=["python", "java"],
        description="Languages to analyze (e.g., ['python', 'java', 'sql', 'shell'])"
    )
    name: Optional[str] = Field(
        default=None,
        description="Optional friendly name for the source"
    )
    enabled: bool = Field(default=True, description="Whether source is enabled for analysis")

    @field_validator("business_area")
    @classmethod
    def validate_business_area(cls, value: str) -> str:
        if value not in settings.business_areas_list:
            raise ValueError(
                f"Invalid business area '{value}'. Valid options: {settings.business_areas_list}"
            )
        return value


class CodeSourceResponse(BaseModel):
    """Response model for code source."""
    source_id: str
    business_area: str
    source_type: str
    path: str
    languages: List[str]
    name: Optional[str] = None
    enabled: bool
    last_analyzed_commit: Optional[str] = None
    last_analyzed_time: Optional[str] = None


class CodeSourceListResponse(BaseModel):
    """Response model for listing code sources."""
    sources: List[CodeSourceResponse]
    total: int


class CodeAnalysisRequest(BaseModel):
    """Request model for triggering code analysis."""
    business_area: Optional[str] = Field(
        default=None,
        description="Business area to analyze (analyzes all sources if not specified)"
    )
    source_id: Optional[str] = Field(
        default=None,
        description="Specific source ID to analyze (overrides business_area)"
    )


class CodeAnalysisResponse(BaseModel):
    """Response model for code analysis."""
    job_id: str
    status: str
    message: str
    business_area: Optional[str] = None
    source_id: Optional[str] = None
