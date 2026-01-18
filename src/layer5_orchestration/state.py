"""Layer 5: Orchestration - Agent state definitions for LangGraph checkpointing."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AgentMode(str, Enum):
    """Agent operational modes."""
    QA = "qa"
    BRIEFING = "briefing"


class AgentState(BaseModel):
    """Q&A agent state (checkpointed at each node) - for LangGraph."""
    request_id: str                              # UUID for tracing
    query: str                                   # User query
    user_id: str = "implicit_personal_user"     # Always same (personal use)
    mode: AgentMode = AgentMode.QA              # qa | briefing
    
    # Profile snapshot
    profile_topics: List[str] = []              # User interest topics
    profile_blocked: List[str] = []             # Blocked topics
    preferences: dict = {}                      # briefing_length, time_window_days
    
    # Retrieval results
    retrieval_needed: bool = False              # Agent decides
    retrieved_chunks: List[dict] = []           # [{"id": "chunk_123", "text": "...", "metadata": {...}}]
    retrieval_k: int = 5                        # Dynamic K
    
    # Generation results
    draft_output: Optional[str] = None          # LLM response
    citations: List[dict] = []                  # [{"url": "...", "chunk_id": "...", "quote": "..."}]
    
    # Validation results
    schema_valid: bool = False                  # Schema passes Pydantic
    grounding_pass: bool = False                # Citations verified
    confidence_score: float = 0.0               # 0.0-1.0
    
    # Token tracking
    tokens_in: int = 0                          # Input tokens
    tokens_out: int = 0                         # Output tokens
    token_budget_remaining: int = 5000          # Dynamic budget
    
    # Error tracking
    errors: List[str] = []                      # Error messages for recovery
    fallback_model_used: bool = False           # Indicates fallback triggered
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True


class BriefingState(BaseModel):
    """Daily briefing agent state - for LangGraph."""
    request_id: str
    date: datetime
    user_id: str = "implicit_personal_user"
    
    # Profile
    profile_topics: List[str] = []
    briefing_length: str = "medium"            # short | medium | long
    time_window_hours: int = 24                # Last N hours
    
    # Retrieval per topic
    topic_articles: dict = {}                  # {"AI": [chunks], "aviation": [chunks]}
    all_chunks: List[dict] = []                # Deduped chunks
    
    # Output
    briefing_text: Optional[str] = None        # Markdown briefing
    citations: List[dict] = []
    
    # Validation
    schema_valid: bool = False
    grounding_pass: bool = False
    confidence_score: float = 0.0
    
    # Tokens
    tokens_in: int = 0
    tokens_out: int = 0
    
    # Email delivery
    email_sent: bool = False
    email_timestamp: Optional[datetime] = None
    
    # Error tracking
    errors: List[str] = []
    fallback_model_used: bool = False
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True


class ChatRequest(BaseModel):
    """Request to chat endpoint."""
    query: str                         # "What's latest in AI?"
    time_window_days: int = 7          # Last N days
    stream: bool = False               # Future: streaming responses


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    answer: str                        # Markdown response
    citations: List[dict]              # [{"url": "...", "title": "...", "quote": "..."}]
    used_articles: List[str]           # Article IDs used
    grounding_pass: bool               # Grounding verified
    confidence: float                  # 0.0-1.0
    request_id: str                    # Tracing ID
    latency_ms: int                    # Response time


class BriefingRequest(BaseModel):
    """Request to generate briefing."""
    date: Optional[str] = None         # "2026-01-18" (today by default)
    time_window_hours: int = 24        # Last N hours


class BriefingResponse(BaseModel):
    """Response from briefing endpoint."""
    briefing: str                      # Markdown briefing
    citations: List[dict]              # Source articles
    grounding_pass: bool
    confidence: float
    email_sent: bool                   # Delivered to email?
    request_id: str


class FeedbackRequest(BaseModel):
    """Feedback submission."""
    signal: str                        # like | dislike | save | skip
    article_id: str                    # From previous response
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Feedback submission response."""
    status: str = "success"
    message: str
    request_id: str
