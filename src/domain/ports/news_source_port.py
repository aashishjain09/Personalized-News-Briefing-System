"""News source port definition (adapter pattern)."""

from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    """Article schema from news sources."""

    title: str
    url: str
    source: str
    published_at: datetime
    author: str
    raw_text: str


class NewsSourcePort(ABC):
    """Abstract interface for news sources (enables NewsAPI ↔ RSS swaps)."""

    @abstractmethod
    def fetch(self, source_name: str) -> List[Article]:
        """
        Fetch articles from news source.

        Args:
            source_name: Source identifier (e.g., 'bbc_news', 'hacker_news')

        Returns:
            List of Article objects
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if news source is accessible."""
        pass
