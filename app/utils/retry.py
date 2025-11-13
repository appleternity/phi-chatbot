"""
Retry utilities for network operations.

Provides retry decorators for handling transient network failures in offline scripts.
For API server operations, let exceptions propagate (fail-fast).

Usage:
    from app.utils.retry import retry_on_network_error

    @retry_on_network_error(max_attempts=3)
    def generate_embedding(provider, text):
        return provider.encode(text)
"""

import logging
from functools import wraps
from typing import Callable, TypeVar, ParamSpec
import time

import httpx
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


logger = logging.getLogger(__name__)


# Type variables for generic decorator
P = ParamSpec('P')
R = TypeVar('R')


# Transient network errors that should be retried
TRANSIENT_ERRORS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
)

if HAS_OPENAI:
    TRANSIENT_ERRORS += (
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.RateLimitError,
    )


def retry_on_network_error(
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Retry decorator for network operations with exponential backoff.

    Only retries on transient network errors (timeouts, connection errors, rate limits).
    All other exceptions propagate immediately (fail-fast).

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 2.0)
        max_delay: Maximum delay in seconds between retries (default: 10.0)
        backoff_factor: Exponential backoff multiplier (default: 2.0)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_on_network_error(max_attempts=3)
        def generate_embedding(provider, text):
            return provider.encode(text)
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            delay = initial_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except TRANSIENT_ERRORS as e:
                    last_exception = e

                    if attempt == max_attempts:
                        # Final attempt failed, re-raise
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Log retry attempt
                    logger.warning(
                        f"⚠️  {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}"
                    )
                    logger.info(f"⏳ Retrying in {delay:.1f}s...")

                    # Wait with exponential backoff
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)

                except Exception:
                    # Non-transient error: fail fast, don't retry
                    raise

            # Should never reach here, but satisfy type checker
            assert last_exception is not None
            raise last_exception

        return wrapper
    return decorator


def retry_on_network_error_async(
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Async version of retry_on_network_error.

    Same behavior as retry_on_network_error but for async functions.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 2.0)
        max_delay: Maximum delay in seconds between retries (default: 10.0)
        backoff_factor: Exponential backoff multiplier (default: 2.0)

    Returns:
        Decorated async function with retry logic

    Example:
        @retry_on_network_error_async(max_attempts=3)
        async def generate_embedding(provider, text):
            return await provider.encode(text)
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            import asyncio

            delay = initial_delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)

                except TRANSIENT_ERRORS as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"⚠️  {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}"
                    )
                    logger.info(f"⏳ Retrying in {delay:.1f}s...")

                    await asyncio.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)

                except Exception:
                    # Non-transient error: fail fast, don't retry
                    raise

            assert last_exception is not None
            raise last_exception

        return wrapper
    return decorator
