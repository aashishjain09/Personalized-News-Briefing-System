"""Rate limiting with token bucket algorithm."""

import time
from typing import Dict, Optional
from collections import defaultdict
from src.layer1_settings import logger


class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Max tokens in bucket
            refill_rate: Tokens per second to add
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if consumption successful, False if rate limit exceeded
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False

    def _refill(self) -> None:
        """Refill bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class RateLimiter:
    """Rate limiter using token bucket algorithm."""

    def __init__(
        self,
        global_rps: int = 100,  # Requests per second
        per_user_rps: int = 10,
        per_user_daily_limit: int = 1000,
    ):
        """
        Initialize rate limiter.

        Args:
            global_rps: Global requests per second limit
            per_user_rps: Per-user requests per second limit
            per_user_daily_limit: Per-user daily request limit
        """
        self.global_bucket = TokenBucket(capacity=global_rps, refill_rate=global_rps)
        self.per_user_rps = per_user_rps
        self.per_user_daily_limit = per_user_daily_limit
        
        # Track per-user buckets and daily limits
        self.user_buckets: Dict[str, TokenBucket] = {}
        self.user_daily_counts: Dict[str, Dict] = defaultdict(
            lambda: {"count": 0, "reset_at": time.time() + 86400}
        )

    def check_rate_limit(
        self,
        user_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Check if request is allowed.

        Args:
            user_id: Optional user identifier

        Returns:
            Tuple of (allowed, reason)
        """
        # Check global limit
        if not self.global_bucket.consume(1):
            logger.warning("Global rate limit exceeded")
            return False, "Global rate limit exceeded. Max 100 requests/sec"

        # Check per-user limits
        if user_id:
            # Check per-second limit
            if user_id not in self.user_buckets:
                self.user_buckets[user_id] = TokenBucket(
                    capacity=self.per_user_rps,
                    refill_rate=self.per_user_rps,
                )

            if not self.user_buckets[user_id].consume(1):
                logger.warning(f"Per-user rate limit exceeded for {user_id}")
                return (
                    False,
                    f"Per-user rate limit exceeded. Max {self.per_user_rps} requests/sec",
                )

            # Check daily limit
            now = time.time()
            daily_info = self.user_daily_counts[user_id]

            # Reset daily counter if period expired
            if now > daily_info["reset_at"]:
                daily_info["count"] = 0
                daily_info["reset_at"] = now + 86400

            if daily_info["count"] >= self.per_user_daily_limit:
                logger.warning(f"Daily limit exceeded for {user_id}")
                return (
                    False,
                    f"Daily limit exceeded. Max {self.per_user_daily_limit} requests/day",
                )

            daily_info["count"] += 1

        return True, ""

    def get_stats(self, user_id: Optional[str] = None) -> dict:
        """Get rate limit statistics."""
        stats = {
            "global_tokens": self.global_bucket.tokens,
            "global_capacity": self.global_bucket.capacity,
        }

        if user_id and user_id in self.user_buckets:
            bucket = self.user_buckets[user_id]
            daily_info = self.user_daily_counts[user_id]
            stats.update({
                "user_tokens": bucket.tokens,
                "user_capacity": bucket.capacity,
                "daily_count": daily_info["count"],
                "daily_limit": self.per_user_daily_limit,
            })

        return stats
