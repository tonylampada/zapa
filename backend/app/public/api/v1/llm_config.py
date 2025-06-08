"""Public API LLM configuration endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.llm import LLMConfigRequest, LLMConfigResponse, LLMTestResponse
from app.services.llm_config_service import LLMConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-config", tags=["llm-configuration"])


def get_llm_config_service() -> LLMConfigService:
    """Get LLM config service instance."""
    return LLMConfigService()


@router.get("/", response_model=LLMConfigResponse | None)
async def get_llm_config(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    llm_service: LLMConfigService = Depends(get_llm_config_service),
) -> LLMConfigResponse | None:
    """Get user's current LLM configuration."""
    user_id = current_user["user_id"]

    try:
        config = llm_service.get_user_config(db=db, user_id=user_id)
        return config
    except Exception as e:
        logger.error(f"Failed to get LLM config for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve LLM configuration") from e


@router.post("/", response_model=LLMConfigResponse)
async def create_or_update_llm_config(
    config: LLMConfigRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    llm_service: LLMConfigService = Depends(get_llm_config_service),
) -> LLMConfigResponse:
    """Create or update user's LLM configuration."""
    user_id = current_user["user_id"]

    try:
        # Validate the configuration
        validation_result = llm_service.validate_config(config)
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid configuration: {validation_result.error}",
            )

        # Save the configuration
        saved_config = llm_service.save_user_config(db=db, user_id=user_id, config=config)
        return saved_config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save LLM config for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save LLM configuration") from e


@router.post("/test", response_model=LLMTestResponse)
async def test_llm_config(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    llm_service: LLMConfigService = Depends(get_llm_config_service),
) -> LLMTestResponse:
    """Test user's current LLM configuration."""
    user_id = current_user["user_id"]

    try:
        # Get current config
        config = llm_service.get_user_config(db=db, user_id=user_id)
        if not config:
            raise HTTPException(
                status_code=404,
                detail="No LLM configuration found. Please configure your AI provider first.",
            )

        # Test the configuration
        test_result = await llm_service.test_config(config)
        return test_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test LLM config for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to test LLM configuration") from e


@router.delete("/")
async def delete_llm_config(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    llm_service: LLMConfigService = Depends(get_llm_config_service),
) -> dict:
    """Delete user's LLM configuration."""
    user_id = current_user["user_id"]

    try:
        success = llm_service.delete_user_config(db=db, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="No LLM configuration found to delete")

        return {"success": True, "message": "LLM configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete LLM config for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete LLM configuration") from e


@router.get("/providers", response_model=list)
async def get_supported_providers() -> list:
    """Get list of supported LLM providers."""
    return [
        {
            "value": "openai",
            "name": "OpenAI",
            "description": "GPT-4, GPT-3.5 Turbo",
            "models": [
                {
                    "value": "gpt-4-turbo-preview",
                    "name": "GPT-4 Turbo",
                    "description": "Most capable",
                },
                {
                    "value": "gpt-3.5-turbo",
                    "name": "GPT-3.5 Turbo",
                    "description": "Fast and efficient",
                },
            ],
        },
        {
            "value": "anthropic",
            "name": "Anthropic",
            "description": "Claude 3 Opus, Sonnet, Haiku",
            "models": [
                {
                    "value": "claude-3-opus",
                    "name": "Claude 3 Opus",
                    "description": "Most capable",
                },
                {
                    "value": "claude-3-sonnet",
                    "name": "Claude 3 Sonnet",
                    "description": "Balanced",
                },
                {
                    "value": "claude-3-haiku",
                    "name": "Claude 3 Haiku",
                    "description": "Fast and efficient",
                },
            ],
        },
        {
            "value": "google",
            "name": "Google",
            "description": "Gemini Pro, Gemini Ultra",
            "models": [
                {
                    "value": "gemini-pro",
                    "name": "Gemini Pro",
                    "description": "Advanced reasoning",
                },
                {
                    "value": "gemini-pro-vision",
                    "name": "Gemini Pro Vision",
                    "description": "Multimodal",
                },
            ],
        },
    ]
