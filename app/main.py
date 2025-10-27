"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import router as api_router
from app.models import HealthResponse, BusinessAreasResponse
from core.config import settings
from core.logging import configure_logging, get_logger
from vectorstore.qdrant_manager import qdrant_manager

# Configure logging
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting EKAP application", version=settings.app_version)
    
    # Initialize Qdrant collections
    try:
        qdrant_manager.initialize_collections()
        logger.info("Qdrant collections initialized")
    except Exception as e:
        logger.error("Failed to initialize Qdrant collections", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("Shutting down EKAP application")


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
        
        return HealthResponse(
            status="healthy",
            services={
                "qdrant": "connected",
                "collections": collections_info
            }
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
