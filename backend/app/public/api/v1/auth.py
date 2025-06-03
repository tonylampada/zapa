"""Public API authentication endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.adapters.whatsapp import WhatsAppBridge
from app.config.public import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.auth import AuthCodeRequest, AuthCodeVerify, AuthTokenResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


def get_auth_service() -> AuthService:
    """Get auth service instance."""
    return AuthService()


def get_whatsapp_adapter() -> WhatsAppBridge:
    """Get WhatsApp adapter instance."""
    return WhatsAppBridge(
        base_url=settings.WHATSAPP_API_URL,
    )


@router.post("/request-code", response_model=dict)
async def request_auth_code(
    request: AuthCodeRequest,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    whatsapp: WhatsAppBridge = Depends(get_whatsapp_adapter),
) -> dict:
    """Request authentication code via WhatsApp."""
    # Check rate limit
    if not auth_service.check_rate_limit(db, request.phone_number):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
        )

    # Create auth code
    auth_code, is_new_user = auth_service.create_auth_code(db, request.phone_number)

    # Send code via WhatsApp
    message = (
        f"Your Zapa verification code is: {auth_code.code}\n\n"
        "This code expires in 5 minutes.\n"
        "If you didn't request this, please ignore this message."
    )

    try:
        async with whatsapp as client:
            # Get the main WhatsApp session (first active session)
            sessions = await client.list_sessions()
            if not sessions:
                logger.error("No WhatsApp sessions available")
                # Still return success to prevent user enumeration
            else:
                main_session = sessions[0].session_id
                await client.send_message(
                    session_id=main_session,
                    recipient=request.phone_number,
                    content=message,
                )
                logger.info(f"Auth code sent to {request.phone_number}")
    except Exception as e:
        logger.error(f"Failed to send auth code via WhatsApp: {e}")
        # Still return success to prevent user enumeration

    return {
        "success": True,
        "message": "Authentication code sent via WhatsApp",
        "phone_number": request.phone_number,
    }


@router.post("/verify", response_model=AuthTokenResponse)
async def verify_auth_code(
    request: AuthCodeVerify,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    """Verify authentication code and receive JWT token."""
    # Verify code
    user = auth_service.verify_auth_code(db, request.phone_number, request.code)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired code",
        )

    # Generate JWT token
    token = auth_service.create_access_token(
        user_id=user.id,
        phone_number=user.phone_number,
        is_admin=user.is_admin,
    )

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=86400,  # 24 hours
        user_id=user.id,
        phone_number=user.phone_number,
    )


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get current authenticated user info."""
    return {
        "user_id": current_user["user_id"],
        "phone_number": current_user["phone_number"],
        "is_authenticated": True,
    }
