"""Embedding service with caching for efficient embedding generation."""

from typing import List, Dict, Optional, Any
from datetime import datetime
from src.layer1_settings import settings, logger
from src.utils import ContentHasher, TimeUtility


class EmbedderService:
    """
    Manages embedding generation with content-hash based caching.
    
    Avoids duplicate API calls for same content by tracking content_hash → embedding.
    This reduces OpenAI API costs significantly during incremental ingestion.
    """

    def __init__(self):
        """Initialize embedder with empty cache."""
        # Content hash -> (embedding, timestamp)
        self._cache: Dict[str, tuple[List[float], datetime]] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def get_embedding(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Get embedding for text, using cache if available.

        Args:
            text: Text to embed
            use_cache: Whether to use cache (default: True)

        Returns:
            Embedding vector (list of floats)

        Raises:
            ValueError: If text is empty
            Exception: If OpenAI API call fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty for embedding")

        # Generate content hash
        content_hash = ContentHasher.hash_content(text)

        # Check cache
        if use_cache and content_hash in self._cache:
            embedding, cached_at = self._cache[content_hash]
            self.cache_hits += 1
            logger.debug(
                f"Cache hit for embedding (hash={content_hash[:8]}..., "
                f"age={TimeUtility.now_utc() - cached_at})"
            )
            return embedding

        # Cache miss - call OpenAI
        self.cache_misses += 1
        logger.debug(f"Cache miss for embedding (hash={content_hash[:8]}...)")

        try:
            embedding = self._call_openai_embedding(text)
            
            # Store in cache
            self._cache[content_hash] = (embedding, TimeUtility.now_utc())
            
            logger.info(
                f"Generated embedding for {len(text)} chars "
                f"(hash={content_hash[:8]}..., cache_size={len(self._cache)})"
            )
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def get_embeddings_batch(
        self, texts: List[str], use_cache: bool = True
    ) -> List[List[float]]:
        """
        Get embeddings for multiple texts efficiently.

        Strategy:
        1. Check cache for each text
        2. Batch remaining uncached texts and call OpenAI once
        3. Return in original order

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache

        Returns:
            List of embeddings in same order as texts
        """
        if not texts:
            return []

        # Check cache and identify uncached texts
        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices: List[int] = []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                logger.warning(f"Skipping empty text at index {i}")
                embeddings[i] = []
                continue

            content_hash = ContentHasher.hash_content(text)

            if use_cache and content_hash in self._cache:
                embedding, _ = self._cache[content_hash]
                embeddings[i] = embedding
                self.cache_hits += 1
            else:
                uncached_indices.append(i)
                self.cache_misses += 1

        # Batch embed uncached texts
        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            logger.debug(
                f"Batch embedding {len(uncached_texts)} texts "
                f"({len(uncached_indices)} cache misses out of {len(texts)})"
            )

            try:
                uncached_embeddings = self._call_openai_embeddings_batch(uncached_texts)

                # Store in cache and place in results
                for idx, text_idx in enumerate(uncached_indices):
                    embedding = uncached_embeddings[idx]
                    content_hash = ContentHasher.hash_content(texts[text_idx])
                    self._cache[content_hash] = (embedding, TimeUtility.now_utc())
                    embeddings[text_idx] = embedding

            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                raise

        return [e for e in embeddings if e is not None]

    def _call_openai_embedding(self, text: str) -> List[float]:
        """
        Call OpenAI embedding API for single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            ImportError: If openai not installed
            Exception: If API call fails
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required for embeddings")

        client = OpenAI(api_key=settings.llm_settings.openai_api_key)

        try:
            response = client.embeddings.create(
                model=settings.embeddings_settings.model,
                input=text,
            )

            if not response.data:
                raise ValueError("No embedding in OpenAI response")

            return response.data[0].embedding

        except Exception as e:
            logger.error(f"OpenAI embedding API error: {e}")
            raise

    def _call_openai_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Call OpenAI embedding API for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors in same order as texts

        Raises:
            ImportError: If openai not installed
            Exception: If API call fails
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required for embeddings")

        if not texts:
            return []

        client = OpenAI(api_key=settings.llm_settings.openai_api_key)

        try:
            response = client.embeddings.create(
                model=settings.embeddings_settings.model,
                input=texts,
            )

            if len(response.data) != len(texts):
                logger.warning(
                    f"Expected {len(texts)} embeddings, got {len(response.data)}"
                )

            # Sort by index to maintain order
            embeddings_dict = {item.index: item.embedding for item in response.data}
            return [embeddings_dict.get(i, []) for i in range(len(texts))]

        except Exception as e:
            logger.error(f"OpenAI batch embedding API error: {e}")
            raise

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get embedding cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (
            (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        )

        return {
            "cache_size": len(self._cache),
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "total_requests": total_requests,
            "hit_rate_percent": hit_rate,
        }

    def clear_cache(self, older_than_hours: Optional[int] = None) -> int:
        """
        Clear cache, optionally only entries older than specified hours.

        Args:
            older_than_hours: Only clear entries older than N hours (default: clear all)

        Returns:
            Number of entries removed
        """
        if older_than_hours is None:
            removed = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared entire embedding cache ({removed} entries)")
            return removed

        now = TimeUtility.now_utc()
        cutoff_time = TimeUtility.hours_ago(older_than_hours)
        removed = 0

        for content_hash in list(self._cache.keys()):
            _, cached_at = self._cache[content_hash]
            if cached_at < cutoff_time:
                del self._cache[content_hash]
                removed += 1

        logger.info(
            f"Cleared {removed} embedding cache entries older than {older_than_hours}h"
        )
        return removed
