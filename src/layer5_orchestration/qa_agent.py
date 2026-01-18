"""Q&A LangGraph agent with 8-node workflow."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from src.layer1_settings import settings, logger
from src.layer5_orchestration import AgentState
from src.layer4_services import IngestionService
from src.utils import TimeUtility


class QAAgent:
    """LangGraph Q&A agent orchestrating the Q&A workflow."""

    def __init__(
        self,
        retrieval_service,
        llm_service,
        grounding_checker,
        sanitizer,
        injection_detector,
    ):
        """Initialize Q&A agent."""
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service
        self.grounding_checker = grounding_checker
        self.sanitizer = sanitizer
        self.injection_detector = injection_detector

    def load_profile(self, state: AgentState) -> AgentState:
        """Node 1: Load user profile if available."""
        # In personal-use context, profile is simplified
        state.profile_topics = []
        state.profile_blocked = []
        state.preferences = {"context_window": 7}  # Default 7 days
        logger.debug("Profile loaded")
        return state

    def sanitize_input(self, state: AgentState) -> AgentState:
        """Node 2: Sanitize and validate input query."""
        # Sanitize
        state.query = self.sanitizer.sanitize(state.query)

        # Check injection
        is_injection, patterns = self.injection_detector.detect(state.query)
        if is_injection:
            logger.warning(f"Injection detected: {patterns}")
            state.errors.append(f"Query contains suspicious patterns")
            state.schema_valid = False
            return state

        # Validate length
        if not self.sanitizer.validate_query_length(state.query):
            state.errors.append("Query too long or too short")
            state.schema_valid = False
            return state

        logger.debug(f"Query sanitized: {state.query[:100]}")
        return state

    def decide_retrieval(self, state: AgentState) -> AgentState:
        """Node 3: Decide if retrieval is needed."""
        # For now, always retrieve (could add heuristics)
        state.retrieval_needed = True

        # Set dynamic K based on query complexity
        words = len(state.query.split())
        if words < 5:
            state.retrieval_k = 3  # Simple question
        elif words < 20:
            state.retrieval_k = 5  # Normal question
        else:
            state.retrieval_k = 10  # Complex question

        logger.debug(f"Retrieval needed: True, k={state.retrieval_k}")
        return state

    def retrieve_chunks(self, state: AgentState) -> AgentState:
        """Node 4: Retrieve relevant chunks."""
        if not state.retrieval_needed:
            state.retrieved_chunks = []
            return state

        try:
            # Get time window from preferences
            time_window = state.preferences.get("context_window", 7)

            # Retrieve
            results = self.retrieval_service.retrieve(
                query=state.query,
                k=state.retrieval_k,
                time_window_days=time_window,
            )

            state.retrieved_chunks = results
            logger.info(f"Retrieved {len(results)} chunks")
            return state

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            state.errors.append(f"Retrieval failed: {str(e)}")
            state.retrieved_chunks = []
            return state

    def synthesize_answer(self, state: AgentState) -> AgentState:
        """Node 5: Generate answer using LLM."""
        if not state.retrieved_chunks and state.retrieval_needed:
            state.draft_output = "I couldn't find relevant information to answer your question."
            return state

        try:
            # Build prompt with context
            context_text = "\n\n".join([
                f"Document {i+1} ({chunk.get('source', 'unknown')}):\n{chunk.get('text', '')}"
                for i, chunk in enumerate(state.retrieved_chunks[:5])  # Top 5
            ])

            prompt = f"""Based on the following documents, answer the user's question.

User Question: {state.query}

Documents:
{context_text}

