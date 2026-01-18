"""Retry logic with exponential backoff."""

import time
import random
from typing import Any, Callable, Optional, Type, Tuple
from src.layer1_settings import logger


class RetryConfig:
    """Configuration for retry strategy."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retriable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay cap
            exponential_base: Base for exponential backoff
            jitter: Add random jitter to delays
            retriable_exceptions: Exceptions to retry on
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retriable_exceptions = retriable_exceptions


class RetryLogic:
    """Implements exponential backoff retry pattern."""

    @staticmethod
    def execute_with_retry(
        func: Callable,
        config: RetryConfig,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute function with exponential backoff retry.

        Args:
            func: Callable to execute
            config: Retry configuration
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: Last exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 1:
                    logger.info(f"Succeeded on attempt {attempt}")
                return result

            except config.retriable_exceptions as e:
                last_exception = e
                
                if attempt == config.max_attempts:
                    logger.error(
                        f"All {config.max_attempts} attempts failed. Last error: {str(e)}"
                    )
                    raise
                
                # Calculate backoff delay
                delay = RetryLogic._calculate_backoff(
                    attempt,
                    config.initial_delay,
                    config.max_delay,
                    config.exponential_base,
                    config.jitter,
                )
                
                logger.warning(
                    f"Attempt {attempt} failed: {str(e)}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)

    @staticmethod
    def _calculate_backoff(
        attempt: int,
        initial_delay: float,
        max_delay: float,
        exponential_base: float,
        jitter: bool,
    ) -> float:
        """
        Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number (1-indexed)
            initial_delay: Initial delay
            max_delay: Maximum cap
            exponential_base: Base for exponential calculation
            jitter: Whether to add random jitter

        Returns:
            Delay in seconds
        """
        # Exponential: initial_delay * (base ^ (attempt - 1))
        delay = initial_delay * (exponential_base ** (attempt - 1))
        
        # Cap at max_delay
        delay = min(delay, max_delay)
        
        # Add jitter: ±10% random variation
        if jitter:
            jitter_amount = delay * 0.1
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(delay, 0.0)
