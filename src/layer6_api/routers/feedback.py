"""Layer 6: API - Feedback endpoint."""

from fastapi import APIRouter, HTTPException
from uuid import uuid4
import time

from src.layer1_settings import get_logger, get_request_id
from src.layer5_orchestration.state import FeedbackRequest, FeedbackResponse
from src.layer4_services import UserMemory
from src.layer2_persistence import DatabaseManager, FeedbackEvent

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["feedback"])

# Global UserMemory instance (initialized on demand)
_user_memory: UserMemory | None = None


def _get_user_memory() -> UserMemory:
    """Get or initialize global UserMemory instance."""
    global _user_memory
    if _user_memory is None:
        _user_memory = UserMemory()
    return _user_memory


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """
    Submit user feedback on article.
    
    Flow:
    1. Validate feedback signal (like | dislike | save | skip)
    2. Save to FeedbackEvent table
    3. Update UserMemory personalization scores
    
    Args:
        request: FeedbackRequest with signal, article_id, optional comment
    
    Returns:
        FeedbackResponse with status
    """
    request_id = get_request_id()
    start_time = time.time()
    
    try:
        if request.signal not in ["like", "dislike", "save", "skip"]:
            raise ValueError(f"Invalid signal: {request.signal}")
        
        logger.info(
            f"Feedback received: {request.signal} for article {request.article_id}",
            extra={"request_id": request_id, "signal": request.signal, "article_id": request.article_id}
        )
        
        # Store feedback event in database
        db_manager = DatabaseManager()
        with db_manager.session_scope() as session:
            feedback_event = FeedbackEvent(
                user_id=request.user_id,
                article_id=request.article_id,
                signal=request.signal,
                comment=request.comment,
            )
            session.add(feedback_event)
            session.commit()
            logger.debug(f"Feedback event saved: {feedback_event.id}")
        
        # Update UserMemory with feedback signal
        # Map feedback signals to topics (inferred from article context)
        # In production, would extract topics from article metadata
        user_memory = _get_user_memory()
        inferred_topics = [request.topic] if hasattr(request, 'topic') and request.topic else []
        
        user_memory.update_from_feedback(
            signal=request.signal,
            topics=inferred_topics,
        )
        logger.debug(f"UserMemory updated for signal: {request.signal}")
        
        elapsed = time.time() - start_time
        logger.info(
            f"Feedback processed successfully in {elapsed:.2f}s",
            extra={"request_id": request_id, "signal": request.signal}
        )
        
        response = FeedbackResponse(
            status="success",
            message="Feedback recorded and personalization updated",
            request_id=request_id,
        )
        
        return response
    
    except ValueError as e:
        logger.error(f"Feedback validation failed: {str(e)}", extra={"request_id": request_id})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Feedback submission failed: {str(e)}", extra={"request_id": request_id}, exc_info=True)
        raise HTTPException(status_code=500, detail="Feedback submission failed")
