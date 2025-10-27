"""API routes for EKAP."""
import uuid
from typing import Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models import (
    QueryRequest,
    QueryResponse,
    IngestionRequest,
    IngestionResponse,
    IngestionStatus
)
from agents.graph import knowledge_workflow
from ingestion.service import ingestion_service, SyncMode
from ingestion.base import SourceType
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["api"])

# In-memory job storage (use Redis in production)
ingestion_jobs: Dict[str, Dict] = {}


@router.post("/query", response_model=QueryResponse)
async def query_knowledge(request: QueryRequest) -> QueryResponse:
    """
    Query the knowledge base using multi-agent workflow.
    
    Args:
        request: Query request with query and business_area
        
    Returns:
        Response with answer, sources, and metadata
    """
    try:
        logger.info(
            "Query received",
            query=request.query[:50],
            business_area=request.business_area
        )
        
        # Run workflow
        result = await knowledge_workflow.run(
            query=request.query,
            business_area=request.business_area,
            max_iterations=request.max_iterations
        )
        
        # Format response
        response = QueryResponse(
            response=result["response"],
            sources=[
                {
                    "title": s["title"],
                    "source": s["source"],
                    "document_type": s["document_type"],
                    "url": s["url"],
                    "score": s["score"]
                }
                for s in result["sources"]
            ],
            metadata=result["metadata"]
        )
        
        logger.info(
            "Query completed",
            business_area=request.business_area,
            sources_count=len(response.sources)
        )
        
        return response
    
    except Exception as e:
        logger.error("Query failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


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
