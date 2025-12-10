"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import router as api_router
from app.models import HealthResponse, BusinessAreasResponse
from core.config import settings
from core.logging import configure_logging, get_logger
from vectorstore.qdrant_manager import qdrant_manager
from core.graph import neo4j_manager
from codeql import code_source_registry, codeql_analysis_service

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Traceback application", version=settings.app_version)
    
    # Initialize Qdrant collections
    try:
        qdrant_manager.initialize_collections()
        logger.info("Qdrant collections initialized")
    except Exception as e:
        logger.error("Failed to initialize Qdrant collections", error=str(e))
    
    # Initialize Neo4j schema (optional - only if code graph is enabled)
    if settings.codeql_enabled:
        try:
            if neo4j_manager.is_available():
                neo4j_manager.initialize_schema()
                logger.info("Neo4j schema initialized")
            else:
                logger.info("Neo4j not available, code graph features disabled")
        except Exception as e:
            logger.warning("Failed to initialize Neo4j schema", error=str(e))
    
    # Auto-register code sources from SOURCES_CONFIG
    if settings.codeql_enabled:
        try:
            for business_area in settings.business_areas_list:
                sources_config = settings.sources_config_map.get(business_area, {})
                codeql_config = sources_config.get("codeql")
                if codeql_config:
                    registered = codeql_analysis_service.register_source_from_config(
                        business_area=business_area,
                        codeql_config=codeql_config
                    )
                    if registered:
                        logger.info(
                            "Auto-registered code sources from config",
                            business_area=business_area,
                            source_count=len(registered)
                        )
        except Exception as e:
            logger.warning("Failed to auto-register code sources", error=str(e))
    
    yield
    
    # Shutdown Neo4j connection
    if neo4j_manager.is_available():
        try:
            neo4j_manager.close()
        except Exception as e:
            logger.warning("Error closing Neo4j connection", error=str(e))
    
    # Shutdown
        logger.info("Shutting down Traceback application")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise Knowledge Agent Platform - Your organization's knowledge, retrieved, reasoned, and governed.",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check Qdrant connection
        collections_info = []
        for business_area in settings.business_areas_list:
            try:
                info = qdrant_manager.get_collection_info(business_area)
                collections_info.append(info)
            except Exception as e:
                logger.error(f"Failed to get info for {business_area}", error=str(e))
        
        services = {
            "qdrant": "connected",
            "collections": collections_info
        }
        
        # Check Neo4j if code graph is enabled
        if settings.codeql_enabled:
            if neo4j_manager.is_available():
                services["neo4j"] = "connected"
            else:
                services["neo4j"] = "unavailable"
        
        return HealthResponse(
            status="healthy",
            services=services
        )
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return HealthResponse(
            status="unhealthy",
            services={
                "error": str(e)
            }
        )


@app.get("/api/v1/business-areas", response_model=BusinessAreasResponse)
async def get_business_areas():
    """Get list of available business areas."""
    return BusinessAreasResponse(
        business_areas=settings.business_areas_list
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
