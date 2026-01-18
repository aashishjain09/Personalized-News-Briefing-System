"""Port definitions (adapter pattern interfaces)."""

from .llm_port import LLMPort
from .vector_store_port import VectorStorePort, SearchResult
from .news_source_port import NewsSourcePort, Article as ArticleSchema
from .scheduler_port import SchedulerPort
from .user_memory_port import UserMemoryPort

__all__ = [
    "LLMPort",
    "VectorStorePort",
    "SearchResult",
    "NewsSourcePort",
    "ArticleSchema",
    "SchedulerPort",
    "UserMemoryPort",
]
