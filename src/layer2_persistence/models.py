"""Layer 2: Persistence - SQLAlchemy ORM models."""

from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Boolean, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional, Dict, List

Base = declarative_base()


class Article(Base):
    """News article metadata (Layer 2)."""
    __tablename__ = "articles"
    
    article_id = Column(String(64), primary_key=True)  # SHA256(url)
    url = Column(String(2048), unique=True, index=True, nullable=False)
    title = Column(String(512), nullable=False)
    source = Column(String(128), index=True)  # BBC, Hacker News, Aviation Today, etc.
    published_at = Column(DateTime, index=True)  # Article publication date
    
    raw_text = Column(Text, nullable=False)  # Full article text
    clean_text = Column(Text, nullable=False)  # Sanitized text
    content_hash = Column(String(64), unique=False)  # For change detection
    
    ingested_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    metadata = Column(JSON)  # {"topic_tags": [...], "entity_names": [...], "category": "..."}
    
    __table_args__ = (
        Index('ix_articles_ingested_source', 'ingested_at', 'source'),
    )


class Chunk(Base):
    """Chunk embeddings (Layer 2)."""
    __tablename__ = "chunks"
    
    chunk_id = Column(String(64), primary_key=True)  # UUID
    article_id = Column(String(64), index=True, nullable=False)  # FK to Article
    chunk_text = Column(Text, nullable=False)  # 800-1200 chars
    
    embedding_id = Column(String(128))  # Chroma collection ID
    metadata = Column(JSON, nullable=False)  # {url, source, published_at, chunk_idx, title}
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('ix_chunks_article_id', 'article_id'),
    )


class FeedbackEvent(Base):
    """User feedback for personalization (Layer 2)."""
    __tablename__ = "feedback_events"
    
    event_id = Column(String(64), primary_key=True)  # UUID
    user_id = Column(String(64), default="implicit_personal_user", index=True)
    article_id = Column(String(64), index=True)  # FK to Article (optional)
    
    signal = Column(String(16), index=True)  # like | dislike | save | skip
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    comment = Column(Text)  # Optional user comment
    
    topic_inferred = Column(String(128))  # Extracted topic from article
    
    __table_args__ = (
        Index('ix_feedback_user_timestamp', 'user_id', 'timestamp'),
    )


class BriefingRun(Base):
    """Audit log of briefing generation (Layer 2)."""
    __tablename__ = "briefing_runs"
    
    run_id = Column(String(64), primary_key=True)
    user_id = Column(String(64), default="implicit_personal_user", index=True)
    date = Column(DateTime, index=True)  # Date of briefing
    
    status = Column(String(16))  # success | fail | degraded
    briefing_text = Column(Text)  # Markdown output
    citations = Column(JSON)  # [{"url": "...", "title": "...", "chunk_id": "..."}]
    
    tokens_in = Column(Integer)
    tokens_out = Column(Integer)
    latency_ms = Column(Integer)
    
    grounding_pass = Column(Boolean)
    confidence_score = Column(Float)
    
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('ix_briefing_user_date', 'user_id', 'date'),
    )


class UserProfile(Base):
    """Personal user preferences and memory (Layer 2)."""
    __tablename__ = "user_profiles"
    
    user_id = Column(String(64), primary_key=True)  # "implicit_personal_user"
    
    # Explicit preferences
    explicit_topics = Column(JSON)  # ["AI", "aviation", "tech"]
    blocked_topics = Column(JSON)  # ["celebrity", "gossip"]
    
    # Learned preferences from feedback
    inferred_topics = Column(JSON)  # {"AI": 0.8, "tech": 0.6}
    topic_weights = Column(JSON)  # Dynamic topic interest scores
    
    # Briefing preferences
    briefing_length = Column(String(16), default="medium")  # short | medium | long
    briefing_time_hours = Column(String(5), default="08:00")  # 08:00 UTC
    time_window_days = Column(Integer, default=3)  # Last N days of articles
    
    # Engagement
    total_feedback_events = Column(Integer, default=0)
    last_feedback_at = Column(DateTime)
    
    # Email settings
    email_enabled = Column(Boolean, default=True)
    last_email_sent = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
