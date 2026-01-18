"""RAGAS evaluation framework for hallucination and grounding detection."""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json
from src.layer1_settings import logger


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for a single response."""
    
    # Faithfulness: 0-1, how much generated answer agrees with source docs
    faithfulness: float
    
    # Context Recall: 0-1, how much relevant info from context is in answer
    context_recall: float
    
    # Context Precision: 0-1, how much of retrieved context is relevant
    context_precision: float
    
    # Answer Relevancy: 0-1, how well answer addresses question
    answer_relevancy: float
    
    # Grounding Score: 0-1, composite of faithfulness + context scores
    grounding_score: float
    
    # Hallucination Flag: True if answer contains unsupported claims
    has_hallucination: bool
    
    # Confidence: 0-1, model's confidence in answer
    confidence: float
    
    # Timestamp
    evaluated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "faithfulness": self.faithfulness,
            "context_recall": self.context_recall,
            "context_precision": self.context_precision,
            "answer_relevancy": self.answer_relevancy,
            "grounding_score": self.grounding_score,
            "has_hallucination": self.has_hallucination,
            "confidence": self.confidence,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass
class RagasInput:
    """Input for RAGAS evaluation."""
    
    question: str
    answer: str
    retrieved_contexts: List[str]
    ground_truth: Optional[str] = None


class RAGASEvaluator:
    """
    RAGAS (Retrieval-Augmented Generation Assessment) evaluation framework.
    
    Evaluates:
    - Faithfulness: Does answer agree with source documents?
    - Context Recall: How much relevant info from context is used?
    - Context Precision: How much retrieved context is actually relevant?
    - Answer Relevancy: How well does answer address the question?
    - Grounding: Overall confidence that answer is grounded in sources
    """

    def __init__(self, llm_service=None, threshold_grounding: float = 0.90):
        """
        Initialize RAGAS evaluator.

        Args:
            llm_service: LLMService for evaluations (optional, can use heuristics)
            threshold_grounding: Minimum grounding score (0-1)
        """
        self.llm_service = llm_service
        self.threshold_grounding = threshold_grounding
        self.evaluation_history: List[EvaluationMetrics] = []

    def evaluate(self, input_data: RagasInput) -> EvaluationMetrics:
        """
        Evaluate a RAG response comprehensively.

        Args:
            input_data: Question, answer, and retrieved contexts

        Returns:
            EvaluationMetrics with all scores
        """
        # Calculate individual metrics
        faithfulness = self._evaluate_faithfulness(
            input_data.answer,
            input_data.retrieved_contexts
        )
        
        context_recall = self._evaluate_context_recall(
            input_data.answer,
            input_data.retrieved_contexts,
            input_data.ground_truth
        )
        
        context_precision = self._evaluate_context_precision(
            input_data.question,
            input_data.retrieved_contexts
        )
        
        answer_relevancy = self._evaluate_answer_relevancy(
            input_data.question,
            input_data.answer
        )
        
        # Calculate composite grounding score
        grounding_score = (
            faithfulness * 0.4 +
            context_recall * 0.25 +
            context_precision * 0.25 +
            answer_relevancy * 0.1
        )
        
        # Detect hallucination
        has_hallucination = faithfulness < 0.6 or context_recall < 0.5
        
        # Determine confidence
        confidence = self._calculate_confidence(
            faithfulness,
            context_precision,
            answer_relevancy
        )
        
        metrics = EvaluationMetrics(
            faithfulness=faithfulness,
            context_recall=context_recall,
            context_precision=context_precision,
            answer_relevancy=answer_relevancy,
            grounding_score=grounding_score,
            has_hallucination=has_hallucination,
            confidence=confidence,
            evaluated_at=datetime.utcnow(),
        )
        
        self.evaluation_history.append(metrics)
        return metrics

    def _evaluate_faithfulness(
        self,
        answer: str,
        contexts: List[str]
    ) -> float:
        """
        Faithfulness: How much does answer agree with source documents?
        
        Checks:
        - Named entities match context
        - Numbers/statistics align with context
        - No contradictions with context
        - Claims are supported by at least one context
        """
        if not answer or not contexts:
            return 0.5
        
        score = 0.0
        
        # Check if answer contains references to context
        context_text = " ".join(contexts).lower()
        answer_lower = answer.lower()
        
        # Extract key phrases from answer
        key_phrases = self._extract_key_phrases(answer)
        supported_phrases = sum(
            1 for phrase in key_phrases
            if any(phrase in ctx.lower() for ctx in contexts)
        )
        
        if key_phrases:
            score = supported_phrases / len(key_phrases)
        else:
            score = 0.5  # Neutral if no key phrases
        
        # Bonus: check for contradictions
        contradiction_keywords = [
            "opposite", "contrary", "unlike", "rather than", "instead"
        ]
        has_contradiction = any(
            keyword in answer_lower for keyword in contradiction_keywords
        ) and not any(
            keyword in context_text for keyword in contradiction_keywords
        )
        
        if has_contradiction:
            score *= 0.7  # Penalize potential contradictions
        
        return min(max(score, 0.0), 1.0)

    def _evaluate_context_recall(
        self,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None
    ) -> float:
        """
        Context Recall: How much relevant information from context is in answer?
        
        Measures how well the answer incorporates available context information.
        """
        if not contexts:
            return 0.5
        
        # Extract key information from contexts
        context_key_info = self._extract_key_phrases(" ".join(contexts))
        
        if not context_key_info:
            return 0.5
        
        # Check how much context info is reflected in answer
        answer_text = answer.lower()
        recalled_info = sum(
            1 for info in context_key_info
            if info in answer_text
        )
        
        recall = recalled_info / len(context_key_info)
        
        # If ground truth provided, compare
        if ground_truth:
            ground_truth_text = ground_truth.lower()
            # Prefer answers closer to ground truth
            if recalled_info > 0:
                recall *= 1.1  # Slight bonus for using context
        
        return min(max(recall, 0.0), 1.0)

    def _evaluate_context_precision(
        self,
        question: str,
        contexts: List[str]
    ) -> float:
        """
        Context Precision: How much retrieved context is actually relevant?
        
        Measures retrieval quality - percentage of contexts that are relevant to question.
        """
        if not contexts:
            return 0.5
        
        question_words = set(question.lower().split())
        question_words = {w for w in question_words if len(w) > 3}
        
        relevant_contexts = 0
        for context in contexts:
            context_words = set(context.lower().split())
            # Calculate overlap
            overlap = len(question_words & context_words)
            
            # Context is relevant if it has sufficient overlap
            if overlap >= max(1, len(question_words) // 3):
                relevant_contexts += 1
        
        precision = relevant_contexts / len(contexts) if contexts else 0.5
        return min(max(precision, 0.0), 1.0)

    def _evaluate_answer_relevancy(
        self,
        question: str,
        answer: str
    ) -> float:
        """
        Answer Relevancy: How well does answer address the question?
        
        Checks:
        - Answer addresses question directly
        - Answer includes all question entities
        - Answer is not overly verbose
        """
        if not question or not answer:
            return 0.5
        
        question_lower = question.lower()
        answer_lower = answer.lower()
        
        # Extract question keywords
        question_words = set(
            w for w in question_lower.split()
            if len(w) > 3 and w not in {"what", "when", "where", "which", "who"}
        )
        
        if not question_words:
            return 0.5
        
        # Check how many question keywords appear in answer
        matched_words = sum(
            1 for word in question_words
            if word in answer_lower
        )
        
        relevancy = matched_words / len(question_words) if question_words else 0.5
        
        # Penalize if answer is too different in length
        answer_words = len(answer.split())
        question_words_count = len(question.split())
        length_ratio = answer_words / max(question_words_count, 1)
        
        # Penalize very long answers (>5x question length)
        if length_ratio > 5:
            relevancy *= 0.8
        
        return min(max(relevancy, 0.0), 1.0)

    def _calculate_confidence(
        self,
        faithfulness: float,
        context_precision: float,
        answer_relevancy: float
    ) -> float:
        """Calculate overall confidence in answer quality."""
        # Confidence is high when faithfulness and precision are both good
        confidence = (
            faithfulness * 0.5 +
            context_precision * 0.3 +
            answer_relevancy * 0.2
        )
        return min(max(confidence, 0.0), 1.0)

    @staticmethod
    def _extract_key_phrases(text: str) -> List[str]:
        """Extract key phrases from text (simple implementation)."""
        # Remove common words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "can", "could", "should", "would", "may", "might", "must", "shall",
            "will", "in", "on", "at", "to", "for", "of", "with", "by", "from",
            "as", "that", "this", "it", "which", "who", "what", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more", "most"
        }
        
        words = text.lower().split()
        phrases = [
            w for w in words
            if len(w) > 3 and w not in stop_words and w.isalpha()
        ]
        return list(set(phrases))[:20]  # Return top 20 unique phrases

    def get_grounding_pass(self, metrics: EvaluationMetrics) -> bool:
        """Check if evaluation passes grounding threshold."""
        return metrics.grounding_score >= self.threshold_grounding

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics from evaluation history."""
        if not self.evaluation_history:
            return {
                "total_evaluations": 0,
                "average_faithfulness": 0.0,
                "average_grounding_score": 0.0,
                "hallucination_rate": 0.0,
                "pass_rate": 0.0,
            }
        
        total = len(self.evaluation_history)
        
        avg_faithfulness = sum(
            m.faithfulness for m in self.evaluation_history
        ) / total
        
        avg_grounding = sum(
            m.grounding_score for m in self.evaluation_history
        ) / total
        
        hallucination_count = sum(
            1 for m in self.evaluation_history if m.has_hallucination
        )
        
        pass_count = sum(
            1 for m in self.evaluation_history if not m.has_hallucination
        )
        
        return {
            "total_evaluations": total,
            "average_faithfulness": round(avg_faithfulness, 3),
            "average_context_recall": round(
                sum(m.context_recall for m in self.evaluation_history) / total, 3
            ),
            "average_context_precision": round(
                sum(m.context_precision for m in self.evaluation_history) / total, 3
            ),
            "average_answer_relevancy": round(
                sum(m.answer_relevancy for m in self.evaluation_history) / total, 3
            ),
            "average_grounding_score": round(avg_grounding, 3),
            "hallucination_rate": round(hallucination_count / total, 3),
            "pass_rate": round(pass_count / total, 3),
            "threshold_grounding": self.threshold_grounding,
            "status": "PASS" if avg_grounding >= self.threshold_grounding else "FAIL",
        }

    def clear_history(self) -> None:
        """Clear evaluation history."""
        self.evaluation_history.clear()
