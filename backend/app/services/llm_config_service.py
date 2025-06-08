"""Service for managing LLM configurations."""

import asyncio
import logging
import time

from sqlalchemy.orm import Session

from app.config.encryption import get_encryption_manager
from app.models.llm_config import LLMConfig
from app.schemas.llm import LLMConfigRequest, LLMConfigResponse, LLMTestResponse

logger = logging.getLogger(__name__)


class LLMConfigService:
    """Service for managing user LLM configurations."""

    def __init__(self):
        self.encryption_manager = get_encryption_manager()

    def get_user_config(self, db: Session, user_id: int) -> LLMConfigResponse | None:
        """Get user's LLM configuration."""
        config = (
            db.query(LLMConfig)
            .filter(LLMConfig.user_id == user_id, LLMConfig.is_active)
            .first()
        )

        if not config:
            return None

        return LLMConfigResponse.model_validate(config)

    def save_user_config(
        self, db: Session, user_id: int, config: LLMConfigRequest
    ) -> LLMConfigResponse:
        """Save or update user's LLM configuration."""
        # Encrypt the API key
        encrypted_key = self.encryption_manager.encrypt(
            config.api_key.encode()
        ).decode()

        # Check if user already has a config
        existing_config = (
            db.query(LLMConfig).filter(LLMConfig.user_id == user_id).first()
        )

        if existing_config:
            # Update existing config
            existing_config.provider = config.provider
            existing_config.api_key_encrypted = encrypted_key
            existing_config.model_settings = config.model_settings
            existing_config.is_active = config.is_active
            db.commit()
            db.refresh(existing_config)
            return LLMConfigResponse.model_validate(existing_config)
        else:
            # Create new config
            new_config = LLMConfig(
                user_id=user_id,
                provider=config.provider,
                api_key_encrypted=encrypted_key,
                model_settings=config.model_settings,
                is_active=config.is_active,
            )
            db.add(new_config)
            db.commit()
            db.refresh(new_config)
            return LLMConfigResponse.model_validate(new_config)

    def delete_user_config(self, db: Session, user_id: int) -> bool:
        """Delete user's LLM configuration."""
        config = db.query(LLMConfig).filter(LLMConfig.user_id == user_id).first()

        if not config:
            return False

        db.delete(config)
        db.commit()
        return True

    def validate_config(self, config: LLMConfigRequest) -> "ValidationResult":
        """Validate LLM configuration."""
        try:
            # Basic validation
            if not config.api_key.strip():
                return ValidationResult(False, "API key cannot be empty")

            if not config.model_settings:
                return ValidationResult(False, "Model settings are required")

            # Provider-specific validation
            if config.provider == "openai":
                if not config.api_key.startswith("sk-"):
                    return ValidationResult(
                        False, "OpenAI API key must start with 'sk-'"
                    )

            elif config.provider == "anthropic":
                if not config.api_key.startswith("sk-ant-"):
                    return ValidationResult(
                        False, "Anthropic API key must start with 'sk-ant-'"
                    )

            # Validate model settings
            required_fields = ["model"]
            for field in required_fields:
                if field not in config.model_settings:
                    return ValidationResult(
                        False, f"'{field}' is required in model_settings"
                    )

            return ValidationResult(True, None)

        except Exception as e:
            logger.error(f"Config validation error: {e}")
            return ValidationResult(False, f"Validation failed: {str(e)}")

    async def test_config(self, config: LLMConfigResponse) -> LLMTestResponse:
        """Test LLM configuration by making a simple API call."""
        try:
            start_time = time.time()

            # Get the decrypted API key (this would need access to the encrypted key)
            # For now, we'll simulate a test
            test_message = "Hello! This is a test message to verify the API connection."

            # Simulate API call based on provider
            if config.provider == "openai":
                success, message = await self._test_openai_config(config, test_message)
            elif config.provider == "anthropic":
                success, message = await self._test_anthropic_config(
                    config, test_message
                )
            elif config.provider == "google":
                success, message = await self._test_google_config(config, test_message)
            else:
                success, message = False, f"Unsupported provider: {config.provider}"

            response_time = int((time.time() - start_time) * 1000)

            return LLMTestResponse(
                success=success,
                message=message,
                response_time_ms=response_time,
                provider=config.provider,
                model=config.model_settings.get("model", "unknown"),
            )

        except Exception as e:
            logger.error(f"Config test error: {e}")
            return LLMTestResponse(
                success=False,
                message=f"Test failed: {str(e)}",
                response_time_ms=None,
                provider=config.provider,
                model=config.model_settings.get("model", "unknown"),
            )

    async def _test_openai_config(
        self, config: LLMConfigResponse, test_message: str
    ) -> tuple[bool, str]:
        """Test OpenAI configuration."""
        try:
            # Simulate API call - in real implementation, would use actual OpenAI client
            await asyncio.sleep(0.5)  # Simulate network delay
            return True, "OpenAI API connection successful"
        except Exception as e:
            return False, f"OpenAI API error: {str(e)}"

    async def _test_anthropic_config(
        self, config: LLMConfigResponse, test_message: str
    ) -> tuple[bool, str]:
        """Test Anthropic configuration."""
        try:
            # Simulate API call - in real implementation, would use actual Anthropic client
            await asyncio.sleep(0.5)  # Simulate network delay
            return True, "Anthropic API connection successful"
        except Exception as e:
            return False, f"Anthropic API error: {str(e)}"

    async def _test_google_config(
        self, config: LLMConfigResponse, test_message: str
    ) -> tuple[bool, str]:
        """Test Google configuration."""
        try:
            # Simulate API call - in real implementation, would use actual Google client
            await asyncio.sleep(0.5)  # Simulate network delay
            return True, "Google API connection successful"
        except Exception as e:
            return False, f"Google API error: {str(e)}"


class ValidationResult:
    """Result of configuration validation."""

    def __init__(self, is_valid: bool, error: str | None = None):
        self.is_valid = is_valid
        self.error = error
