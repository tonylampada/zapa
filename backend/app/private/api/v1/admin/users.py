from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from datetime import datetime
import math

from app.core.database import get_db
from app.core.security import get_current_admin
from app.services.message_service import MessageService
from app.schemas.admin import (
    UserListResponse,
    UserDetailResponse,
    UserCreate,
    UserUpdate,
    ConversationHistoryResponse,
    PaginationParams,
    MessageSummary,
)
from app.models import User, Message, LLMConfig

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """List all users with pagination and optional search."""
    query = db.query(User)

    # Apply search filter if provided
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.phone_number.ilike(search_pattern),
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern),
                User.display_name.ilike(search_pattern),
            )
        )

    # Get total count
    total = query.count()

    # Calculate pagination
    total_pages = math.ceil(total / page_size)
    offset = (page - 1) * page_size

    # Get paginated users
    users = query.offset(offset).limit(page_size).all()

    # Convert to response format
    user_summaries = []
    for user in users:
        # Get message count and last message
        message_count = db.query(func.count(Message.id)).filter(Message.user_id == user.id).scalar()

        last_message = (
            db.query(Message)
            .filter(Message.user_id == user.id)
            .order_by(Message.created_at.desc())
            .first()
        )

        user_summaries.append(
            UserSummary(
                id=user.id,
                phone_number=user.phone_number,
                first_name=user.first_name,
                last_name=user.last_name,
                is_active=user.is_active,
                created_at=user.first_seen,
                last_message_at=last_message.created_at if last_message else None,
                total_messages=message_count,
            )
        )

    return UserListResponse(
        users=user_summaries, total=total, page=page, page_size=page_size, total_pages=total_pages
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: int, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)
):
    """Get detailed information about a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get message counts
    messages_sent = (
        db.query(func.count(Message.id))
        .filter(Message.user_id == user.id, Message.is_from_user == True)
        .scalar()
    )

    messages_received = (
        db.query(func.count(Message.id))
        .filter(Message.user_id == user.id, Message.is_from_user == False)
        .scalar()
    )

    # Check if LLM config exists
    llm_config_set = (
        db.query(LLMConfig)
        .filter(LLMConfig.user_id == user.id, LLMConfig.is_active == True)
        .first()
        is not None
    )

    # Get last message
    last_message = (
        db.query(Message)
        .filter(Message.user_id == user.id)
        .order_by(Message.created_at.desc())
        .first()
    )

    return UserDetailResponse(
        id=user.id,
        phone_number=user.phone_number,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        created_at=user.first_seen,
        last_message_at=last_message.created_at if last_message else None,
        total_messages=messages_sent + messages_received,
        user_metadata=user.user_metadata,
        llm_config_set=llm_config_set,
        messages_sent=messages_sent,
        messages_received=messages_received,
    )


@router.post("/", response_model=UserDetailResponse)
async def create_user(
    user_data: UserCreate, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)
):
    """Create a new user."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.phone_number == user_data.phone_number).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists",
        )

    # Create new user
    new_user = User(
        phone_number=user_data.phone_number,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        is_active=user_data.is_active,
        user_metadata=user_data.user_metadata or {},
        first_seen=datetime.utcnow(),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserDetailResponse(
        id=new_user.id,
        phone_number=new_user.phone_number,
        first_name=new_user.first_name,
        last_name=new_user.last_name,
        is_active=new_user.is_active,
        created_at=new_user.first_seen,
        last_message_at=None,
        total_messages=0,
        user_metadata=new_user.user_metadata,
        llm_config_set=False,
        messages_sent=0,
        messages_received=0,
    )


@router.put("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """Update an existing user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Update fields if provided
    if user_data.first_name is not None:
        user.first_name = user_data.first_name
    if user_data.last_name is not None:
        user.last_name = user_data.last_name
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.user_metadata is not None:
        user.user_metadata = user_data.user_metadata

    db.commit()
    db.refresh(user)

    # Get updated stats
    messages_sent = (
        db.query(func.count(Message.id))
        .filter(Message.user_id == user.id, Message.is_from_user == True)
        .scalar()
    )

    messages_received = (
        db.query(func.count(Message.id))
        .filter(Message.user_id == user.id, Message.is_from_user == False)
        .scalar()
    )

    llm_config_set = (
        db.query(LLMConfig)
        .filter(LLMConfig.user_id == user.id, LLMConfig.is_active == True)
        .first()
        is not None
    )

    last_message = (
        db.query(Message)
        .filter(Message.user_id == user.id)
        .order_by(Message.created_at.desc())
        .first()
    )

    return UserDetailResponse(
        id=user.id,
        phone_number=user.phone_number,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        created_at=user.first_seen,
        last_message_at=last_message.created_at if last_message else None,
        total_messages=messages_sent + messages_received,
        user_metadata=user.user_metadata,
        llm_config_set=llm_config_set,
        messages_sent=messages_sent,
        messages_received=messages_received,
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: int, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)
):
    """Delete a user and all their data."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Don't allow deleting admin users
    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete admin users"
        )

    # Delete user (cascade will handle related records)
    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}


@router.get("/{user_id}/conversations", response_model=ConversationHistoryResponse)
async def get_user_conversations(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """Get conversation history for a specific user."""
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Query messages
    query = db.query(Message).filter(Message.user_id == user_id)

    # Get total count
    total = query.count()

    # Calculate pagination
    total_pages = math.ceil(total / page_size)
    offset = (page - 1) * page_size

    # Get paginated messages
    messages = query.order_by(Message.created_at.desc()).offset(offset).limit(page_size).all()

    # Convert to response format
    message_summaries = [
        MessageSummary(
            id=msg.id,
            content=msg.content,
            is_from_user=msg.is_from_user,
            message_type=msg.message_type.value,
            created_at=msg.created_at,
            status=msg.status.value,
        )
        for msg in messages
    ]

    return ConversationHistoryResponse(
        messages=message_summaries,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.delete("/{user_id}/conversations")
async def clear_user_conversations(
    user_id: int, db: Session = Depends(get_db), current_admin=Depends(get_current_admin)
):
    """Clear all conversation history for a user."""
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Delete all messages for the user
    deleted_count = db.query(Message).filter(Message.user_id == user_id).delete()
    db.commit()

    return {"message": f"Deleted {deleted_count} messages"}
