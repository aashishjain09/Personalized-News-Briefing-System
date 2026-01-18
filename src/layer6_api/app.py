"""Layer 6: API - FastAPI application initialization."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import logging

from src.layer1_settings import settings, get_logger, set_request_id
from src.layer6_api.middleware import (
    RequestLoggingMiddleware,
    ErrorHandlerMiddleware,
    RateLimitingMiddleware,
    CORSMiddleware,
)

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        description="Production-grade AI personalized news briefing with RAG, grounding, and safety",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    
    # Add middleware (order matters - last added is first executed)
    app.add_middleware(CORSMiddleware)
    app.add_middleware(RateLimitingMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": settings.app.version,
            "environment": settings.app.environment,
        }
    
    # Include API routers
    from src.layer6_api.routers import chat, briefing, feedback, health
    
    app.include_router(chat.router)
    app.include_router(briefing.router)
    app.include_router(feedback.router)
    app.include_router(health.router)
    
    # Mount static files for web UI
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Serve web UI at root
    @app.get("/")
    async def serve_root():
        """Serve web UI."""
        index_path = Path(__file__).parent / "static" / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Web UI not available"}
    
    logger.info(f"FastAPI app created: {settings.app.name} v{settings.app.version}")
    
    return app


# Create app instance
app = create_app()
