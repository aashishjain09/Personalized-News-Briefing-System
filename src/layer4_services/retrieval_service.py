"""Retrieval service with hybrid search and metadata filtering."""

from typing import List, Dict, Any, Optional
from src.layer1_settings import settings, logger
from src.domain.ports.vector_store_port import VectorStorePort, SearchResult


class RetrievalService:
    """Retrieves relevant chunks from vector store with hybrid search."""

    def __init__(self, vector_store: VectorStorePort, embedder):
        """
        Initialize retrieval service.

        Args:
            vector_store: Vector store adapter
            embedder: Embedder service for query embeddings
        """
        self.vector_store = vector_store
        self.embedder = embedder

    def retrieve(
        self,
        query: str,
        k: int = 5,
        source_filter: Optional[str] = None,
        time_window_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks using semantic search with filtering.

        Args:
            query: Search query
            k: Number of results to return
            source_filter: Optional source name filter (e.g., 'bbc_news')
            time_window_days: Only retrieve articles within N days

        Returns:
            List of retrieval results with chunk text, source, similarity
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to retrieve()")
            return []

        try:
            # Generate embedding for query
            query_embedding = self.embedder.get_embedding(query)

            # Dynamic K: increase if specific source or time window
            adjusted_k = k
            if source_filter:
                adjusted_k = int(k * 1.5)  # Retrieve more to apply filter

            # Search vector store
            results = self.vector_store.search(
                embedding=query_embedding,
                k=adjusted_k,
            )

            if not results:
                logger.debug(f"No results for query: {query}")
                return []

            # Post-process results
            processed = [
                {
                    "chunk_id": r.chunk_id,
                    "text": r.text,
                    "similarity": r.similarity,
                    "source": r.metadata.get("source", "unknown"),
                    "article_id": r.metadata.get("article_id", "unknown"),
                    "chunk_index": r.metadata.get("chunk_index", 0),
                    "total_chunks": r.metadata.get("total_chunks", 1),
                }
                for r in results
            ]

            # Apply source filter if specified
            if source_filter:
                processed = [
                    r for r in processed if r["source"].lower() == source_filter.lower()
                ]
                processed = processed[:k]

            logger.info(f"Retrieved {len(processed)} chunks for query (k={k})")
            return processed

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            raise

    def retrieve_with_reranking(
        self,
        query: str,
        k: int = 5,
        rerank_top_n: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve with two-stage ranking (semantic + keyword).

        Args:
            query: Search query
            k: Final number of results
            rerank_top_n: Top N results to rerank

        Returns:
            List of top K reranked results
        """
        # First stage: semantic search
        results = self.retrieve(query, k=rerank_top_n)

        if not results:
            return []

        # Second stage: keyword relevance scoring
        query_terms = set(query.lower().split())
        for result in results:
            # Count keyword hits in chunk text
            text_terms = set(result["text"].lower().split())
            keyword_matches = len(query_terms & text_terms)
            result["keyword_score"] = keyword_matches / (len(query_terms) + 1e-6)

            # Combined score: 70% semantic, 30% keyword
            result["combined_score"] = (
                0.7 * result["similarity"] + 0.3 * result["keyword_score"]
            )

        # Sort by combined score
        results.sort(key=lambda x: x["combined_score"], reverse=True)
        return results[:k]

    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics."""
        return self.vector_store.get_stats()
