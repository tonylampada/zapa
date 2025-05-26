"""Custom exceptions for Zapa applications."""
from fastapi import HTTPException
from typing import Any, Dict, Optional


class ZapaException(Exception):
    """Base exception for Zapa applications."""

    def __init__(
        self,
        message: str,
        error_code: str = "ZAPA_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(ZapaException):
    """Database-related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )


class ConfigurationError(ZapaException):
    """Configuration-related errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            details=details,
        )


class WhatsAppBridgeError(ZapaException):
    """WhatsApp Bridge connectivity errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="WHATSAPP_BRIDGE_ERROR",
            status_code=503,
            details=details,
        )


class AuthenticationError(ZapaException):
    """Authentication-related errors."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details,
        )


class AuthorizationError(ZapaException):
    """Authorization-related errors."""

    def __init__(
        self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details,
        )


class ValidationError(ZapaException):
    """Input validation errors."""

    def __init__(
        self, message: str, field: str = None, details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            details=error_details,
        )


class NotFoundError(ZapaException):
    """Resource not found errors."""

    def __init__(
        self,
        resource: str,
        identifier: str = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"

        error_details = details or {}
        error_details["resource"] = resource
        if identifier:
            error_details["identifier"] = identifier

        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=error_details,
        )


class RateLimitError(ZapaException):
    """Rate limiting errors."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
        )


class ExternalServiceError(ZapaException):
    """External service errors (LLM providers, etc.)."""

    def __init__(
        self, service: str, message: str, details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details["service"] = service

        super().__init__(
            message=f"{service}: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details=error_details,
        )
