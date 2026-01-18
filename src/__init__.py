"""Personalized News Brief - Production-grade AI news briefing system.

This is a 7-layer architecture:
- Layer 1 (Settings): Configuration, logging, error definitions
- Layer 2 (Persistence): SQL + vector store data access
- Layer 3 (Safety): Input validation, injection detection, grounding
- Layer 4 (Services): Business logic with resilience patterns
- Layer 5 (Orchestration): LangGraph agents, state management
- Layer 6 (API): FastAPI endpoints, middleware
- Layer 7 (Observability): Metrics, evaluation, tracing
"""

from layer1_settings import settings, logger
from layer2_persistence import db_manager, Article, Chunk, FeedbackEvent, BriefingRun, UserProfile
from layer5_orchestration import AgentState, BriefingState, ChatRequest, ChatResponse

__version__ = "0.1.0"

__all__ = [
    "settings",
    "logger",
    "db_manager",
    "Article",
    "Chunk",
    "FeedbackEvent",
    "BriefingRun",
    "UserProfile",
    "AgentState",
    "BriefingState",
    "ChatRequest",
    "ChatResponse",
]
