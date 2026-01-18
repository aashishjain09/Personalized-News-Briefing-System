"""Content hashing utilities for deduplication."""

import hashlib
from typing import Optional
from src.layer1_settings import logger


class ContentHasher:
    """Generates deterministic hashes for content deduplication."""

    ALGORITHM = "sha256"

    @staticmethod
    def hash_url(url: str) -> str:
        """
        Generate hash from URL for duplicate detection.

        Used to identify if we've already seen this exact URL.

        Args:
            url: Article URL

        Returns:
            SHA256 hex digest of normalized URL
        """
        if not url:
            raise ValueError("URL cannot be empty")

        # Normalize URL: lowercase, strip whitespace
        normalized = url.strip().lower()

        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @staticmethod
    def hash_content(text: str) -> str:
        """
        Generate hash from content for duplicate detection.

        Used to identify if we've already ingested semantically duplicate content
        (same article from different URLs, or copy-pasted articles).

        Args:
            text: Article content (should be cleaned text)

        Returns:
            SHA256 hex digest of normalized content
        """
        if not text:
            raise ValueError("Content cannot be empty")

        # Normalize content: lowercase, strip excess whitespace
        normalized = ' '.join(text.split()).lower()

        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @staticmethod
    def hash_url_and_content(url: str, content: str) -> tuple[str, str]:
        """
        Generate both URL and content hashes efficiently.

        Args:
            url: Article URL
            content: Article content

        Returns:
            Tuple of (url_hash, content_hash)
        """
        return (
            ContentHasher.hash_url(url),
            ContentHasher.hash_content(content),
        )

    @staticmethod
    def is_duplicate_url(url_hash: str, existing_url_hashes: set[str]) -> bool:
        """
        Check if URL hash exists in set of seen URLs.

        Args:
            url_hash: Hash to check
            existing_url_hashes: Set of previously seen URL hashes

        Returns:
            True if duplicate found
        """
        return url_hash in existing_url_hashes

    @staticmethod
    def is_duplicate_content(content_hash: str, existing_content_hashes: set[str]) -> bool:
        """
        Check if content hash exists in set of seen content.

        Args:
            content_hash: Hash to check
            existing_content_hashes: Set of previously seen content hashes

        Returns:
            True if duplicate found
        """
        return content_hash in existing_content_hashes
