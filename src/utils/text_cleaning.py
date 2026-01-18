"""Text processing utilities for article cleaning and chunking."""

import re
from typing import List
from src.layer1_settings import logger


class TextCleaner:
    """Cleans raw HTML/text to produce normalized content."""

    # Patterns for HTML/markup removal
    HTML_PATTERN = re.compile(r'<[^>]+>')
    MULTIPLE_SPACES = re.compile(r' {2,}')
    MULTIPLE_NEWLINES = re.compile(r'\n{3,}')
    CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

    @staticmethod
    def clean(raw_text: str) -> str:
        """
        Clean raw HTML/text into normalized plain text.

        Steps:
        1. Remove HTML tags
        2. Decode HTML entities
        3. Remove control characters
        4. Normalize whitespace
        5. Strip leading/trailing whitespace

        Args:
            raw_text: Raw HTML or text content

        Returns:
            Cleaned plain text
        """
        if not raw_text:
            return ""

        # Remove HTML tags
        text = TextCleaner.HTML_PATTERN.sub(' ', raw_text)

        # Decode HTML entities
        try:
            from html import unescape
            text = unescape(text)
        except Exception as e:
            logger.warning(f"Failed to decode HTML entities: {e}")

        # Remove control characters
        text = TextCleaner.CONTROL_CHARS.sub('', text)

        # Normalize multiple spaces to single space
        text = TextCleaner.MULTIPLE_SPACES.sub(' ', text)

        # Normalize multiple newlines to double newline (preserve paragraph breaks)
        text = TextCleaner.MULTIPLE_NEWLINES.sub('\n\n', text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text


class TextChunker:
    """Splits text into overlapping chunks for embedding."""

    def __init__(self, chunk_size: int = 1000, overlap: float = 0.2):
        """
        Initialize chunker.

        Args:
            chunk_size: Target chunk size in characters (800-1200 recommended)
            overlap: Overlap fraction, e.g. 0.2 = 20% overlap (0.0-0.5 recommended)

        Raises:
            ValueError: If chunk_size < 100 or overlap not in [0, 0.5]
        """
        if chunk_size < 100:
            raise ValueError(f"chunk_size must be >= 100, got {chunk_size}")
        if not (0 <= overlap <= 0.5):
            raise ValueError(f"overlap must be in [0, 0.5], got {overlap}")

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.overlap_size = int(chunk_size * overlap)

    def chunk(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Strategy:
        1. Split by paragraph (double newline) first to preserve semantic boundaries
        2. If any paragraph is larger than chunk_size, split by sentences
        3. Then group sentences into chunks, respecting overlap

        Args:
            text: Cleaned text to chunk

        Returns:
            List of text chunks with overlap
        """
        if not text:
            return []

        # Split by paragraph
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            # If adding paragraph would exceed chunk_size, finalize current chunk
            if current_chunk and len(current_chunk) + len(para) + 1 > self.chunk_size:
                chunks.append(current_chunk)
                # Create overlap with end of previous chunk
                current_chunk = current_chunk[-self.overlap_size:] if self.overlap_size > 0 else ""

            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += '\n\n' + para
            else:
                current_chunk = para

        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks


def clean_and_chunk(raw_text: str, chunk_size: int = 1000, overlap: float = 0.2) -> List[str]:
    """
    Convenience function to clean text and chunk in one call.

    Args:
        raw_text: Raw HTML/text content
        chunk_size: Target chunk size in characters
        overlap: Overlap fraction

    Returns:
        List of cleaned, chunked text segments
    """
    cleaned = TextCleaner.clean(raw_text)
    chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk(cleaned)
