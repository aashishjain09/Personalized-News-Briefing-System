"""Briefing LangGraph agent with 5-node workflow."""

from typing import Dict, Any
from src.layer1_settings import logger
from src.layer5_orchestration import BriefingState
from src.utils import TimeUtility


class BriefingAgent:
    """LangGraph agent for daily briefing generation."""

    def __init__(
        self,
        briefing_service,
        email_service,
        user_memory,
    ):
        """Initialize briefing agent."""
        self.briefing_service = briefing_service
        self.email_service = email_service
        self.user_memory = user_memory

    def load_profile(self, state: BriefingState) -> BriefingState:
        """Node 1: Load user profile and preferences."""
        state.profile_topics = list(dict(self.user_memory.get_topic_interests()))
        state.profile_blocked = list(self.user_memory.blocked_topics)
        state.preferences = {
            "briefing_length": "medium",
            "max_articles": 10,
            "time_window_hours": 24,
        }
        logger.debug("Profile loaded for briefing")
        return state

    def select_topics(self, state: BriefingState) -> BriefingState:
        """Node 2: Select topics for today's briefing."""
        # Get top topics
        topics = self.user_memory.get_topic_interests(top_n=5)
        state.topic_articles = {topic: [] for topic, _ in topics}
        logger.debug(f"Selected {len(topics)} topics for briefing")
        return state

    def retrieve_articles(self, state: BriefingState) -> BriefingState:
        """Node 3: Retrieve articles for selected topics."""
        try:
            time_window = state.preferences.get("time_window_hours", 24)
            max_articles = state.preferences.get("max_articles", 10)

            for topic in state.topic_articles.keys():
                articles = self.briefing_service.retrieval_service.retrieve(
                    query=f"recent {topic} news",
                    k=max_articles // len(state.topic_articles),
                    time_window_days=time_window // 24,
                )
                state.topic_articles[topic] = articles

            total_articles = sum(len(a) for a in state.topic_articles.values())
            logger.info(f"Retrieved {total_articles} articles for briefing")
            return state

        except Exception as e:
            logger.error(f"Article retrieval failed: {e}")
            state.errors.append(str(e))
            return state

    def synthesize_briefing(self, state: BriefingState) -> BriefingState:
        """Node 4: Synthesize articles into briefing narrative."""
        try:
            # Collect all articles
            all_articles = []
            for articles in state.topic_articles.values():
                all_articles.extend(articles)

            if not all_articles:
                state.briefing_text = "No articles found for today's briefing."
                return state

            # Synthesize using briefing service
            briefing_result = self.briefing_service.generate_briefing(
                date=state.date,
                time_window_hours=state.preferences.get("time_window_hours", 24),
                max_articles=state.preferences.get("max_articles", 10),
            )

            state.briefing_text = briefing_result.get("briefing_text", "")
            state.citations = briefing_result.get("citations", [])
            state.grounding_pass = briefing_result.get("grounding_pass", False)
            state.confidence_score = briefing_result.get("confidence_score", 0.0)

            if state.briefing_text:
                logger.info(f"Briefing synthesized: {len(state.briefing_text)} chars")
            return state

        except Exception as e:
            logger.error(f"Briefing synthesis failed: {e}")
            state.errors.append(str(e))
            return state

    def send_email(self, state: BriefingState) -> BriefingState:
        """Node 5: Send briefing via email."""
        if not state.briefing_text:
            state.email_sent = False
            logger.warning("No briefing text to send")
            return state

        try:
            # Get recipient email from settings
            recipient_email = "user@example.com"  # Would come from user profile in production

            # Send email
            success = self.email_service.send_briefing(
                to_email=recipient_email,
                subject=f"Daily News Brief - {state.date}",
                briefing_text=state.briefing_text,
                citations=state.citations,
            )

            if success:
                state.email_sent = True
                state.email_sent_at = TimeUtility.now_utc()
                logger.info(f"Briefing email sent to {recipient_email}")
            else:
                state.email_sent = False
                state.errors.append("Email send failed")

            return state

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            state.email_sent = False
            state.errors.append(str(e))
            return state

    def run(
        self,
        user_id: str = "default",
        date=None,
    ) -> Dict[str, Any]:
        """
        Run briefing agent end-to-end.

        Args:
            user_id: User identifier
            date: Briefing date

        Returns:
            Final agent state as dict
        """
        # Initialize state
        state = BriefingState(
            request_id=str(TimeUtility.now_utc()),
            query="",
            user_id=user_id,
            mode="briefing",
            date=date or TimeUtility.now_utc().date(),
            profile_topics=[],
            profile_blocked=[],
            preferences={},
            topic_articles={},
            briefing_text="",
            citations=[],
            grounding_pass=False,
            confidence_score=0.0,
            tokens_in=0,
            tokens_out=0,
            token_budget_remaining=8000,
            errors=[],
            fallback_model_used=False,
            email_sent=False,
            email_sent_at=None,
            created_at=TimeUtility.now_utc(),
        )

        logger.info(f"Starting briefing agent for {state.date}")

        state = self.load_profile(state)
        state = self.select_topics(state)
        state = self.retrieve_articles(state)
        state = self.synthesize_briefing(state)
        state = self.send_email(state)

        logger.info(f"Briefing complete. Email sent: {state.email_sent}")
        return state.dict()
