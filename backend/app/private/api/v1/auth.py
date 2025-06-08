from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token
from app.models import User
from app.schemas.admin import AdminLogin, AdminTokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AdminTokenResponse)
async def admin_login(
    login_data: AdminLogin, db: Session = Depends(get_db)
) -> AdminTokenResponse:
    """Admin login endpoint."""
    # For now, we'll use a simple hardcoded admin check
    # In production, this should check against a proper admin user table

    # Check if user exists and is admin
    user = (
        db.query(User)
        .filter(User.phone_number == login_data.username, User.is_admin)
        .first()
    )

    if not user:
        # For initial setup, create an admin user if none exists
        # This is just for development - remove in production
        if login_data.username == "admin" and login_data.password == "admin123":
            # Check if any admin exists
            admin_exists = db.query(User).filter(User.is_admin).first()
            if not admin_exists:
                # Create the first admin user
                from datetime import datetime

                admin_user = User(
                    phone_number="admin",
                    display_name="System Admin",
                    first_name="System",
                    last_name="Admin",
                    first_seen=datetime.utcnow(),
                    is_admin=True,
                    is_active=True,
                )
                db.add(admin_user)
                db.commit()
                db.refresh(admin_user)
                user = admin_user
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

    # For development, allow simple password check
    # In production, use proper password hashing
    if login_data.username == "admin" and login_data.password == "admin123":
        # Create access token
        access_token_expires = timedelta(hours=24)
        access_token = create_access_token(
            data={"sub": user.id}, expires_delta=access_token_expires
        )

        return AdminTokenResponse(access_token=access_token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
    )
