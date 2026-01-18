"""Layer 1: Settings - Configuration, logging, error definitions."""

from .config import Settings, settings
from .logger import setup_logging, get_logger, set_request_id, get_request_id

# Create application logger instance
logger = get_logger("personalized_news_brief")

from .errors import (
    PersonalizedNewsError,
    RateLimitError,
    APIConnectionError,
    APIStatusError,
    TokenLimitError,
    InputValidationError,
    InjectionDetectedError,
    GroundingViolationError,
    SchemaValidationError,
    DatabaseError,
    VectorStoreError,
    EmbeddingError,
    IngestionError,
    RetrievalError,
    SynthesisError,
    BriefingGenerationError,
    CircuitBreakerOpenError,
    DegradedModeError,
    TimeoutError,
)
from .constants import *

__all__ = [
    # Config
    "Settings",
    "settings",
    # Logging
    "logger",
    "setup_logging",
    "get_logger",
    "set_request_id",
    "get_request_id",
    # Errors
    "PersonalizedNewsError",
    "RateLimitError",
    "APIConnectionError",
    "APIStatusError",
    "TokenLimitError",
    "InputValidationError",
    "InjectionDetectedError",
    "GroundingViolationError",
    "SchemaValidationError",
    "DatabaseError",
    "VectorStoreError",
    "EmbeddingError",
    "IngestionError",
    "RetrievalError",
    "SynthesisError",
    "BriefingGenerationError",
    "CircuitBreakerOpenError",
    "DegradedModeError",
    "TimeoutError",
]
