"""Two-stage grounding verification for RAG outputs."""

import re
from typing import List, Dict, Any, Tuple, Optional
from src.layer1_settings import settings, logger


class GroundingChecker:
    """
    Two-stage grounding verification:
    1. Stage A (Fast): Rule-based extraction checking
    2. Stage B (Slow): LLM-as-judge confidence scoring
    """

    def __init__(self, llm_service=None):
        """
        Initialize grounding checker.

        Args:
            llm_service: LLMService for Stage B (optional)
        """
        self.llm_service = llm_service
        self.min_confidence_threshold = 0.7

    def ground(
        self,
        answer: str,
        retrieved_chunks: List[str],
        use_llm_judge: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform two-stage grounding check.

        Args:
            answer: Generated answer
            retrieved_chunks: Retrieved context chunks
            use_llm_judge: Whether to use Stage B (LLM judge)

        Returns:
            Grounding result with confidence score and evidence
        """
        # Stage A: Rule-based extraction
        stage_a = self._stage_a_rule_based(answer, retrieved_chunks)

        # Stage B: LLM judge (optional)
        stage_b = None
        if use_llm_judge and self.llm_service:
            stage_b = self._stage_b_llm_judge(answer, retrieved_chunks, stage_a)

        # Combine results
        final_confidence = stage_a["confidence"]
        if stage_b:
            final_confidence = 0.6 * stage_a["confidence"] + 0.4 * stage_b["confidence"]

        return {
            "grounded": final_confidence >= self.min_confidence_threshold,
            "confidence_score": final_confidence,
            "stage_a": stage_a,
            "stage_b": stage_b,
            "evidence_count": len(stage_a.get("evidence", [])),
        }

    def _stage_a_rule_based(
        self,
        answer: str,
        retrieved_chunks: List[str],
    ) -> Dict[str, Any]:
        """
        Stage A: Rule-based grounding check.

        Looks for:
        1. Chunks referenced in answer
        2. Content overlap with chunks
        3. Factual claims with evidence
        4. Absence of unsupported statements

        Args:
            answer: Generated answer
            retrieved_chunks: Retrieved chunks

        Returns:
            Stage A result with confidence and evidence
        """
        evidence = []
        answer_sentences = self._split_sentences(answer)

        # Check each sentence for grounding
        grounded_sentences = 0
        for sentence in answer_sentences:
            if self._is_grounded_in_chunks(sentence, retrieved_chunks):
                grounded_sentences += 1
                evidence.append(sentence)

        # Calculate confidence based on grounding ratio
        if len(answer_sentences) == 0:
            confidence = 0.0
        else:
            confidence = min(1.0, grounded_sentences / len(answer_sentences))

        # Reduce confidence if many factual claims present
        factual_claims = len(re.findall(r"\b(is|are|was|were|found|showed|proved)\b", answer))
        if factual_claims > len(answer_sentences) * 0.5:  # Many claims
            confidence *= 0.8  # Reduce confidence

        return {
            "confidence": confidence,
            "evidence": evidence,
            "grounded_sentences": grounded_sentences,
            "total_sentences": len(answer_sentences),
            "checks": {
                "content_overlap": self._check_content_overlap(answer, retrieved_chunks),
                "fact_density": factual_claims / max(1, len(answer_sentences)),
            },
        }

    def _stage_b_llm_judge(
        self,
        answer: str,
        retrieved_chunks: List[str],
        stage_a_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Stage B: LLM-as-judge grounding assessment.

        Uses LLM to evaluate:
        1. Consistency between answer and chunks
        2. Presence of hallucinations
        3. Citation accuracy
        4. Overall faithfulness

        Args:
            answer: Generated answer
            retrieved_chunks: Retrieved chunks
            stage_a_result: Stage A result for context

        Returns:
            Stage B result with LLM confidence
        """
        if not self.llm_service:
            return None

        try:
            prompt = self._build_llm_judge_prompt(answer, retrieved_chunks)

            response = self.llm_service.generate(
                prompt=prompt,
                context="You are an expert at evaluating answer grounding and consistency.",
                max_tokens=200,
                temperature=0.1,
            )

            # Parse LLM response
            confidence = self._extract_confidence_score(response)

            logger.debug(f"LLM judge confidence: {confidence}")

            return {
                "confidence": confidence,
                "reasoning": response,
                "checks": {
                    "consistency": confidence > 0.8,
                    "hallucination_free": confidence > 0.7,
                },
            }

        except Exception as e:
            logger.error(f"LLM judge failed: {e}, skipping Stage B")
            return None

    def _is_grounded_in_chunks(self, sentence: str, chunks: List[str]) -> bool:
        """Check if sentence is grounded in any chunk."""
        sentence_lower = sentence.lower()

        for chunk in chunks:
            chunk_lower = chunk.lower()

            # Check for direct substring match
            if sentence_lower in chunk_lower:
                return True

            # Check for significant overlap (>50% of words)
            sentence_words = set(sentence.split())
            chunk_words = set(chunk.split())
            overlap = len(sentence_words & chunk_words) / max(1, len(sentence_words))

            if overlap > 0.5:
                return True

        return False

    def _check_content_overlap(self, answer: str, chunks: List[str]) -> float:
        """Calculate overall content overlap between answer and chunks."""
        answer_words = set(answer.lower().split())
        chunk_words = set()

        for chunk in chunks:
            chunk_words.update(chunk.lower().split())

        if not answer_words:
            return 0.0

        overlap = len(answer_words & chunk_words) / len(answer_words)
        return min(1.0, overlap)

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting on period, question mark, exclamation
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _build_llm_judge_prompt(self, answer: str, chunks: List[str]) -> str:
        """Build prompt for LLM judge."""
        chunks_str = "\n\n".join([f"Chunk {i+1}: {c[:500]}" for i, c in enumerate(chunks)])

        return f"""
Evaluate the grounding of this answer against the provided context chunks.

ANSWER:
{answer}

CONTEXT CHUNKS:
{chunks_str}

Questions to answer:
1. Is the answer consistent with the context?
2. Does the answer contain hallucinations or unsupported claims?
3. Are citations accurate?
4. Overall faithfulness score (0-1)?

Provide a brief assessment and a single confidence score (0-1).
"""

    def _extract_confidence_score(self, response: str) -> float:
        """Extract confidence score from LLM response."""
        # Look for patterns like "0.8" or "80%"
        patterns = [
            r'(?:score|confidence|faithfulness)[:\s]+([0-1]\.\d+)',
            r'(\d+)\s*%',
            r'(?:score|confidence)[:\s]+([0-1])',
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                # Convert percentage to 0-1 if needed
                if score > 1:
                    score = score / 100
                return min(1.0, max(0.0, score))

        # Default to moderate confidence if can't extract
        return 0.6
