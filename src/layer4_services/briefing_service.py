"""Briefing service for daily news aggregation."""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from src.layer1_settings import settings, logger
from src.layer4_services.user_memory import UserMemory
from src.utils import TimeUtility


class BriefingService:
    """Generates daily briefings personalized to user interests."""

    def __init__(
        self,
        retrieval_service,
        llm_service,
        user_memory: Optional[UserMemory] = None,
    ):
        """
        Initialize briefing service.

        Args:
            retrieval_service: RetrievalService for finding articles
            llm_service: LLMService for synthesis
            user_memory: User memory for personalization
        """
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service
        self.user_memory = user_memory or UserMemory()

    def generate_briefing(
        self,
        date: Optional[date] = None,
        time_window_hours: int = 24,
        max_articles: int = 10,
    ) -> Dict[str, Any]:
        """
        Generate daily briefing.

        Args:
            date: Date of briefing (default: today)
            time_window_hours: Hours to look back for articles
            max_articles: Max articles to include

        Returns:
            Briefing dict with text, citations, confidence
        """
        if date is None:
            date = datetime.now().date()

        logger.info(f"Generating briefing for {date}")

        try:
            # Get user's top topics
            topics = self.user_memory.get_topic_interests(top_n=5)

            if not topics:
                # Fallback: use default broad topics
                topics = [
                    ("business", 0.8),
                    ("technology", 0.7),
                    ("science", 0.6),
                ]

            # Retrieve articles for each topic
            all_articles = []
            for topic, weight in topics:
                articles = self.retrieval_service.retrieve(
                    query=f"recent {topic} news",
                    k=max_articles // len(topics),
                    time_window_days=time_window_hours // 24,
                )

                # Boost score by topic weight
                for article in articles:
                    article["topic_weight"] = weight
                    article["final_score"] = article.get("similarity", 0) * weight

                all_articles.extend(articles)

            # Deduplicate by source
            unique_articles = {}
            for article in all_articles:
                key = f"{article.get('source')}_{article.get('chunk_id')}"
                if key not in unique_articles or article["final_score"] > unique_articles[key]["final_score"]:
                    unique_articles[key] = article

            # Sort by score and limit
            articles = sorted(
                unique_articles.values(),
                key=lambda x: x.get("final_score", 0),
                reverse=True,
            )[:max_articles]

            if not articles:
                return {
                    "briefing_text": "No articles found for today.",
                    "citations": [],
                    "articles_used": 0,
                    "grounding_pass": False,
                    "confidence_score": 0.0,
                }

            # Synthesize briefing
            briefing_text = self._synthesize_briefing(articles, topics)

            # Extract citations
            citations = self.llm_service.extract_citations(
                answer=briefing_text,
                retrieved_chunks=articles,
            )

            return {
                "date": str(date),
                "briefing_text": briefing_text,
                "citations": citations,
                "articles_used": len(articles),
                "topics_covered": [t[0] for t in topics],
                "grounding_pass": len(citations) >= len(articles) * 0.5,  # At least 50% cited
                "confidence_score": sum(a.get("similarity", 0) for a in articles) / len(articles) if articles else 0,
            }

        except Exception as e:
            logger.error(f"Briefing generation failed: {e}")
            return {
                "error": str(e),
                "briefing_text": "",
                "citations": [],
                "grounding_pass": False,
            }

    def _synthesize_briefing(self, articles: List[Dict], topics: List[tuple]) -> str:
        """
        Synthesize articles into briefing narrative.

        Args:
            articles: Top articles
            topics: User topics

        Returns:
            Briefing narrative
        """
        article_summaries = "\n\n".join([
            f"**{article.get('source', 'Unknown')}**: {article.get('text', '')[:300]}"
            for article in articles[:5]
        ])

        prompt = f"""Create a concise daily news briefing based on these articles:

{article_summaries}

User interests: {', '.join([t[0] for t in topics])}

Write a 2-3 paragraph briefing that connects these stories to the user's interests."""

        briefing = self.llm_service.generate(
            prompt=prompt,
            context="You are a news briefing writer. Create engaging, concise summaries.",
            max_tokens=400,
            temperature=0.8,
        )

        return briefing


class BriefingScheduler:
    """Manages scheduled briefing generation."""

    def __init__(self, briefing_service: BriefingService):
        """Initialize scheduler."""
        self.briefing_service = briefing_service
        self.scheduled_jobs = {}

    def schedule_daily(self, hour: int = 7, minute: int = 0) -> str:
        """
        Schedule daily briefing generation.

        Args:
            hour: Hour of day (0-23)
            minute: Minute (0-59)

        Returns:
            Job ID
        """
        try:
            from apscheduler.schedulers.background import BackgroundScheduler

            if not hasattr(self, '_scheduler'):
                self._scheduler = BackgroundScheduler()
                self._scheduler.start()
                logger.info("APScheduler started")

            job_id = f"briefing_daily_{hour}_{minute}"

            # Schedule job
            self._scheduler.add_job(
                self.briefing_service.generate_briefing,
                "cron",
                hour=hour,
                minute=minute,
                id=job_id,
                replace_existing=True,
            )

            self.scheduled_jobs[job_id] = {
                "hour": hour,
                "minute": minute,
                "active": True,
            }

            logger.info(f"Scheduled briefing for {hour}:{minute:02d} daily")
            return job_id

        except ImportError:
            logger.error("APScheduler not installed")
            return ""
        except Exception as e:
            logger.error(f"Failed to schedule briefing: {e}")
            return ""

    def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        if hasattr(self, '_scheduler'):
            self._scheduler.shutdown()
            logger.info("Scheduler stopped")
