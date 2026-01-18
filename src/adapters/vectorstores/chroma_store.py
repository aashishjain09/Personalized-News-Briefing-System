"""Chroma vector store adapter implementation."""

from typing import List, Dict, Any, Optional
import os
import chromadb
from chromadb.config import Settings as ChromaSettings
from src.layer1_settings import settings, logger
from src.domain.ports.vector_store_port import VectorStorePort, SearchResult


class ChromaVectorStore(VectorStorePort):
    """Chroma-based vector store implementation."""

    def __init__(self, persist_dir: Optional[str] = None):
        """
        Initialize Chroma vector store.

        Args:
            persist_dir: Directory for persistent storage (default: from config)
        """
        self.persist_dir = persist_dir or settings.vector_store_settings.chroma_persist_dir
        
        # Ensure directory exists
        os.makedirs(self.persist_dir, exist_ok=True)

        # Configure Chroma with persistence
        chroma_settings = ChromaSettings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=self.persist_dir,
            anonymized_telemetry=False,
        )

        try:
            self.client = chromadb.Client(chroma_settings)
            logger.info(f"Initialized Chroma client with persist_dir={self.persist_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize Chroma client: {e}")
            raise

    def add_embeddings(
        self,
        chunk_ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Add embeddings to vector store.

        Args:
            chunk_ids: Unique chunk identifiers
            texts: Text content of chunks
            embeddings: Embedding vectors (should be same length as texts)
            metadatas: Optional metadata dicts for each chunk

        Raises:
            ValueError: If arrays have mismatched lengths
            Exception: If Chroma operation fails
        """
        if not (len(chunk_ids) == len(texts) == len(embeddings)):
            raise ValueError(
                f"Length mismatch: ids={len(chunk_ids)}, texts={len(texts)}, embeddings={len(embeddings)}"
            )

        if metadatas is None:
            metadatas = [{} for _ in chunk_ids]

        if len(metadatas) != len(chunk_ids):
            raise ValueError(
                f"Metadata length {len(metadatas)} doesn't match ids length {len(chunk_ids)}"
            )

        try:
            collection = self.client.get_or_create_collection(
                name=settings.vector_store_settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

            logger.info(f"Added {len(chunk_ids)} embeddings to Chroma")
        except Exception as e:
            logger.error(f"Failed to add embeddings to Chroma: {e}")
            raise

    def search(
        self,
        embedding: List[float],
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for similar embeddings.

        Args:
            embedding: Query embedding vector
            k: Number of results to return
            where: Optional Chroma where filter (metadata filtering)

        Returns:
            List of SearchResult objects sorted by relevance
        """
        try:
            collection = self.client.get_collection(
                name=settings.vector_store_settings.chroma_collection_name
            )

            results = collection.query(
                query_embeddings=[embedding],
                n_results=k,
                where=where,
                include=["embeddings", "documents", "metadatas", "distances"],
            )

            # Convert Chroma results to SearchResult objects
            search_results = []
            if results and results["ids"] and len(results["ids"]) > 0:
                for i, chunk_id in enumerate(results["ids"][0]):
                    # Chroma returns distances (lower is better for cosine)
                    # Convert to similarity score: similarity = 1 - distance
                    distance = results["distances"][0][i] if results["distances"] else 0
                    similarity = 1 - distance

                    search_results.append(
                        SearchResult(
                            chunk_id=chunk_id,
                            text=results["documents"][0][i],
                            similarity=similarity,
                            metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        )
                    )

            logger.debug(f"Search returned {len(search_results)} results for k={k}")
            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete(self, chunk_ids: List[str]) -> None:
        """
        Delete embeddings by chunk ID.

        Args:
            chunk_ids: IDs of chunks to delete

        Raises:
            Exception: If deletion fails
        """
        try:
            collection = self.client.get_collection(
                name=settings.vector_store_settings.chroma_collection_name
            )

            collection.delete(ids=chunk_ids)
            logger.info(f"Deleted {len(chunk_ids)} embeddings from Chroma")

        except Exception as e:
            logger.error(f"Failed to delete embeddings: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get vector store statistics.

        Returns:
            Dictionary with store metadata and stats
        """
        try:
            collection = self.client.get_collection(
                name=settings.vector_store_settings.chroma_collection_name
            )

            count = collection.count()
            return {
                "collection_name": settings.vector_store_settings.chroma_collection_name,
                "total_chunks": count,
                "persist_dir": self.persist_dir,
                "storage_type": "duckdb+parquet",
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "error": str(e),
                "persist_dir": self.persist_dir,
            }

    def health_check(self) -> bool:
        """
        Check if vector store is healthy and accessible.

        Returns:
            True if vector store is operational
        """
        try:
            stats = self.get_stats()
            return "error" not in stats
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            return False
