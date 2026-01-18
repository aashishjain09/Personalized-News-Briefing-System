"""Layer 6: API - Briefing endpoint."""

from fastapi import APIRouter, HTTPException
from datetime import datetime, date
from uuid import uuid4
import time

from src.layer1_settings import get_logger, get_request_id
from src.layer5_orchestration.state import BriefingRequest, BriefingResponse
from src.layer5_orchestration import BriefingAgent
from src.layer2_persistence import DatabaseManager

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["briefing"])

# Global agent instance (initialized on demand)
_agent: BriefingAgent | None = None


def _get_briefing_agent() -> BriefingAgent:
    """Get or initialize global BriefingAgent instance."""
    global _agent
    if _agent is None:
        from src.layer4_services import (
            BriefingService,
            EmailService,
            UserMemory,
            RetrievalService,
            LLMService,
            EmbedderService,
        )
        from src.adapters.vectorstores.chroma_store import ChromaVectorStore
        
        # Initialize low-level services
        vector_store = ChromaVectorStore()
        embedder = EmbedderService()
        
        # Initialize high-level services
        retrieval_svc = RetrievalService(vector_store=vector_store, embedder=embedder)
        llm_svc = LLMService()
        user_mem = UserMemory()
        
        # Initialize specialized services
        briefing_svc = BriefingService(
            retrieval_service=retrieval_svc,
            llm_service=llm_svc,
            user_memory=user_mem,
        )
        email_svc = EmailService()
        
        # Create agent
        _agent = BriefingAgent(
            briefing_service=briefing_svc,
            email_service=email_svc,
            user_memory=user_mem,
        )
    return _agent


@router.post("/briefing/generate", response_model=BriefingResponse)
async def generate_briefing(request: BriefingRequest) -> BriefingResponse:
    """
    Generate daily briefing for specified date.
    
    Flow:
    1. Load user profile (implicit)
    2. Retrieve articles by user topics
    3. Synthesize briefing
    4. Verify grounding
    5. Send email (if enabled)
    6. Return briefing + email status
    
    Args:
        request: BriefingRequest with optional date and time_window_hours
    
    Returns:
        BriefingResponse with briefing text, citations, email status
    """
    request_id = get_request_id()
    start_time = time.time()
    
    try:
        # Default to today
        briefing_date = datetime.fromisoformat(request.date).date() if request.date else datetime.utcnow().date()
        
        logger.info(
            f"Briefing generation requested for {briefing_date}",
            extra={"request_id": request_id, "date": str(briefing_date), "user_id": request.user_id}
        )
        
        # Get agent instance
        agent = _get_briefing_agent()
        
        # Execute briefing workflow
        result = agent.run(user_id=request.user_id, date=briefing_date)
        
        # Extract results
        briefing_text = result.get("briefing_text", "")
        citations = result.get("citations", [])
        email_sent = result.get("email_sent", False)
        grounding_pass = result.get("grounding_pass", True)
        confidence = result.get("confidence", 0.95)
        
        elapsed = time.time() - start_time
        logger.info(
            f"Briefing generated successfully in {elapsed:.2f}s",
            extra={"request_id": request_id, "email_sent": email_sent, "citations_count": len(citations)}
        )
        
        response = BriefingResponse(
            briefing=briefing_text,
            citations=citations,
            grounding_pass=grounding_pass,
            confidence=confidence,
            email_sent=email_sent,
            request_id=request_id,
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Briefing generation failed: {str(e)}", extra={"request_id": request_id}, exc_info=True)
        raise HTTPException(status_code=500, detail="Briefing generation failed")
