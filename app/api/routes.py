"""API routes for Traceback."""
import uuid
from typing import Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models import (
    IngestionRequest,
    IngestionResponse,
    IngestionStatus,
    IncidentRequest,
    IncidentResponse,
    CodeSourceRegisterRequest,
    CodeSourceResponse,
    CodeSourceListResponse,
    CodeAnalysisRequest,
    CodeAnalysisResponse,
)
from agents.incident_workflow import incident_workflow
from ingestion.service import ingestion_service, SyncMode
from ingestion.base import SourceType
from codeql import code_source_registry, codeql_analysis_service
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["api"])

# In-memory job storage (use Redis in production)
ingestion_jobs: Dict[str, Dict] = {}


@router.post("/ingest", response_model=IngestionResponse)
async def trigger_ingestion(
    request: IngestionRequest,
    background_tasks: BackgroundTasks
) -> IngestionResponse:
    """
    Trigger data ingestion from sources.
    
    Args:
        request: Ingestion request
        background_tasks: FastAPI background tasks
        
    Returns:
        Job ID and status
    """
    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        ingestion_jobs[job_id] = {
            "status": "running",
            "business_area": request.business_area,
            "sources": request.sources or ["all"],
            "mode": request.mode,
            "progress": {},
            "error": None
        }
        
        # Start ingestion in background
        background_tasks.add_task(
            run_ingestion,
            job_id=job_id,
            business_area=request.business_area,
            sources=request.sources,
            mode=request.mode
        )
        
        logger.info(
            "Ingestion triggered",
            job_id=job_id,
            business_area=request.business_area,
            mode=request.mode
        )
        
        return IngestionResponse(
            job_id=job_id,
            status="running",
            message=f"Ingestion started for {request.business_area}"
        )
    
    except Exception as e:
        logger.error("Failed to trigger ingestion", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest/{job_id}", response_model=IngestionStatus)
async def get_ingestion_status(job_id: str) -> IngestionStatus:
    """
    Get ingestion job status.
    
    Args:
        job_id: Job ID
        
    Returns:
        Job status and progress
    """
    if job_id not in ingestion_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = ingestion_jobs[job_id]
    
    return IngestionStatus(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        error=job.get("error")
    )


@router.post("/incidents", response_model=IncidentResponse)
async def generate_incident_brief(request: IncidentRequest) -> IncidentResponse:
    """
    Generate an incident briefing for the provided payload.
    
    Args:
        request: Incident request payload
        
    Returns:
        Incident briefing and context
    """
    try:
        logger.info(
            "Incident request received",
            business_area=request.business_area,
            query=request.query[:100],
            payload_keys=list(request.incident_payload.keys())
        )

        workflow_result = await incident_workflow.run(
            query=request.query,
            business_area=request.business_area,
            incident_payload=request.incident_payload,
            retrieval_plan=request.retrieval_plan.dict() if request.retrieval_plan else None
        )

        attachments = [
            {
                "source": attachment["source"],
                "retriever": attachment["retriever"],
                "document_count": attachment["document_count"],
                "message": attachment["message"]
            }
            for attachment in workflow_result.get("attachments", [])
        ]

        response = IncidentResponse(
            briefing_summary=workflow_result.get("briefing_summary"),
            briefing_markdown=workflow_result.get("briefing_markdown"),
            incident_context=workflow_result.get("incident_context", {}),
            attachments=attachments,
            errors=workflow_result.get("errors", [])
        )

        logger.info(
            "Incident briefing generated",
            business_area=request.business_area,
            has_errors=bool(response.errors)
        )

        return response

    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "Incident briefing generation failed",
            business_area=request.business_area,
            error=str(exc)
        )
        raise HTTPException(status_code=500, detail=str(exc))


