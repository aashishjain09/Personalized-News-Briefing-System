"""Vector store port definition (adapter pattern)."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Result from vector similarity search."""

    chunk_id: str
    text: str
    similarity: float  # 0-1, where 1 is perfect match
    metadata: Dict[str, Any]


class VectorStorePort(ABC):
    """Abstract interface for vector stores (enables Chroma ↔ Pinecone swaps)."""

    @abstractmethod
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
            embeddings: Embedding vectors
            metadatas: Optional metadata for each chunk
        """
        pass

    @abstractmethod
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
            k: Number of results
            where: Optional metadata filter

        Returns:
            List of search results sorted by relevance
        """
        pass

    @abstractmethod
    def delete(self, chunk_ids: List[str]) -> None:
        """Delete embeddings by chunk ID."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if vector store is healthy."""
        pass
