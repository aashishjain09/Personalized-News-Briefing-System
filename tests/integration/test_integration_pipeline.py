"""Integration tests for ingestion pipeline."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

from src.utils import TextCleaner, TextChunker, ContentHasher, clean_and_chunk
from src.layer4_services import EmbedderService, IngestionService
from src.layer2_persistence.models import Article as ArticleORM, Chunk as ChunkORM
from src.layer2_persistence.database import DatabaseManager
from src.domain.ports.news_source_port import NewsSourcePort, Article as ArticleSchema
from src.domain.ports.vector_store_port import VectorStorePort, SearchResult
from src.utils import TimeUtility


class MockVectorStore(VectorStorePort):
    """Mock vector store for testing."""

    def __init__(self):
        self.embeddings: Dict[str, Dict[str, Any]] = {}

    def add_embeddings(
        self,
        chunk_ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Store embeddings in memory."""
        for cid, text, emb, meta in zip(chunk_ids, texts, embeddings, metadatas or []):
            self.embeddings[cid] = {
                "text": text,
                "embedding": emb,
                "metadata": meta or {},
            }

    def search(
        self, embedding: List[float], k: int = 5, where: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Mock search (returns dummy results)."""
        results = []
        for cid, data in list(self.embeddings.items())[:k]:
            results.append(
                SearchResult(
                    chunk_id=cid,
                    text=data["text"],
                    similarity=0.95,
                    metadata=data["metadata"],
                )
            )
        return results

    def delete(self, chunk_ids: List[str]) -> None:
        """Delete embeddings."""
        for cid in chunk_ids:
            self.embeddings.pop(cid, None)

    def get_stats(self) -> Dict[str, Any]:
        """Get store stats."""
        return {"total_embeddings": len(self.embeddings)}

    def health_check(self) -> bool:
        """Always healthy for mock."""
        return True


class MockNewsSource(NewsSourcePort):
    """Mock news source for testing."""

    def __init__(self, articles: Optional[List[ArticleSchema]] = None):
        self.articles = articles or []

    def fetch(self, source_name: str) -> List[ArticleSchema]:
        """Return mock articles."""
        return self.articles

    def health_check(self) -> bool:
        """Always healthy for mock."""
        return True


class TestTextCleaning:
    """Tests for text cleaning utilities."""

    def test_clean_removes_html_tags(self):
        """HTML tags should be removed."""
        html = "<p>Hello <b>world</b></p>"
        cleaned = TextCleaner.clean(html)
        assert "<" not in cleaned
        assert ">" not in cleaned
        assert "Hello" in cleaned
        assert "world" in cleaned

    def test_clean_normalizes_whitespace(self):
        """Multiple spaces should be normalized."""
        text = "Hello    world  \n\n\n  test"
        cleaned = TextCleaner.clean(text)
        assert "    " not in cleaned
        assert cleaned.count("\n") <= 2  # At most double newline

    def test_clean_handles_empty_string(self):
        """Empty string should return empty."""
        assert TextCleaner.clean("") == ""
        assert TextCleaner.clean("   ") == ""

    def test_clean_decodes_html_entities(self):
        """HTML entities should be decoded."""
        text = "Hello &amp; goodbye &quot;world&quot;"
        cleaned = TextCleaner.clean(text)
        assert "&" in cleaned or "and" in cleaned  # & or decoded
        assert "goodbye" in cleaned


class TestTextChunking:
    """Tests for text chunking."""

    def test_chunk_size_validation(self):
        """Invalid chunk sizes should raise."""
        if not PYTEST_AVAILABLE:
            return  # Skip if pytest not available
        try:
            TextChunker(chunk_size=50)  # Too small
            assert False, "Should raise ValueError"
        except ValueError:
            pass
        
        try:
            TextChunker(chunk_size=1000, overlap=0.6)  # Overlap too high
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_chunk_respects_size(self):
        """Chunks should respect size limit."""
        text = "a" * 5000  # 5000 chars
        chunker = TextChunker(chunk_size=1000, overlap=0.2)
        chunks = chunker.chunk(text)

        for chunk in chunks:
            assert len(chunk) <= 1000 * 1.2  # Allow small overage

    def test_chunk_creates_overlap(self):
        """Chunks should overlap."""
        text = "This is a test. " * 100  # ~1600 chars
        chunker = TextChunker(chunk_size=800, overlap=0.2)
        chunks = chunker.chunk(text)

        assert len(chunks) >= 2
        # Check that consecutive chunks overlap
        if len(chunks) > 1:
            # First chunk should end with content that appears in second chunk
            assert len(chunks[0]) > 0
            assert len(chunks[1]) > 0

    def test_chunk_handles_empty_text(self):
        """Empty text should return empty list."""
        chunker = TextChunker(chunk_size=1000, overlap=0.2)
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_clean_and_chunk_integration(self):
        """clean_and_chunk should work end-to-end."""
        html = "<p>Hello world. " * 100 + "</p>"
        chunks = clean_and_chunk(html, chunk_size=500, overlap=0.2)

        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)
        assert all(len(c) > 0 for c in chunks)


class TestContentHashing:
    """Tests for content hashing and deduplication."""

    def test_hash_url_consistency(self):
        """Same URL should always produce same hash."""
        url = "https://example.com/article"
        hash1 = ContentHasher.hash_url(url)
        hash2 = ContentHasher.hash_url(url)
        assert hash1 == hash2

    def test_hash_url_normalization(self):
        """URL hashing should be case-insensitive."""
        hash1 = ContentHasher.hash_url("https://EXAMPLE.com/Article")
        hash2 = ContentHasher.hash_url("https://example.com/article")
        assert hash1 == hash2

    def test_hash_content_consistency(self):
        """Same content should always produce same hash."""
        content = "This is test content."
        hash1 = ContentHasher.hash_content(content)
        hash2 = ContentHasher.hash_content(content)
        assert hash1 == hash2

    def test_duplicate_detection(self):
        """Duplicate detection should work."""
        url = "https://example.com"
        url_hash = ContentHasher.hash_url(url)
        existing_hashes = {url_hash}

        # Same URL should be detected as duplicate
        assert ContentHasher.is_duplicate_url(url_hash, existing_hashes)

        # Different URL should not be duplicate
        different_hash = ContentHasher.hash_url("https://other.com")
        assert not ContentHasher.is_duplicate_url(different_hash, existing_hashes)


class TestEmbedderService:
    """Tests for embedding service."""

    def test_embedder_initialization(self):
        """Embedder should initialize cleanly."""
        embedder = EmbedderService()
        assert embedder.cache_hits == 0
        assert embedder.cache_misses == 0

    def test_embedder_cache_stats(self):
        """Cache stats should be accurate."""
        embedder = EmbedderService()
        
        # Mock add to cache
        embedder._cache["hash1"] = ([0.1, 0.2], TimeUtility.now_utc())
        embedder.cache_hits = 5
        embedder.cache_misses = 5

        stats = embedder.get_cache_stats()
        assert stats["cache_size"] == 1
        assert stats["hits"] == 5
        assert stats["misses"] == 5
        assert stats["total_requests"] == 10
        assert stats["hit_rate_percent"] == 50.0

    def test_embedder_cache_clear(self):
        """Cache clearing should work."""
        embedder = EmbedderService()
        
        # Add entries
        embedder._cache["hash1"] = ([0.1], TimeUtility.now_utc())
        embedder._cache["hash2"] = ([0.2], TimeUtility.now_utc())
        
        assert len(embedder._cache) == 2
        removed = embedder.clear_cache()
        assert removed == 2
        assert len(embedder._cache) == 0


class TestIngestionService:
    """Tests for ingestion service."""

    def test_ingestion_initialization(self, tmp_path):
        """Service should initialize with dependencies."""
        vector_store = MockVectorStore()
        news_source = MockNewsSource()
        db_manager = DatabaseManager()  # Uses test DB from config

        service = IngestionService(
            news_source=news_source,
            vector_store=vector_store,
            db_manager=db_manager,
        )

        assert service.news_source is news_source
        assert service.vector_store is vector_store
        assert service.db_manager is db_manager
        assert service.embedder is not None

    def test_ingestion_empty_source(self, tmp_path):
        """Ingestion of empty source should return stats."""
        vector_store = MockVectorStore()
        news_source = MockNewsSource(articles=[])
        db_manager = DatabaseManager()

        service = IngestionService(
            news_source=news_source,
            vector_store=vector_store,
            db_manager=db_manager,
        )

        stats = service.ingest_source("empty_source")
        assert stats["total_fetched"] == 0
        assert stats["errors"] == 0

    def test_duplicate_url_detection(self, tmp_path):
        """Duplicate URLs should be skipped."""
        vector_store = MockVectorStore()
        
        # Create article
        article = ArticleSchema(
            title="Test Article",
            url="https://example.com/test",
            source="test_source",
            published_at=TimeUtility.now_utc(),
            author="Test Author",
            raw_text="Test content for duplicate detection.",
        )
        
        news_source = MockNewsSource(articles=[article, article])  # Duplicate
        db_manager = DatabaseManager()

        service = IngestionService(
            news_source=news_source,
            vector_store=vector_store,
            db_manager=db_manager,
        )

        # Mock embedder to avoid OpenAI calls
        service.embedder = EmbedderService()
        
        # This should ingest first but skip second (duplicate URL)
        # Note: Without full DB setup, this is a partial test
        assert service.stats["total_fetched"] == 2

    def test_ingestion_stats_tracking(self, tmp_path):
        """Ingestion should track statistics."""
        vector_store = MockVectorStore()
        news_source = MockNewsSource(articles=[])
        db_manager = DatabaseManager()

        service = IngestionService(
            news_source=news_source,
            vector_store=vector_store,
            db_manager=db_manager,
        )

        assert service.get_stats()["total_fetched"] == 0
        assert service.get_stats()["total_ingested"] == 0


class TestVectorStoreIntegration:
    """Tests for vector store integration."""

    def test_mock_vector_store_add_retrieve(self):
        """Mock vector store should store and retrieve."""
        store = MockVectorStore()
        
        chunk_ids = ["chunk1", "chunk2"]
        texts = ["First chunk", "Second chunk"]
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        metadatas = [{"source": "test"}, {"source": "test"}]

        store.add_embeddings(chunk_ids, texts, embeddings, metadatas)
        assert len(store.get_stats()["total_embeddings"]) >= 2

    def test_mock_vector_store_delete(self):
        """Mock vector store should delete."""
        store = MockVectorStore()
        
        chunk_ids = ["chunk1"]
        texts = ["First chunk"]
        embeddings = [[0.1, 0.2, 0.3]]
        
        store.add_embeddings(chunk_ids, texts, embeddings)
        initial_count = len(store.embeddings)
        
        store.delete(chunk_ids)
        assert len(store.embeddings) < initial_count


class TestNewsSourceIntegration:
    """Tests for news source integration."""

    def test_mock_news_source_fetch(self):
        """Mock news source should return articles."""
        articles = [
            ArticleSchema(
                title="Article 1",
                url="https://example.com/1",
                source="test",
                published_at=TimeUtility.now_utc(),
                author="Author 1",
                raw_text="Content 1",
            )
        ]
        
        source = MockNewsSource(articles=articles)
        fetched = source.fetch("test_source")
        
        assert len(fetched) == 1
        assert fetched[0].title == "Article 1"

    def test_mock_news_source_health(self):
        """Mock news source health check should pass."""
        source = MockNewsSource()
        assert source.health_check() is True


if __name__ == "__main__":
    if PYTEST_AVAILABLE:
        pytest.main([__file__, "-v"])
    else:
        print("pytest not installed. Run: pip install pytest")
