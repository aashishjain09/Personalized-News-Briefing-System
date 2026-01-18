"""Layer 1: Settings - Configuration management."""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any
import os
from pathlib import Path

class AppSettings(BaseModel):
    """Application settings."""
    name: str = "Personalized News Briefing"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True


class LLMSettings(BaseModel):
    """LLM configuration."""
    primary_model: str = "gpt-4-turbo-preview"
    fallback_model: str = "gpt-3.5-turbo"
    temperature: float = 0.3
    max_tokens: int = 1500
    timeout_seconds: int = 30
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0


class EmbeddingsSettings(BaseModel):
    """Embedding model configuration."""
    model: str = "text-embedding-3-large"
    dimension: int = 3072
    batch_size: int = 32
    timeout_seconds: int = 30


class VectorStoreSettings(BaseModel):
    """Vector store configuration."""
    type: str = "chroma"
    chroma_db_path: str = "./data/chroma_db"
    collection_name: str = "news_chunks"


class DatabaseSettings(BaseModel):
    """Database configuration."""
    type: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    name: str = "personalized_news"
    user: str = "postgres"
    password: str = "postgres"
    echo: bool = False

    @property
    def url(self) -> str:
        """Generate SQLAlchemy connection URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class IngestionSettings(BaseModel):
    """Ingestion configuration."""
    schedule_minutes: int = 60
    max_article_size_chars: int = 50000
    content_hash_check: bool = True
    dedup_days: int = 30


class RetrievalSettings(BaseModel):
    """Retrieval configuration."""
    default_k: int = 5
    max_k: int = 10
    time_window_days: int = 7
    metadata_filter_enabled: bool = True


class GroundingSettings(BaseModel):
    """Grounding verification configuration."""
    stage_a_enabled: bool = True
    stage_b_enabled: bool = True
    confidence_threshold: float = 0.7
    min_citation_coverage: float = 0.8


class SafetySettings(BaseModel):
    """Safety and security configuration."""
    max_query_length: int = 500
    max_article_length: int = 50000
    injection_detection_enabled: bool = True
    content_sanitization_enabled: bool = True
    rate_limit_per_minute: int = 60


class EmailSettings(BaseModel):
    """Email delivery configuration."""
    enabled: bool = True
    service: str = "sendgrid"
    from_address: str = "briefing@personalizednews.local"
    send_time_utc: str = "08:00"


class ObservabilitySettings(BaseModel):
    """Observability configuration."""
    log_level: str = "INFO"
    structured_logging: bool = True
    request_id_header: str = "X-Request-ID"
    trace_enabled: bool = False


class EvaluationSettings(BaseModel):
    """Evaluation configuration."""
    enabled: bool = True
    grounding_pass_rate_threshold: float = 0.90
    schema_validity_threshold: float = 0.95
    regression_gate_enabled: bool = True


class Settings(BaseSettings):
    """Main settings class aggregating all configuration."""
    
    app: AppSettings = Field(default_factory=AppSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    grounding: GroundingSettings = Field(default_factory=GroundingSettings)
    safety: SafetySettings = Field(default_factory=SafetySettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    evaluation: EvaluationSettings = Field(default_factory=EvaluationSettings)
    
    # Paths
    project_root: Path = Path(__file__).parent.parent.parent
    config_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "configs")
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")
    logs_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "logs")
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"
        case_sensitive = False

    def __init__(self, **data):
        super().__init__(**data)
        # Create required directories
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)


# Load settings from environment or config file
settings = Settings()
