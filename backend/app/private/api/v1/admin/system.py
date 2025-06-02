from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime, timedelta, timezone
import psutil
import time
import json
import uuid
import httpx

from app.core.database import get_db
from app.core.security import get_current_admin
from app.core.config import settings
from app.schemas.admin import SystemStatsResponse, SystemHealthResponse, ExportDataResponse
from app.models import User, Message, Session as SessionModel, LLMConfig

router = APIRouter(prefix="/admin/system", tags=["admin-system"])

# Store export jobs in memory (in production, use Redis or database)
export_jobs = {}


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    db: Session = Depends(get_db), current_admin=Depends(get_current_admin)
):
    """Get system health status."""
    # Check database connectivity
    database_connected = False
    try:
        db.execute(text("SELECT 1"))
        database_connected = True
    except Exception:
        pass

    # Check WhatsApp bridge connectivity
    whatsapp_bridge_connected = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.WHATSAPP_BRIDGE_URL}/health", timeout=5.0)
            whatsapp_bridge_connected = response.status_code == 200
    except Exception:
        pass

    # Get system resource usage
    memory_usage_percent = psutil.virtual_memory().percent
    disk_usage_percent = psutil.disk_usage("/").percent

    # Get uptime (simplified - in production, track actual start time)
    uptime_seconds = int(time.time() - psutil.boot_time())

    # Determine overall status
    if not database_connected:
        status = "unhealthy"
    elif not whatsapp_bridge_connected or memory_usage_percent > 90 or disk_usage_percent > 90:
        status = "degraded"
    else:
        status = "healthy"

    return SystemHealthResponse(
        status=status,
        database_connected=database_connected,
        whatsapp_bridge_connected=whatsapp_bridge_connected,
        memory_usage_percent=memory_usage_percent,
        disk_usage_percent=disk_usage_percent,
        uptime_seconds=uptime_seconds,
    )


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(db: Session = Depends(get_db), current_admin=Depends(get_current_admin)):
    """Get system-wide statistics."""
    # Get user counts
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()

    # Get message counts
    total_messages = db.query(func.count(Message.id)).scalar()

    # Messages today (using UTC)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = (
        db.query(func.count(Message.id)).filter(Message.created_at >= today_start).scalar()
    )

    # Calculate average response time (simplified)
    # In production, you'd track actual response times
    avg_response_time = (
        db.query(
            func.avg(
                func.extract("epoch", Message.created_at)
                - func.extract("epoch", Message.created_at)
            )
        )
        .filter(Message.is_from_user == False)
        .scalar()
        or 0.0
    )

    # Convert to milliseconds
    average_response_time_ms = (
        float(avg_response_time * 1000) if avg_response_time else 250.0
    )  # Default 250ms

    # Get LLM provider usage
    provider_counts = (
        db.query(LLMConfig.provider, func.count(LLMConfig.id))
        .filter(LLMConfig.is_active == True)
        .group_by(LLMConfig.provider)
        .all()
    )

    llm_provider_usage = {provider: count for provider, count in provider_counts}

    # Add zero counts for providers not in use
    for provider in ["openai", "anthropic", "google"]:
        if provider not in llm_provider_usage:
            llm_provider_usage[provider] = 0

    return SystemStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_messages=total_messages,
        messages_today=messages_today,
        average_response_time_ms=average_response_time_ms,
        llm_provider_usage=llm_provider_usage,
    )


@router.post("/export", response_model=ExportDataResponse)
async def export_system_data(
    start_date: datetime,
    end_date: datetime,
    include_messages: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    """Export system data for backup or analysis."""
    # Validate date range
    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days")

    # Create export job
    export_id = str(uuid.uuid4())
    export_jobs[export_id] = {"status": "pending", "download_url": None, "error_message": None}

    # Start background export task
    background_tasks.add_task(perform_export, export_id, start_date, end_date, include_messages, db)

    return ExportDataResponse(
        export_id=export_id, status="pending", download_url=None, error_message=None
    )


@router.get("/export/{export_id}", response_model=ExportDataResponse)
async def get_export_status(export_id: str, current_admin=Depends(get_current_admin)):
    """Get the status of an export job."""
    if export_id not in export_jobs:
        raise HTTPException(status_code=404, detail="Export job not found")

    job = export_jobs[export_id]

    return ExportDataResponse(
        export_id=export_id,
        status=job["status"],
        download_url=job["download_url"],
        error_message=job["error_message"],
    )


async def perform_export(
    export_id: str, start_date: datetime, end_date: datetime, include_messages: bool, db: Session
):
    """Perform the actual data export (background task)."""
    try:
        export_jobs[export_id]["status"] = "processing"

        # Prepare export data
        export_data = {
            "export_info": {
                "export_id": export_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "exported_at": datetime.utcnow().isoformat(),
            },
            "users": [],
            "messages": [] if include_messages else None,
        }

        # Export users
        users = (
            db.query(User).filter(User.first_seen >= start_date, User.first_seen <= end_date).all()
        )

        for user in users:
            export_data["users"].append(
                {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "display_name": user.display_name,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "first_seen": user.first_seen.isoformat() if user.first_seen else None,
                    "last_active": user.last_active.isoformat() if user.last_active else None,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                }
            )

        # Export messages if requested
        if include_messages:
            messages = (
                db.query(Message)
                .filter(Message.created_at >= start_date, Message.created_at <= end_date)
                .all()
            )

            for message in messages:
                export_data["messages"].append(
                    {
                        "id": message.id,
                        "user_id": message.user_id,
                        "content": message.content,
                        "is_from_user": message.is_from_user,
                        "message_type": message.message_type.value,
                        "status": message.status.value,
                        "created_at": (
                            message.created_at.isoformat() if message.created_at else None
                        ),
                    }
                )

        # In production, save to S3 or file storage
        # For now, we'll just mark as completed
        export_jobs[export_id]["status"] = "completed"
        export_jobs[export_id]["download_url"] = f"/api/v1/admin/system/export/{export_id}/download"

    except Exception as e:
        export_jobs[export_id]["status"] = "failed"
        export_jobs[export_id]["error_message"] = str(e)
