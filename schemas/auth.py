import re

from pydantic import BaseModel, Field, field_validator


class AuthCodeRequest(BaseModel):
    """Schema for requesting an auth code."""

    phone_number: str = Field(..., min_length=10, max_length=20)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number format."""
        # Basic validation - must start with + and contain only digits and +
        if not re.match(r"^\+[1-9]\d{1,14}$", v):
            raise ValueError("Invalid phone number format")
        return v


class AuthCodeVerify(BaseModel):
    """Schema for verifying an auth code."""

    phone_number: str = Field(..., min_length=10, max_length=20)
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number format."""
        if not re.match(r"^\+[1-9]\d{1,14}$", v):
            raise ValueError("Invalid phone number format")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code is 6 digits."""
        if not re.match(r"^\d{6}$", v):
            raise ValueError("Code must be 6 digits")
        return v


class AuthToken(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # 1 hour
    user_id: int
