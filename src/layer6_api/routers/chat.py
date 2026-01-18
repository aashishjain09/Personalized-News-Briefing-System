"""Layer 6: API - Chat endpoint (Q&A)."""

from fastapi import APIRouter, HTTPException
from uuid import uuid4
import time

from src.layer1_settings import logger, get_request_id
from src.layer5_orchestration.state import ChatRequest, ChatResponse
from src.layer4_services import RetrievalService, LLMService, EmbedderService
from src.layer3_safety import InputSanitizer, PromptInjectionDetector, GroundingChecker
from src.layer5_orchestration import QAAgent
from src.adapters.vectorstores.chroma_store import ChromaVectorStore
from src.layer2_persistence.database import DatabaseManager

logger_instance = logger
router = APIRouter(prefix="/api/v1", tags=["chat"])

# Global agent instance
_agent = None


def get_agent():
    """Get or create Q&A agent."""
    global _agent
    if _agent is None:
        try:
            embedder = EmbedderService()
            vector_store = ChromaVectorStore()
            
            retrieval_service = RetrievalService(vector_store, embedder)
            llm_service = LLMService()
            sanitizer = InputSanitizer()
            injection_detector = PromptInjectionDetector()
            grounding_checker = GroundingChecker(llm_service)

            _agent = QAAgent(
                retrieval_service=retrieval_service,
                llm_service=llm_service,
                grounding_checker=grounding_checker,
                sanitizer=sanitizer,
                injection_detector=injection_detector,
            )
            logger_instance.info("Q&A agent initialized")
        except Exception as e:
            logger_instance.error(f"Failed to initialize Q&A agent: {e}")
            raise

    return _agent


@router.post("/chat/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest) -> ChatResponse:
    """Answer question using RAG."""
    request_id = get_request_id()
    start_time = time.time()
    
    try:
        logger_instance.info(f"Chat query: {request.query[:100]}")
        
        agent = get_agent()
        result = agent.run(query=request.query, user_id="default")
        
        response = ChatResponse(
            answer=result.get("draft_output", ""),
            citations=result.get("citations", []),
            used_articles=list(set([
                chunk.get("source", "unknown")
                for chunk in result.get("retrieved_chunks", [])
            ])),
            grounding_pass=result.get("grounding_pass", False),
            confidence=result.get("confidence_score", 0.0),
            request_id=request_id,
            latency_ms=int((time.time() - start_time) * 1000),
        )
        
        return response
    
    except Exception as e:
        logger_instance.error(f"Chat query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
