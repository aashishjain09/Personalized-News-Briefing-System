"""Layer 6: API - Middleware for request handling, logging, and safety."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware as StarleteCORSMiddleware
from uuid import uuid4
import time
import json
from typing import Callable

from src.layer1_settings import (
    settings,
    get_logger,
    set_request_id,
    get_request_id,
    RATE_LIMIT_PER_MINUTE,
)
from src.layer1_settings.errors import PersonalizedNewsError

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with request ID and timing."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID if not provided
        request_id = request.headers.get(settings.observability.request_id_header)
        if not request_id:
            request_id = str(uuid4())
        
        set_request_id(request_id)
        
        # Add to request state
        request.state.request_id = request_id
        request.state.start_time = time.time()
        
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={"request_id": request_id, "method": request.method, "path": request.url.path}
        )
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response
        response.headers[settings.observability.request_id_header] = request_id
        
        # Log response with timing
        duration = time.time() - request.state.start_time
        logger.info(
            f"Response: {request.method} {request.url.path} {response.status_code} ({duration*1000:.1f}ms)",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "duration_ms": duration * 1000
            }
        )
        
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Handle application errors and return structured error responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except PersonalizedNewsError as e:
            # Application errors
            logger.error(
                f"Application error: {str(e)}",
                extra={"request_id": get_request_id(), "error_type": type(e).__name__}
            )
            return Response(
                content=json.dumps({
                    "error": str(e),
                    "request_id": get_request_id(),
                    "status": "error",
                    "error_type": type(e).__name__,
                }),
                status_code=500,
                media_type="application/json",
            )
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={"request_id": get_request_id()},
                exc_info=True
            )
            return Response(
                content=json.dumps({
                    "error": "Internal server error",
                    "request_id": get_request_id(),
                    "status": "error",
                }),
                status_code=500,
                media_type="application/json",
            )


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware (in-memory, per-endpoint)."""
    
    def __init__(self, app):
        super().__init__(app)
        # Simple in-memory rate limit tracking (IP-based)
        # In production, use Redis
        self.request_counts = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Increment request count for this IP
        key = f"{client_ip}:{request.method}:{request.url.path}"
        self.request_counts[key] = self.request_counts.get(key, 0) + 1
        
        # Check rate limit (simplified - in production use Redis)
        if self.request_counts[key] > RATE_LIMIT_PER_MINUTE:
            logger.warning(
                f"Rate limit exceeded for {client_ip}",
                extra={"request_id": get_request_id(), "client_ip": client_ip}
            )
            return Response(
                content=json.dumps({
                    "error": "Rate limit exceeded",
                    "request_id": get_request_id(),
                    "status": "error",
                }),
                status_code=429,
                media_type="application/json",
            )
        
        return await call_next(request)


class CORSMiddleware(StarleteCORSMiddleware):
    """CORS middleware with safe defaults."""
    
    def __init__(self, app):
        super().__init__(
            app,
            allow_origins=["http://localhost:3000", "http://localhost:8000"],  # Frontend dev servers
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
