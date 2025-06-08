"""Public API message endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.message import MessageResponse, MessageStats
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["messages"])


def get_message_service() -> MessageService:
    """Get message service instance."""
    return MessageService()


@router.get("/", response_model=list[MessageResponse])
async def get_messages(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
    skip: int = Query(0, ge=0, description="Number of messages to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of messages to return"),
    search: str | None = Query(None, description="Search messages by content"),
) -> list[MessageResponse]:
    """Get user's messages with pagination and search."""
    user_id = current_user["user_id"]

    try:
        messages = message_service.get_user_messages(
            db=db, user_id=user_id, skip=skip, limit=limit, search=search
        )
        return messages
    except Exception as e:
        logger.error(f"Failed to get messages for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve messages") from e


@router.get("/recent", response_model=list[MessageResponse])
async def get_recent_messages(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
    count: int = Query(10, ge=1, le=50, description="Number of recent messages"),
) -> list[MessageResponse]:
    """Get user's most recent messages."""
    user_id = current_user["user_id"]

    try:
        messages = message_service.get_recent_messages(db=db, user_id=user_id, count=count)
        return messages
    except Exception as e:
        logger.error(f"Failed to get recent messages for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recent messages") from e


@router.get("/search", response_model=list[MessageResponse])
async def search_messages(
    query: str = Query(..., min_length=1, description="Search query"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
) -> list[MessageResponse]:
    """Search messages by content."""
    user_id = current_user["user_id"]

    try:
        messages = message_service.search_user_messages(
            db=db, user_id=user_id, query=query, skip=skip, limit=limit
        )
        return messages
    except Exception as e:
        logger.error(f"Failed to search messages for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search messages") from e


@router.get("/stats", response_model=MessageStats)
async def get_message_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
) -> MessageStats:
    """Get user's message statistics."""
    user_id = current_user["user_id"]

    try:
        stats = message_service.get_user_message_stats(db=db, user_id=user_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get message stats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve message statistics") from e


@router.get("/export")
async def export_messages(
    format: str = Query("json", regex="^(json|csv)$", description="Export format"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
):
    """Export user's messages in JSON or CSV format."""
    user_id = current_user["user_id"]

    try:
        export_data = message_service.export_user_messages(db=db, user_id=user_id, format=format)

        if format == "json":
            return {
                "format": "json",
                "data": export_data,
                "total_messages": (len(export_data) if isinstance(export_data, list) else 0),
            }
        else:  # CSV
            return {"format": "csv", "data": export_data, "content_type": "text/csv"}
    except Exception as e:
        logger.error(f"Failed to export messages for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to export messages") from e
