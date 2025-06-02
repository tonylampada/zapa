import base64
import hashlib
import time
from datetime import datetime

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.llm.agent import create_agent
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin
from app.models import LLMConfig, User
from app.schemas.admin import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestResponse,
    LLMConfigUpdate,
    LLMProviderInfo,
)

router = APIRouter(prefix="/admin/llm-config", tags=["admin-llm"])

# Initialize Fernet for encryption/decryption
# Generate a proper Fernet key from the configured encryption key
key_bytes = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
fernet_key = base64.urlsafe_b64encode(key_bytes)
fernet = Fernet(fernet_key)


@router.get("/providers", response_model=list[LLMProviderInfo])
async def get_available_providers(current_admin=Depends(get_current_admin)):
    """Get list of available LLM providers and their models."""
    return [
        LLMProviderInfo(
            provider="openai",
            name="OpenAI",
            models=["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            supports_function_calling=True,
        ),
        LLMProviderInfo(
            provider="anthropic",
            name="Anthropic",
            models=["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
            supports_function_calling=True,
        ),
        LLMProviderInfo(
            provider="google",
            name="Google",
            models=["gemini-pro", "gemini-pro-vision"],
            supports_function_calling=True,
        ),
    ]


@router.get("/{user_id}", response_model=LLMConfigResponse)
async def get_user_llm_config(
    user_id: int, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)
):
    """Get LLM configuration for a user."""
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get active LLM config
    config = db.query(LLMConfig).filter(LLMConfig.user_id == user_id, LLMConfig.is_active).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No LLM configuration found for this user"
        )

    # Don't expose the actual API key
    model_settings = config.model_settings.copy()
    model_settings["api_key"] = "***hidden***"

    return LLMConfigResponse(
        id=config.id,
        user_id=config.user_id,
        provider=config.provider,
        model_settings=model_settings,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/{user_id}", response_model=LLMConfigResponse)
async def create_user_llm_config(
    user_id: int,
    config_data: LLMConfigCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """Create LLM configuration for a user."""
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Deactivate any existing configs
    db.query(LLMConfig).filter(LLMConfig.user_id == user_id).update({"is_active": False})

    # Encrypt the API key
    encrypted_api_key = fernet.encrypt(config_data.api_key.encode()).decode()

    # Create model settings with encrypted API key
    model_settings = config_data.model_settings.copy()
    model_settings["api_key"] = encrypted_api_key

    # Set default model if not specified
    if "model" not in model_settings:
        default_models = {"openai": "gpt-4", "anthropic": "claude-3-sonnet", "google": "gemini-pro"}
        model_settings["model"] = default_models.get(config_data.provider, "gpt-4")

    # Create new config
    new_config = LLMConfig(
        user_id=user_id,
        provider=config_data.provider,
        model_settings=model_settings,
        is_active=config_data.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(new_config)
    db.commit()
    db.refresh(new_config)

    # Return response without exposing API key
    response_settings = model_settings.copy()
    response_settings["api_key"] = "***hidden***"

    return LLMConfigResponse(
        id=new_config.id,
        user_id=new_config.user_id,
        provider=new_config.provider,
        model_settings=response_settings,
        is_active=new_config.is_active,
        created_at=new_config.created_at,
        updated_at=new_config.updated_at,
    )


@router.put("/{user_id}", response_model=LLMConfigResponse)
async def update_user_llm_config(
    user_id: int,
    config_data: LLMConfigUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """Update LLM configuration for a user."""
    # Get existing config
    config = db.query(LLMConfig).filter(LLMConfig.user_id == user_id, LLMConfig.is_active).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active LLM configuration found for this user",
        )

    # Update fields if provided
    if config_data.api_key is not None:
        encrypted_api_key = fernet.encrypt(config_data.api_key.encode()).decode()
        config.model_settings["api_key"] = encrypted_api_key

    if config_data.model_settings is not None:
        # Preserve API key if not being updated
        api_key = config.model_settings.get("api_key")
        config.model_settings.update(config_data.model_settings)
        if api_key and "api_key" not in config_data.model_settings:
            config.model_settings["api_key"] = api_key

    if config_data.is_active is not None:
        config.is_active = config_data.is_active

    config.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(config)

    # Return response without exposing API key
    response_settings = config.model_settings.copy()
    response_settings["api_key"] = "***hidden***"

    return LLMConfigResponse(
        id=config.id,
        user_id=config.user_id,
        provider=config.provider,
        model_settings=response_settings,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/{user_id}/test", response_model=LLMConfigTestResponse)
async def test_user_llm_config(
    user_id: int, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)
):
    """Test if the user's LLM configuration is working."""
    # Get user and config
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    config = db.query(LLMConfig).filter(LLMConfig.user_id == user_id, LLMConfig.is_active).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active LLM configuration found for this user",
        )

    # Try to create an agent and make a simple call
    start_time = time.time()

    try:
        # Decrypt API key for testing
        decrypted_settings = config.model_settings.copy()
        encrypted_key = config.model_settings.get("api_key")
        if encrypted_key:
            decrypted_settings["api_key"] = fernet.decrypt(encrypted_key.encode()).decode()

        # Create agent with decrypted settings
        agent = create_agent(
            provider=config.provider, model_settings=decrypted_settings, user=user, db=db
        )

        # Make a simple test call
        agent.run("Say 'Hello, the LLM configuration is working!' and nothing else.")

        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)

        return LLMConfigTestResponse(
            success=True,
            error_message=None,
            response_time_ms=response_time_ms,
            model_used=config.model_settings.get("model", "unknown"),
        )

    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)

        return LLMConfigTestResponse(
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms,
            model_used=config.model_settings.get("model", "unknown"),
        )
