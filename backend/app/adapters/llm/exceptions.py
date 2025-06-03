"""LLM adapter exceptions."""

from typing import Optional


class LLMError(Exception):
    """Base exception for LLM operations."""

    def __init__(self, message: str, provider: str = "unknown", original_error: Optional[Exception] = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


class LLMConnectionError(LLMError):
    """Raised when connection to LLM provider fails."""

    pass


class LLMAuthenticationError(LLMError):
    """Raised when authentication with LLM provider fails."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""

    pass


class LLMInvalidRequestError(LLMError):
    """Raised when request to LLM is invalid."""

    pass
