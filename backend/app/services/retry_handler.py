"""Retry handler for resilient service operations."""

from typing import Callable, Any, TypeVar, Coroutine
import asyncio
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryHandler:
    """Handler for retrying failed operations with exponential backoff."""
    
    @staticmethod
    async def with_retry(
        func: Callable[..., Coroutine[Any, Any, T]],
        *args,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        **kwargs
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
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = delay * (backoff ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"All {max_retries} attempts failed for {func.__name__}: {e}"
                    )
        
        raise last_exception