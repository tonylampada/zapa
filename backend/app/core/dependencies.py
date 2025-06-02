"""Common dependencies for the application."""


from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService

security = HTTPBearer()


def get_auth_service() -> AuthService:
    """Get auth service instance."""
    return AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Get current user from JWT token."""
    token = credentials.credentials

    try:
        payload = auth_service.verify_access_token(token)
        return {
            "user_id": payload["user_id"],
            "phone_number": payload["phone_number"],
            "is_admin": payload.get("is_admin", False),
        }
    except (JWTError, KeyError, ValueError) as e:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_active_user(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Get current active user from database."""
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user
