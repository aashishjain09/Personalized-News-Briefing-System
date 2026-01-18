"""Ingestion service for orchestrating RSS → chunk → embed → store pipeline."""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from uuid import uuid4
from src.layer1_settings import settings, logger
from src.utils import TextCleaner, TextChunker, ContentHasher, TimeUtility, clean_and_chunk
from src.layer2_persistence.models import Article as ArticleORM, Chunk as ChunkORM
from src.layer2_persistence.database import DatabaseManager
from src.domain.ports.news_source_port import NewsSourcePort, Article as ArticleSchema
from src.domain.ports.vector_store_port import VectorStorePort
from src.layer4_services.embedder_service import EmbedderService


class IngestionService:
    """
    Orchestrates the complete ingestion pipeline:
    1. Fetch articles from news source (RSS/NewsAPI)
    2. Clean and chunk text
    3. Generate embeddings (with caching)
    4. Detect duplicates (by URL + content hash)
    5. Store in SQL database + vector store
    
    All operations use retry logic and comprehensive error handling.
    """

    def __init__(
        self,
        news_source: NewsSourcePort,
        vector_store: VectorStorePort,
        db_manager: DatabaseManager,
        embedder: Optional[EmbedderService] = None,
    ):
        """
        Initialize ingestion service.

        Args:
            news_source: News source adapter (RSS, NewsAPI, etc.)
            vector_store: Vector store adapter (Chroma, Pinecone, etc.)
            db_manager: Database manager
            embedder: Embedder service (creates one if not provided)
        """
        self.news_source = news_source
        self.vector_store = vector_store
        self.db_manager = db_manager
        self.embedder = embedder or EmbedderService()

        # Ingestion statistics
        self.stats = {
            "total_fetched": 0,
            "total_ingested": 0,
            "duplicates_skipped": 0,
            "chunks_created": 0,
            "embeddings_generated": 0,
            "errors": 0,
        }

    def ingest_source(self, source_name: str) -> Dict[str, Any]:
        """
        Ingest all articles from a news source.

        Pipeline:
        1. Fetch articles from source
        2. For each article: clean, chunk, embed, deduplicate, store
        3. Return statistics

        Args:
            source_name: News source identifier (e.g., 'bbc_news')

        Returns:
            Statistics dictionary with ingestion results
        """
        logger.info(f"Starting ingestion from source: {source_name}")

        try:
            # Fetch articles
            articles = self.news_source.fetch(source_name)
            self.stats["total_fetched"] = len(articles)
            logger.info(f"Fetched {len(articles)} articles from {source_name}")

            if not articles:
                logger.warning(f"No articles fetched from {source_name}")
                return self.stats

            # Load existing URL and content hashes for deduplication
            url_hashes, content_hashes = self._load_existing_hashes()

            # Ingest each article
            for article in articles:
                try:
                    self._ingest_article(
                        article, source_name, url_hashes, content_hashes
                    )
                except Exception as e:
                    logger.error(f"Failed to ingest article '{article.title}': {e}")
                    self.stats["errors"] += 1
                    continue

            logger.info(
                f"Ingestion complete for {source_name}. "
                f"Stats: {self.stats}"
            )
            return self.stats

        except Exception as e:
            logger.error(f"Ingestion pipeline failed for {source_name}: {e}")
            self.stats["errors"] += 1
            return self.stats

    def _ingest_article(
        self,
        article: ArticleSchema,
        source_name: str,
        url_hashes: set[str],
        content_hashes: set[str],
    ) -> None:
        """
        Ingest a single article through the pipeline.

        Args:
            article: Article from news source
            source_name: News source identifier
            url_hashes: Set of existing URL hashes for deduplication
            content_hashes: Set of existing content hashes for deduplication

        Raises:
            Exception: If any pipeline step fails
        """
        # Check URL duplicate
        url_hash = ContentHasher.hash_url(article.url)
        if ContentHasher.is_duplicate_url(url_hash, url_hashes):
            logger.debug(f"Skipping duplicate URL: {article.url}")
            self.stats["duplicates_skipped"] += 1
            return

        # Clean text
        cleaned_text = TextCleaner.clean(article.raw_text)
        if not cleaned_text:
            logger.warning(f"No content after cleaning: {article.title}")
            return

        # Check content duplicate
        content_hash = ContentHasher.hash_content(cleaned_text)
        if ContentHasher.is_duplicate_content(content_hash, content_hashes):
            logger.debug(f"Skipping duplicate content: {article.title}")
            self.stats["duplicates_skipped"] += 1
            return

        # Create article in SQL database
        article_id = str(uuid4())
        article_orm = ArticleORM(
            article_id=article_id,
            url=article.url,
            title=article.title,
            source=article.source,
            published_at=article.published_at,
            author=article.author,
            raw_text=article.raw_text,
            clean_text=cleaned_text,
            content_hash=content_hash,
            metadata={
                "url_hash": url_hash,
                "ingestion_source": source_name,
            },
        )

        # Chunk text
        chunks = clean_and_chunk(
            cleaned_text,
            chunk_size=settings.ingestion_settings.chunk_size,
            overlap=settings.ingestion_settings.chunk_overlap,
        )

        if not chunks:
            logger.warning(f"No chunks created for article: {article.title}")
            return

        logger.debug(f"Created {len(chunks)} chunks from article: {article.title}")

        # Generate embeddings for all chunks
        embeddings = self.embedder.get_embeddings_batch(chunks, use_cache=True)
        self.stats["embeddings_generated"] += len(embeddings)

        # Create chunk records and add to vector store
        chunk_ids = []
        chunk_orms = []

        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{article_id}_{i}"
            chunk_ids.append(chunk_id)

            chunk_orm = ChunkORM(
                chunk_id=chunk_id,
                article_id=article_id,
                chunk_text=chunk_text,
                embedding_id=chunk_id,  # Use same ID for vector store
                metadata={
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "source": article.source,
                },
            )
            chunk_orms.append(chunk_orm)

        # Store in vector store
        self.vector_store.add_embeddings(
            chunk_ids=chunk_ids,
            texts=chunks,
            embeddings=embeddings,
            metadatas=[c.metadata for c in chunk_orms],
        )

        # Store in SQL database (transaction)
        with self.db_manager.session_scope() as session:
            try:
                session.add(article_orm)
                session.add_all(chunk_orms)
                session.commit()
                self.stats["total_ingested"] += 1
                self.stats["chunks_created"] += len(chunk_orms)
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to commit article to database: {e}")
                raise

        # Update deduplication sets
        url_hashes.add(url_hash)
        content_hashes.add(content_hash)

        logger.info(
            f"Ingested article: {article.title} "
            f"({len(chunks)} chunks, {len(embeddings)} embeddings)"
        )

    def _load_existing_hashes(self) -> Tuple[set[str], set[str]]:
        """
        Load existing URL and content hashes from database for deduplication.

        Returns:
            Tuple of (url_hashes, content_hashes) sets
        """
        try:
            with self.db_manager.session_scope() as session:
                articles = session.query(ArticleORM).all()

                url_hashes = {
                    ContentHasher.hash_url(a.url) for a in articles
                }
                content_hashes = {a.content_hash for a in articles if a.content_hash}

                logger.info(
                    f"Loaded {len(url_hashes)} URL hashes and "
                    f"{len(content_hashes)} content hashes from database"
                )
                return url_hashes, content_hashes

        except Exception as e:
            logger.warning(f"Failed to load existing hashes: {e}, proceeding with empty sets")
            return set(), set()

    def ingest_all_sources(self) -> Dict[str, Dict[str, Any]]:
        """
        Ingest all configured news sources.

        Returns:
            Dictionary mapping source names to ingestion statistics
        """
        if not settings.ingestion_settings.rss_sources:
            logger.warning("No RSS sources configured")
            return {}

        results = {}
        for source_name in settings.ingestion_settings.rss_sources.keys():
            logger.info(f"Ingesting source: {source_name}")
            try:
                stats = self.ingest_source(source_name)
                results[source_name] = stats
            except Exception as e:
                logger.error(f"Failed to ingest source {source_name}: {e}")
                results[source_name] = {"error": str(e)}

        return results

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cumulative ingestion statistics.

        Returns:
            Statistics dictionary
        """
        return self.stats.copy()

    def get_embedder_stats(self) -> Dict[str, Any]:
        """
        Get embedding cache statistics.

        Returns:
            Embedder cache stats
        """
        return self.embedder.get_cache_stats()
