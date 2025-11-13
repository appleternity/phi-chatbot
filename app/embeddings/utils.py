"""
Utility functions for embedding providers.

Provides shared utilities for retry logic, error handling, and common operations
across all embedding providers (local, OpenRouter, Aliyun).
"""

import logging
import random
import time
from typing import TypeVar, Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")

def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 10.0,
) -> T:
    """
    Retry function with exponential backoff and jitter.

    Implements exponential backoff retry strategy for transient failures:
    - Retries HTTP 5xx errors (server-side failures)
    - Retries HTTP 429 (rate limit exceeded)
    - Retries network timeouts, connection errors, DNS failures
    - Does NOT retry HTTP 4xx errors (except 429) - permanent failures
    - Adds jitter to prevent thundering herd problem

    Backoff schedule (base_delay=2s, 3 retries):
    - Attempt 1: Immediate (0s)
    - Attempt 2: 2s + jitter (0-0.2s) = ~2s total
    - Attempt 3: 4s + jitter (0-0.4s) = ~4s total
    - Attempt 4: 8s + jitter (0-0.8s) = ~8s total
    - Total max delay: ~15s for 3 retries

    Args:
        func: Function to retry (no arguments)
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Base delay in seconds between retries (default: 2.0)
        max_delay: Maximum delay cap in seconds (default: 10.0)

    Returns:
        Function result on success

    Raises:
        Exception: Last exception if all retries exhausted

    Example:
        >>> def api_call():
        ...     return client.embeddings.create(model="...", input="...")
        >>> response = retry_with_backoff(api_call, max_retries=3)
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            # Don't retry on client errors (4xx except 429)
            # HTTP 401/403: Authentication failure (permanent)
            # HTTP 400: Bad request (permanent)
            # HTTP 404: Not found (permanent)
            # HTTP 429: Rate limit (transient, should retry)
            if hasattr(e, "status_code"):
                status_code = e.status_code
                if 400 <= status_code < 500 and status_code != 429:
                    logger.error(
                        f"Client error {status_code} (permanent failure), not retrying: {e}"
                    )
                    raise

            # Last attempt, raise exception
            if attempt == max_retries:
                logger.error(f"All {max_retries} retries exhausted: {e}")
                raise

            # Calculate backoff with jitter
            # Exponential: 2^attempt * base_delay (2s, 4s, 8s, ...)
            # Jitter: Random 0-10% of delay to prevent synchronization
            delay = min(base_delay * (2**attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)
            total_delay = delay + jitter

            logger.warning(f"Retry {attempt + 1}/{max_retries} after {total_delay:.2f}s: {e}")
            time.sleep(total_delay)

    # Should never reach here, but satisfy type checker
    raise RuntimeError(f"Unexpected retry logic exit after {max_retries} attempts")
