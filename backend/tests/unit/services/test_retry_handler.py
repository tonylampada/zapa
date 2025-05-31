"""Unit tests for retry handler."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.services.retry_handler import RetryHandler


@pytest.mark.asyncio
class TestRetryHandler:
    """Test retry handler functionality."""
    
    async def test_successful_first_attempt(self):
        """Test function succeeds on first attempt."""
        mock_func = AsyncMock(return_value="success")
        
        result = await RetryHandler.with_retry(
            mock_func,
            "arg1",
            kwarg1="value1",
            max_retries=3
        )
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
    
    async def test_retry_on_failure(self):
        """Test function retries on failure and eventually succeeds."""
        mock_func = AsyncMock()
        # Fail twice, then succeed
        mock_func.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            "success"
        ]
        
        with patch('asyncio.sleep') as mock_sleep:
            result = await RetryHandler.with_retry(
                mock_func,
                max_retries=3,
                delay=1.0,
                backoff=2.0
            )
        
        assert result == "success"
        assert mock_func.call_count == 3
        
        # Check sleep was called with correct delays
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)  # First retry: delay * backoff^0
        mock_sleep.assert_any_call(2.0)  # Second retry: delay * backoff^1
    
    async def test_all_retries_exhausted(self):
        """Test exception raised when all retries fail."""
        mock_func = AsyncMock()
        mock_func.side_effect = Exception("Persistent failure")
        
        with patch('asyncio.sleep'):
            with pytest.raises(Exception) as exc_info:
                await RetryHandler.with_retry(
                    mock_func,
                    max_retries=3
                )
            
            assert str(exc_info.value) == "Persistent failure"
            assert mock_func.call_count == 3
    
    async def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            Exception("Failure 1"),
            Exception("Failure 2"),
            Exception("Failure 3"),
            Exception("Failure 4")
        ]
        
        sleep_calls = []
        
        async def mock_sleep(delay):
            sleep_calls.append(delay)
        
        with patch('asyncio.sleep', mock_sleep):
            with pytest.raises(Exception):
                await RetryHandler.with_retry(
                    mock_func,
                    max_retries=4,
                    delay=0.5,
                    backoff=3.0
                )
        
        # Verify exponential backoff
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == 0.5    # 0.5 * 3^0
        assert sleep_calls[1] == 1.5    # 0.5 * 3^1
        assert sleep_calls[2] == 4.5    # 0.5 * 3^2
    
    async def test_zero_retries(self):
        """Test with max_retries=1 (no retries, just one attempt)."""
        mock_func = AsyncMock()
        mock_func.side_effect = Exception("Failure")
        
        with pytest.raises(Exception) as exc_info:
            await RetryHandler.with_retry(
                mock_func,
                max_retries=1
            )
        
        assert str(exc_info.value) == "Failure"
        mock_func.assert_called_once()
    
    async def test_function_with_return_value(self):
        """Test retry handler preserves function return value."""
        async def test_func(x, y, z=3):
            return x + y + z
        
        result = await RetryHandler.with_retry(
            test_func,
            1,
            2,
            z=4
        )
        
        assert result == 7