async def run_ingestion(
    job_id: str,
    business_area: str,
    sources: list | None,
    mode: str
):
    """
    Run ingestion in background.
    
    Args:
        job_id: Job ID
        business_area: Business area
        sources: Sources to ingest from
        mode: Sync mode (full/incremental)
    """
    try:
        logger.info(
            "Starting background ingestion",
            job_id=job_id,
            business_area=business_area
        )
        
        sync_mode = SyncMode.FULL if mode == "full" else SyncMode.INCREMENTAL
        
        if sources:
            # Ingest from specific sources
            results = {}
            for source_name in sources:
                try:
                    source_type = SourceType(source_name)
                    # Get source config
                    config = ingestion_service._get_sources_config(business_area).get(source_type)
                    
                    if config:
                        result = await ingestion_service.ingest(
                            business_area=business_area,
                            source=source_type,
                            config=config,
                            mode=sync_mode
                        )
                        results[source_name] = result
                    else:
                        results[source_name] = {
                            "status": "error",
                            "error": f"Source {source_name} not configured for {business_area}"
                        }
                except Exception as e:
                    logger.error(f"Failed to ingest from {source_name}", error=str(e))
                    results[source_name] = {
                        "status": "error",
                        "error": str(e)
                    }
        else:
            # Ingest from all sources
            results = await ingestion_service.ingest_all_sources(
                business_area=business_area,
                mode=sync_mode
            )
        
        # Update job status
        ingestion_jobs[job_id]["status"] = "completed"
        ingestion_jobs[job_id]["progress"] = results
        
        logger.info(
            "Background ingestion completed",
            job_id=job_id,
            business_area=business_area
        )
    
    except Exception as e:
        logger.error(
            "Background ingestion failed",
            job_id=job_id,
            error=str(e)
        )
        ingestion_jobs[job_id]["status"] = "failed"
        ingestion_jobs[job_id]["error"] = str(e)


