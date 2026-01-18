"""RSS feed parser implementation."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import feedparser
import requests
from src.layer1_settings import settings, logger
from src.domain.ports.news_source_port import NewsSourcePort, Article
from src.utils import TimeUtility


class RSSClient(NewsSourcePort):
    """Fetches and parses RSS feeds."""

    def __init__(self, timeout_seconds: int = 30):
        """
        Initialize RSS client.

        Args:
            timeout_seconds: HTTP request timeout
        """
        self.timeout = timeout_seconds

    def fetch(self, source_name: str) -> List[Article]:
        """
        Fetch articles from RSS feed.

        Args:
            source_name: Name of RSS source from configs/sources.yaml

        Returns:
            List of Article objects

        Raises:
            ValueError: If source not configured
            Exception: If feed fetch/parse fails
        """
        if source_name not in settings.ingestion_settings.rss_sources:
            raise ValueError(
                f"RSS source '{source_name}' not found in configuration. "
                f"Available: {list(settings.ingestion_settings.rss_sources.keys())}"
            )

        feed_url = settings.ingestion_settings.rss_sources[source_name]

        try:
            logger.info(f"Fetching RSS feed from {source_name}: {feed_url}")

            # Fetch feed with timeout
            response = requests.get(feed_url, timeout=self.timeout)
            response.raise_for_status()

            # Parse feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"Feed parsing warning for {source_name}: {feed.bozo_exception}")

            # Convert entries to Article objects
            articles = []
            for entry in feed.entries[:settings.ingestion_settings.max_articles_per_feed]:
                try:
                    article = self._entry_to_article(entry, source_name)
                    articles.append(article)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse RSS entry from {source_name}: {e}, skipping"
                    )
                    continue

            logger.info(
                f"Fetched {len(articles)} articles from {source_name} "
                f"(total entries: {len(feed.entries)})"
            )
            return articles

        except requests.RequestException as e:
            logger.error(f"Failed to fetch RSS feed {source_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching RSS {source_name}: {e}")
            raise

    def _entry_to_article(self, entry: Dict[str, Any], source_name: str) -> Article:
        """
        Convert RSS entry to Article object.

        Args:
            entry: feedparser entry
            source_name: Name of RSS source

        Returns:
            Article object

        Raises:
            ValueError: If required fields missing
        """
        # Extract required fields
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()

        if not title:
            raise ValueError("Entry missing title")
        if not url:
            raise ValueError("Entry missing link")

        # Extract published date
        published_at = None
        if "published_parsed" in entry and entry["published_parsed"]:
            try:
                published_at = datetime(*entry["published_parsed"][:6])
                # Make timezone-aware (assume UTC)
                published_at = published_at.replace(tzinfo=TimeUtility.UTC)
            except Exception as e:
                logger.warning(f"Failed to parse published date: {e}")

        if not published_at:
            published_at = TimeUtility.now_utc()

        # Extract content (prefer summary, fallback to title)
        content = entry.get("summary", "").strip() or title

        # Extract author
        author = entry.get("author", "").strip() or "Unknown"

        return Article(
            title=title,
            url=url,
            source=source_name,
            published_at=published_at,
            author=author,
            raw_text=content,
        )

    def health_check(self) -> bool:
        """
        Check if at least one RSS feed is accessible.

        Returns:
            True if at least one feed is reachable
        """
        if not settings.ingestion_settings.rss_sources:
            logger.warning("No RSS sources configured")
            return False

        # Try first feed
        first_source = next(iter(settings.ingestion_settings.rss_sources.keys()))
        first_url = settings.ingestion_settings.rss_sources[first_source]

        try:
            response = requests.head(first_url, timeout=5, allow_redirects=True)
            is_healthy = response.status_code < 400
            if is_healthy:
                logger.info(f"RSS health check passed: {first_source}")
            else:
                logger.warning(f"RSS health check failed {first_source}: HTTP {response.status_code}")
            return is_healthy
        except Exception as e:
            logger.error(f"RSS health check failed: {e}")
            return False
