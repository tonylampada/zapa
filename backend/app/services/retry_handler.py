"""Retry handler for resilient service operations."""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryHandler:
    """Handler for retrying failed operations with exponential backoff."""

    @staticmethod
    async def with_retry(
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        **kwargs: Any,
    ) -> T:
        """
        Execute async function with exponential backoff retry.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            max_retries: Maximum number of retry attempts
            delay: Initial delay between retries in seconds
            backoff: Backoff multiplier for exponential delay
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution

        Raises:
            Last exception if all retries fail
        """
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = delay * (backoff**attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {max_retries} attempts failed for {func.__name__}: {e}")

        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError("Retry failed but no exception was captured")
