"""Layer 1: Settings - Application constants."""

# Chunking
DEFAULT_CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200  # characters
MIN_CHUNK_SIZE = 100  # characters
MAX_CHUNK_SIZE = 2000  # characters

# Retrieval
DEFAULT_RETRIEVAL_K = 5
MIN_RETRIEVAL_K = 1
MAX_RETRIEVAL_K = 20
DEFAULT_TIME_WINDOW_DAYS = 7

# Token budgeting
SYSTEM_PROMPT_TOKENS = 800
QUERY_TOKEN_ESTIMATE = 100
RETRIEVED_CONTEXT_TOKENS = 3000
OUTPUT_TOKEN_BUDGET = 1000
TOTAL_TOKEN_BUDGET = 5000

# Rate limiting
RATE_LIMIT_PER_MINUTE = 60
RATE_LIMIT_BURST_SIZE = 10

# Retry & backoff
MAX_RETRY_ATTEMPTS = 3
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
BACKOFF_MULTIPLIER = 2.0

# Timeouts
LLM_CALL_TIMEOUT_SECONDS = 30
VECTOR_STORE_TIMEOUT_SECONDS = 10
DATABASE_TIMEOUT_SECONDS = 5
API_CALL_TIMEOUT_SECONDS = 15

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_ERROR_RATE_THRESHOLD = 0.5
CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = 60

# Grounding
MIN_GROUNDING_CONFIDENCE = 0.7
MIN_CITATION_COVERAGE = 0.8
MAX_UNSUPPORTED_CLAIMS = 0.1  # 10% of claims can be non-factual

# Input validation
MAX_QUERY_LENGTH = 500
MAX_ARTICLE_LENGTH = 50000
MAX_FEEDBACK_COMMENT_LENGTH = 1000
ALLOWED_QUERY_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?;:-'\"()")

# Injection detection patterns
INJECTION_PATTERNS = [
    "ignore previous",
    "system prompt",
    "override",
    "bypass",
    "disregard",
    "forget",
    "initial instructions",
    "security override",
    "admin mode",
    "superuser",
]

# Scheduling
DEFAULT_BRIEFING_SCHEDULE_HOUR = 8  # 8 AM UTC
INGESTION_SCHEDULE_MINUTES = 60  # Every hour

# Email
EMAIL_TEMPLATE_DIR = "configs/prompts/templates"
SUPPORTED_EMAIL_SERVICES = ["sendgrid", "ses"]

# Evaluation
GROUNDING_PASS_RATE_THRESHOLD = 0.90
SCHEMA_VALIDITY_THRESHOLD = 0.95
HALLUCINATION_RATE_THRESHOLD = 0.05  # 5% max
INJECTION_TEST_PASS_RATE_THRESHOLD = 1.0  # 100% must fail injection

# Cache
EMBEDDING_CACHE_MAX_SIZE = 10000  # Max cached embeddings
QUERY_CACHE_TTL_SECONDS = 3600  # 1 hour
EMBEDDING_CACHE_TTL_SECONDS = 86400  # 24 hours

# Personalization
DEFAULT_BRIEFING_LENGTH = "medium"  # short | medium | long
FEEDBACK_WINDOW_DAYS = 30  # Consider feedback from last 30 days
MIN_FEEDBACK_SAMPLES_FOR_PERSONALIZATION = 5

# Personal user (no multi-user auth)
IMPLICIT_USER_ID = "implicit_personal_user"

# API versions
API_VERSION = "v1"
API_PREFIX = "/api/v1"
