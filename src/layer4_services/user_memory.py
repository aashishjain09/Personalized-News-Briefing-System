"""User memory for implicit personalization tracking."""

from typing import Dict, List, Set, Optional
from datetime import datetime
from src.layer1_settings import logger
from src.utils import TimeUtility


class UserMemory:
    """Tracks user preferences implicitly from feedback."""

    def __init__(self, user_id: str = "default"):
        """
        Initialize user memory.

        Args:
            user_id: User identifier
        """
        self.user_id = user_id
        self.explicit_topics: Set[str] = set()
        self.blocked_topics: Set[str] = set()
        self.inferred_topics: Dict[str, float] = {}  # topic -> confidence (0-1)
        self.topic_weights: Dict[str, float] = {}  # topic -> importance (0-1)
        self.source_preferences: Dict[str, float] = {}  # source -> preference (0-1)
        self.last_interaction: Optional[datetime] = None
        self.interaction_count = 0

    def update_from_feedback(
        self,
        signal: str,
        topics: List[str],
        source: Optional[str] = None,
    ) -> None:
        """
        Update memory from user feedback.

        Args:
            signal: 'like', 'dislike', 'save', 'skip'
            topics: Topics in article
            source: Source name
        """
        self.last_interaction = TimeUtility.now_utc()
        self.interaction_count += 1

        # Update topic weights based on signal
        for topic in topics:
            current_weight = self.inferred_topics.get(topic, 0.5)

            if signal == "like":
                new_weight = min(1.0, current_weight + 0.15)
            elif signal == "dislike":
                new_weight = max(0.0, current_weight - 0.15)
            elif signal == "save":
                new_weight = min(1.0, current_weight + 0.1)
            elif signal == "skip":
                new_weight = max(0.0, current_weight - 0.05)
            else:
                new_weight = current_weight

            self.inferred_topics[topic] = new_weight

        # Update source preference
        if source:
            current_pref = self.source_preferences.get(source, 0.5)
            if signal == "like":
                new_pref = min(1.0, current_pref + 0.1)
            elif signal == "dislike":
                new_pref = max(0.0, current_pref - 0.1)
            else:
                new_pref = current_pref
            self.source_preferences[source] = new_pref

        logger.debug(f"Updated memory for {self.user_id}: {signal} on {topics}")

    def add_explicit_topic(self, topic: str) -> None:
        """Add explicitly selected topic."""
        self.explicit_topics.add(topic.lower())
        self.inferred_topics[topic.lower()] = 1.0  # Full confidence
        logger.debug(f"Added explicit topic: {topic}")

    def block_topic(self, topic: str) -> None:
        """Block topic from recommendations."""
        self.blocked_topics.add(topic.lower())
        self.inferred_topics[topic.lower()] = 0.0  # Zero confidence
        logger.debug(f"Blocked topic: {topic}")

    def get_topic_interests(self, top_n: int = 5) -> List[tuple[str, float]]:
        """
        Get top N topics by interest level.

        Returns:
            List of (topic, weight) tuples sorted by weight
        """
        # Filter out blocked topics
        interests = [
            (topic, weight)
            for topic, weight in self.inferred_topics.items()
            if topic not in self.blocked_topics and weight > 0.3
        ]

        # Sort by weight descending
        interests.sort(key=lambda x: x[1], reverse=True)
        return interests[:top_n]

    def get_source_preferences(self) -> List[tuple[str, float]]:
        """Get source preferences sorted by preference."""
        prefs = sorted(
            self.source_preferences.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return prefs

    def to_dict(self) -> Dict:
        """Convert to dict for persistence."""
        return {
            "user_id": self.user_id,
            "explicit_topics": list(self.explicit_topics),
            "blocked_topics": list(self.blocked_topics),
            "inferred_topics": self.inferred_topics,
            "source_preferences": self.source_preferences,
            "interaction_count": self.interaction_count,
            "last_interaction": self.last_interaction.isoformat() if self.last_interaction else None,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UserMemory":
        """Recreate from dict."""
        memory = cls(user_id=data.get("user_id", "default"))
        memory.explicit_topics = set(data.get("explicit_topics", []))
        memory.blocked_topics = set(data.get("blocked_topics", []))
        memory.inferred_topics = data.get("inferred_topics", {})
        memory.source_preferences = data.get("source_preferences", {})
        memory.interaction_count = data.get("interaction_count", 0)
        
        if data.get("last_interaction"):
            memory.last_interaction = TimeUtility.parse_timestamp(data["last_interaction"])
        
        return memory