Answer:"""

            # Generate answer
            answer = self.llm_service.generate(
                prompt=prompt,
                context="You are a helpful assistant answering questions based on provided documents.",
                max_tokens=500,
                temperature=0.7,
            )

            state.draft_output = answer
            state.tokens_out = self.llm_service.count_tokens(answer)
            logger.info(f"Answer synthesized: {len(answer)} chars")
            return state

        except Exception as e:
            logger.error(f"Answer synthesis failed: {e}")
            state.errors.append(f"Synthesis failed: {str(e)}")
            state.draft_output = ""
            return state

    def validate_schema(self, state: AgentState) -> AgentState:
        """Node 6: Validate answer schema."""
        if not state.draft_output:
            state.schema_valid = False
            state.errors.append("Empty answer")
            return state

        # Check basic schema validity
        checks = {
            "has_content": len(state.draft_output) > 10,
            "reasonable_length": 50 < len(state.draft_output) < 5000,
            "no_error_markers": "error" not in state.draft_output.lower(),
        }

        state.schema_valid = all(checks.values())

        if not state.schema_valid:
            state.errors.append(f"Schema validation failed: {checks}")

        logger.debug(f"Schema valid: {state.schema_valid}")
        return state

    def ground_answer(self, state: AgentState) -> AgentState:
        """Node 7: Check grounding."""
        if not state.draft_output or not state.retrieved_chunks:
            state.grounding_pass = False
            state.confidence_score = 0.0
            return state

        try:
            # Extract chunk texts
            chunk_texts = [chunk.get("text", "") for chunk in state.retrieved_chunks]

            # Check grounding
            grounding_result = self.grounding_checker.ground(
                answer=state.draft_output,
                retrieved_chunks=chunk_texts,
                use_llm_judge=True,
            )

            state.grounding_pass = grounding_result.get("grounded", False)
            state.confidence_score = grounding_result.get("confidence_score", 0.0)

            # Extract citations
            state.citations = self.llm_service.extract_citations(
                answer=state.draft_output,
                retrieved_chunks=state.retrieved_chunks,
            )

            logger.info(f"Grounding check: {state.grounding_pass}, confidence: {state.confidence_score}")
            return state

        except Exception as e:
            logger.error(f"Grounding check failed: {e}")
            state.grounding_pass = False
            state.confidence_score = 0.0
            state.errors.append(f"Grounding check failed: {str(e)}")
            return state

    def update_memory(self, state: AgentState) -> AgentState:
        """Node 8: Update user memory with feedback."""
        # In personal-use context, this would update user preferences
        # For now, just mark as complete
        state.created_at = TimeUtility.now_utc()
        logger.debug("Memory update complete")
        return state

    def run(self, query: str, user_id: str = "default") -> Dict[str, Any]:
        """
        Run Q&A agent end-to-end.

        Args:
            query: User question
            user_id: User identifier

        Returns:
            Final agent state as dict
        """
        # Initialize state
        state = AgentState(
            request_id=str(TimeUtility.now_utc()),
            query=query,
            user_id=user_id,
            mode="qa",
            profile_topics=[],
            profile_blocked=[],
            preferences={},
            retrieval_needed=False,
            retrieved_chunks=[],
            retrieval_k=5,
            draft_output="",
            citations=[],
            schema_valid=False,
            grounding_pass=False,
            confidence_score=0.0,
            tokens_in=self.llm_service.count_tokens(query) if self.llm_service else 0,
            tokens_out=0,
            token_budget_remaining=settings.llm_settings.token_budget,
            errors=[],
            fallback_model_used=False,
            created_at=TimeUtility.now_utc(),
        )

        # Run nodes in sequence
        logger.info(f"Starting Q&A agent for query: {query[:100]}")

        state = self.load_profile(state)
        if state.errors:
            return state.dict()

        state = self.sanitize_input(state)
        if state.errors:
            return state.dict()

        state = self.decide_retrieval(state)
        state = self.retrieve_chunks(state)
        state = self.synthesize_answer(state)
        state = self.validate_schema(state)
        state = self.ground_answer(state)
        state = self.update_memory(state)

        logger.info(f"Q&A agent complete. Grounded: {state.grounding_pass}, Confidence: {state.confidence_score}")
        return state.dict()
