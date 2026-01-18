"""Layer 1: Settings - Typed exception hierarchy."""


class PersonalizedNewsError(Exception):
    """Base exception for all application errors."""
    pass


# Tier 1: External service errors


class RateLimitError(PersonalizedNewsError):
    """Rate limit exceeded (429 HTTP status)."""
    def __init__(self, service: str, retry_after: int = 60):
        self.service = service
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded for {service}. Retry after {retry_after}s.")


class APIConnectionError(PersonalizedNewsError):
    """Failed to connect to external API (timeout, network error)."""
    def __init__(self, service: str, original_error: Exception):
        self.service = service
        self.original_error = original_error
        super().__init__(f"Connection error to {service}: {str(original_error)}")


class APIStatusError(PersonalizedNewsError):
    """API returned non-success status code (not 4xx/5xx handled above)."""
    def __init__(self, service: str, status_code: int, message: str):
        self.service = service
        self.status_code = status_code
        super().__init__(f"{service} returned {status_code}: {message}")


class TokenLimitError(PersonalizedNewsError):
    """Exceeded token budget for LLM call."""
    def __init__(self, tokens_requested: int, budget: int):
        self.tokens_requested = tokens_requested
        self.budget = budget
        super().__init__(f"Tokens requested ({tokens_requested}) exceed budget ({budget})")


# Tier 2: Data validation and safety


class InputValidationError(PersonalizedNewsError):
    """User input failed validation (length, char set, format)."""
    def __init__(self, field: str, reason: str):
        self.field = field
        super().__init__(f"Validation error in {field}: {reason}")


class InjectionDetectedError(PersonalizedNewsError):
    """Prompt injection pattern detected in input or retrieved content."""
    def __init__(self, location: str, pattern: str):
        self.location = location
        self.pattern = pattern
        super().__init__(f"Injection pattern detected in {location}: {pattern}")


class GroundingViolationError(PersonalizedNewsError):
    """Output failed grounding check (no valid citations)."""
    def __init__(self, reason: str):
        super().__init__(f"Grounding verification failed: {reason}")


class SchemaValidationError(PersonalizedNewsError):
    """Output failed Pydantic schema validation."""
    def __init__(self, model_name: str, errors: list):
        self.model_name = model_name
        self.errors = errors
        super().__init__(f"Schema validation failed for {model_name}: {errors}")


# Tier 3: Data persistence errors


class DatabaseError(PersonalizedNewsError):
    """Database connection or query error."""
    def __init__(self, operation: str, original_error: Exception):
        self.operation = operation
        super().__init__(f"Database error during {operation}: {str(original_error)}")


class VectorStoreError(PersonalizedNewsError):
    """Vector database operation failed."""
    def __init__(self, operation: str, original_error: Exception):
        self.operation = operation
        super().__init__(f"Vector store error during {operation}: {str(original_error)}")


class EmbeddingError(PersonalizedNewsError):
    """Failed to generate embeddings."""
    def __init__(self, reason: str):
        super().__init__(f"Embedding generation failed: {reason}")


# Tier 4: Business logic errors


class IngestionError(PersonalizedNewsError):
    """Article ingestion pipeline failed."""
    def __init__(self, stage: str, reason: str):
        self.stage = stage
        super().__init__(f"Ingestion failed at {stage}: {reason}")


class RetrievalError(PersonalizedNewsError):
    """Document retrieval failed."""
    def __init__(self, reason: str):
        super().__init__(f"Retrieval failed: {reason}")


class SynthesisError(PersonalizedNewsError):
    """LLM synthesis/generation failed."""
    def __init__(self, reason: str):
        super().__init__(f"Synthesis failed: {reason}")


class BriefingGenerationError(PersonalizedNewsError):
    """Daily briefing generation failed."""
    def __init__(self, reason: str):
        super().__init__(f"Briefing generation failed: {reason}")


# Tier 5: Operational errors


class CircuitBreakerOpenError(PersonalizedNewsError):
    """Circuit breaker is open, preventing operation."""
    def __init__(self, service: str, retry_after: int = 60):
        self.service = service
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker open for {service}. Try again after {retry_after}s.")


class DegradedModeError(PersonalizedNewsError):
    """System operating in degraded mode (partial functionality)."""
    def __init__(self, reason: str, fallback_available: bool):
        self.fallback_available = fallback_available
        super().__init__(f"Degraded mode: {reason}. Fallback available: {fallback_available}")


class TimeoutError(PersonalizedNewsError):
    """Operation exceeded timeout."""
    def __init__(self, operation: str, timeout_seconds: int):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(f"{operation} exceeded timeout of {timeout_seconds}s")