# ============================================
# Code Source Management Endpoints
# ============================================
@router.post("/code-sources/register", response_model=CodeSourceResponse)
async def register_code_source(request: CodeSourceRegisterRequest) -> CodeSourceResponse:
    """
    Register a code source for CodeQL analysis.
    
    Args:
        request: Code source registration request
        
    Returns:
        Registered source information
    """
    try:
        source_id = code_source_registry.register(
            business_area=request.business_area,
            source_type=request.source_type,
            path=request.path,
            languages=request.languages,
            name=request.name,
            enabled=request.enabled
        )
        
        source = code_source_registry.get(source_id)
        if not source:
            raise HTTPException(status_code=500, detail="Failed to retrieve registered source")
        
        return CodeSourceResponse(
            source_id=source.source_id,
            business_area=source.business_area,
            source_type=source.source_type,
            path=source.path,
            languages=source.languages,
            name=source.name,
            enabled=source.enabled,
            last_analyzed_commit=source.last_analyzed_commit,
            last_analyzed_time=source.last_analyzed_time.isoformat() if source.last_analyzed_time else None
        )
    
    except Exception as e:
        logger.error("Failed to register code source", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/code-sources", response_model=CodeSourceListResponse)
async def list_code_sources(
    business_area: str | None = None,
    source_type: str | None = None,
    enabled_only: bool = False
) -> CodeSourceListResponse:
    """
    List registered code sources.
    
    Args:
        business_area: Optional filter by business area
        source_type: Optional filter by source type (gitlab, filesystem)
        enabled_only: Only return enabled sources
        
    Returns:
        List of code sources
    """
    try:
        sources = code_source_registry.list_sources(
            business_area=business_area,
            source_type=source_type,
            enabled_only=enabled_only
        )
        
        source_responses = [
            CodeSourceResponse(
                source_id=source.source_id,
                business_area=source.business_area,
                source_type=source.source_type,
                path=source.path,
                languages=source.languages,
                name=source.name,
                enabled=source.enabled,
                last_analyzed_commit=source.last_analyzed_commit,
                last_analyzed_time=source.last_analyzed_time.isoformat() if source.last_analyzed_time else None
            )
            for source in sources
        ]
        
        return CodeSourceListResponse(
            sources=source_responses,
            total=len(source_responses)
        )
    
    except Exception as e:
        logger.error("Failed to list code sources", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/code-sources/{source_id}", response_model=CodeSourceResponse)
async def get_code_source(source_id: str) -> CodeSourceResponse:
    """
    Get code source by ID.
    
    Args:
        source_id: Source ID
        
    Returns:
        Source information
    """
    source = code_source_registry.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
    
    return CodeSourceResponse(
        source_id=source.source_id,
        business_area=source.business_area,
        source_type=source.source_type,
        path=source.path,
        languages=source.languages,
        name=source.name,
        enabled=source.enabled,
        last_analyzed_commit=source.last_analyzed_commit,
        last_analyzed_time=source.last_analyzed_time.isoformat() if source.last_analyzed_time else None
    )


@router.delete("/code-sources/{source_id}")
async def delete_code_source(source_id: str) -> Dict[str, str]:
    """
    Delete a code source from registry.
    
    Args:
        source_id: Source ID
        
    Returns:
        Success message
    """
    try:
        code_source_registry.delete(source_id)
        return {"message": f"Source {source_id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete code source", source_id=source_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Code Analysis Endpoints
# ============================================
@router.post("/analyze", response_model=CodeAnalysisResponse)
async def trigger_code_analysis(
    request: CodeAnalysisRequest,
    background_tasks: BackgroundTasks
) -> CodeAnalysisResponse:
    """
    Trigger CodeQL analysis for code sources.
    
    Args:
        request: Analysis request (business_area or source_id)
        background_tasks: FastAPI background tasks
        
    Returns:
        Job ID and status
    """
    try:
        job_id = str(uuid.uuid4())
        
        if request.source_id:
            # Analyze specific source
            source = code_source_registry.get(request.source_id)
            if not source:
                raise HTTPException(status_code=404, detail=f"Source not found: {request.source_id}")
            
            background_tasks.add_task(
                run_code_analysis,
                job_id=job_id,
                source_id=request.source_id
            )
            
            message = f"Analysis started for source {request.source_id}"
            business_area = source.business_area
        
        elif request.business_area:
            # Analyze all sources for business area
            if not codeql_analysis_service.is_codeql_enabled(request.business_area):
                raise HTTPException(
                    status_code=400,
                    detail=f"CodeQL not enabled for business area: {request.business_area}"
                )
            
            background_tasks.add_task(
                run_code_analysis,
                job_id=job_id,
                business_area=request.business_area
            )
            
            message = f"Analysis started for business area {request.business_area}"
            business_area = request.business_area
        
        else:
            raise HTTPException(
                status_code=400,
                detail="Either business_area or source_id must be provided"
            )
        
        logger.info("Code analysis triggered", job_id=job_id, business_area=business_area)
        
        return CodeAnalysisResponse(
            job_id=job_id,
            status="running",
            message=message,
            business_area=business_area,
            source_id=request.source_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to trigger code analysis", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def run_code_analysis(
    job_id: str,
    source_id: str | None = None,
    business_area: str | None = None
):
    """
    Run code analysis in background.
    
    Args:
        job_id: Job ID
        source_id: Optional specific source ID
        business_area: Optional business area (analyzes all sources)
    """
    try:
        logger.info(
            "Starting background code analysis",
            job_id=job_id,
            source_id=source_id,
            business_area=business_area
        )
        
        if source_id:
            result = await codeql_analysis_service.analyze_source(source_id)
        elif business_area:
            result = await codeql_analysis_service.analyze_business_area(business_area)
        else:
            logger.error("Neither source_id nor business_area provided")
            return
        
        logger.info(
            "Background code analysis completed",
            job_id=job_id,
            status=result.get("status")
        )
    
    except Exception as e:
        logger.error(
            "Background code analysis failed",
            job_id=job_id,
            error=str(e)
        )
