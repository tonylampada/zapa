"""Authentication service for handling auth codes and JWT tokens."""

import secrets
from datetime import datetime, timedelta

from jose import JWTError, jwt
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_code import AuthCode
from app.models.user import User


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self) -> None:
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 1440  # 24 hours

    def generate_auth_code(self) -> str:
        """Generate a secure 6-digit authentication code."""
        return "".join([str(secrets.randbelow(10)) for _ in range(6)])

    def create_auth_code(
        self, db: Session, phone_number: str, user: User | None = None
    ) -> tuple[AuthCode, bool]:
        """Create an auth code for a phone number.

        Returns tuple of (auth_code, is_new_user).
        """
        # Check if user exists
        if not user:
            user = db.query(User).filter(User.phone_number == phone_number).first()

        is_new_user = False
        if not user:
            # Create new user
            user = User(
                phone_number=phone_number,
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db.add(user)
            db.flush()  # Get user ID without committing
            is_new_user = True

        # Invalidate any existing codes for this user
        db.query(AuthCode).filter(
            and_(
                AuthCode.user_id == user.id,
                AuthCode.used == False,
                AuthCode.expires_at > datetime.utcnow(),
            )
        ).update({"used": True})

        # Create new auth code
        code = self.generate_auth_code()
        auth_code = AuthCode(
            user_id=user.id,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            used=False,
        )
        db.add(auth_code)
        db.commit()

        return auth_code, is_new_user

    def verify_auth_code(self, db: Session, phone_number: str, code: str) -> User | None:
        """Verify an auth code and return the user if valid."""
        # Find user by phone number
        user = db.query(User).filter(User.phone_number == phone_number).first()
        if not user:
            return None

        # Find valid auth code
        auth_code = (
            db.query(AuthCode)
            .filter(
                and_(
                    AuthCode.user_id == user.id,
                    AuthCode.code == code,
                    AuthCode.used == False,
                    AuthCode.expires_at > datetime.utcnow(),
                )
            )
            .first()
        )

        if not auth_code:
            return None

        # Mark code as used
        auth_code.used = True
        db.commit()

        return user

    def create_access_token(self, user_id: int, phone_number: str, is_admin: bool = False) -> str:
        """Create a JWT access token."""
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        expire = datetime.utcnow() + expires_delta

        to_encode = {
            "sub": str(user_id),
            "user_id": user_id,
            "phone_number": phone_number,
            "is_admin": is_admin,
            "exp": expire,
        }
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_access_token(self, token: str) -> dict:
        """Verify and decode a JWT access token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            raise ValueError("Invalid token") from e

    def check_rate_limit(self, db: Session, phone_number: str) -> bool:
        """Check if phone number has exceeded rate limit for auth codes.

        Returns True if within limit, False if exceeded.
        """
        # Count auth codes created in the last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        user = db.query(User).filter(User.phone_number == phone_number).first()
        if not user:
            return True  # New users can always request

        count = (
            db.query(AuthCode)
            .filter(
                and_(
                    AuthCode.user_id == user.id,
                    AuthCode.created_at > one_hour_ago,
                )
            )
            .count()
        )

        return count < 3  # Max 3 requests per hour
