"""LLM service with token budgeting, fallback routing, and structured output."""

from typing import Optional, Dict, Any, List
import json
from src.layer1_settings import settings, logger


class LLMService:
    """Manages OpenAI API interactions with token tracking and fallback."""

    # Token limits per model
    TOKEN_LIMITS = {
        "gpt-4": 8000,
        "gpt-4-32k": 32000,
        "gpt-3.5-turbo": 4000,
    }

    # Approximate tokens per word
    TOKENS_PER_WORD = 1.3

    def __init__(self):
        """Initialize LLM service."""
        self.primary_model = settings.llm_settings.primary_model
        self.fallback_model = settings.llm_settings.fallback_model
        self.api_key = settings.llm_settings.openai_api_key
        self.token_budget = settings.llm_settings.token_budget

    def estimate_tokens(self, text: str) -> int:
        """
        Rough estimate of tokens in text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        words = len(text.split())
        return int(words * self.TOKENS_PER_WORD)

    def generate(
        self,
        prompt: str,
        context: str = "",
        max_tokens: int = 500,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate text using OpenAI.

        Args:
            prompt: Main prompt
            context: Optional context/system message
            max_tokens: Max completion tokens
            temperature: Sampling temperature
            model: Override model (default: primary)

        Returns:
            Generated text

        Raises:
            ImportError: If openai not installed
            Exception: If API call fails
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required")

        client = OpenAI(api_key=self.api_key)
        model_to_use = model or self.primary_model

        # Calculate tokens
        input_tokens = self.estimate_tokens(prompt + context)
        total_tokens = input_tokens + max_tokens

        if total_tokens > self.token_budget:
            logger.warning(
                f"Token budget exceeded: {total_tokens} > {self.token_budget}. "
                f"Reducing max_tokens from {max_tokens} to {self.token_budget - input_tokens}"
            )
            max_tokens = max(100, self.token_budget - input_tokens)

        try:
            response = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": context or "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            text = response.choices[0].message.content
            logger.debug(
                f"LLM response ({model_to_use}): {len(text)} chars, "
                f"usage: {response.usage.prompt_tokens}+{response.usage.completion_tokens}"
            )
            return text

        except Exception as e:
            logger.error(f"LLM generation failed with {model_to_use}: {e}")
            if model_to_use != self.fallback_model:
                logger.info(f"Falling back to {self.fallback_model}")
                return self.generate(
                    prompt=prompt,
                    context=context,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    model=self.fallback_model,
                )
            raise

    def generate_structured(
        self,
        prompt: str,
        context: str,
        output_format: Dict[str, Any],
        max_tokens: int = 500,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Args:
            prompt: Main prompt
            context: System context
            output_format: Expected JSON schema as dict
            max_tokens: Max tokens

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If response doesn't match format
            Exception: If API call fails
        """
        # Add JSON instruction to prompt
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"Respond with valid JSON matching this schema:\n"
            f"{output_format}"
        )

        response_text = self.generate(
            prompt=enhanced_prompt,
            context=context,
            max_tokens=max_tokens,
            temperature=0.1,  # Low temp for consistency
        )

        # Parse JSON
        try:
            result = json.loads(response_text)
            logger.debug(f"Structured output parsed successfully")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse structured output: {e}\nText: {response_text}")
            raise ValueError(f"LLM output not valid JSON: {response_text}")

    def extract_citations(
        self,
        answer: str,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Extract citations from answer referring to retrieved chunks.

        Simple heuristic: find chunk IDs mentioned in answer or do substring matching.

        Args:
            answer: Generated answer text
            retrieved_chunks: List of chunks used

        Returns:
            List of cited chunks with evidence
        """
        citations = []

        for chunk in retrieved_chunks:
            chunk_id = chunk.get("chunk_id", "")
            chunk_text = chunk.get("text", "")

            # Check if chunk ID mentioned explicitly
            if chunk_id in answer:
                citations.append({
                    "chunk_id": chunk_id,
                    "source": chunk.get("source"),
                    "evidence": chunk_text[:200],  # First 200 chars
                    "citation_type": "explicit",
                })
            # Check if major content appears in answer
            elif len(chunk_text) > 50:
                # Check if any significant phrase from chunk appears in answer
                phrases = chunk_text.split(".")
                for phrase in phrases:
                    if len(phrase) > 30 and phrase.strip() in answer:
                        citations.append({
                            "chunk_id": chunk_id,
                            "source": chunk.get("source"),
                            "evidence": chunk_text[:200],
                            "citation_type": "implicit",
                        })
                        break

        return citations

    def count_tokens(self, text: str) -> int:
        """Get token count for text."""
        return self.estimate_tokens(text)
