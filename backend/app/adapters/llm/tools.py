"""Agent tools for message operations."""

import logging
from datetime import datetime
from typing import Any

from agents import RunContextWrapper, function_tool
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message

logger = logging.getLogger(__name__)


class MessageSearchResult(BaseModel):
    """Result from message search."""

    message_id: int
    content: str
    sender: str
    timestamp: datetime
    relevance_score: float = Field(default=1.0)


class ChatSummary(BaseModel):
    """Summary of a chat conversation."""

    summary: str
    message_count: int
    date_range: dict[str, datetime]
    key_topics: list[str]


class ExtractedTask(BaseModel):
    """Task extracted from conversation."""

    task: str
    mentioned_at: datetime
    priority: str = Field(default="medium")
    completed: bool = Field(default=False)


class ConversationStats(BaseModel):
    """Statistics about a conversation."""

    total_messages: int
    user_messages: int
    assistant_messages: int
    date_range: dict[str, datetime]
    average_messages_per_day: float


async def search_messages_impl(
    ctx: RunContextWrapper[dict[str, Any]],
    query: str,
    limit: int = 10,
) -> list[MessageSearchResult]:
    """
    Search through the user's message history.

    Args:
        query: Search query to find relevant messages
        limit: Maximum number of results to return (default: 10)

    Returns:
        List of messages matching the search query
    """
    db: AsyncSession = ctx.context.get("db_session")
    user_id: int = ctx.context.get("user_id")

    if not db or not user_id:
        logger.error("Missing database session or user_id in context")
        return []

    try:
        # Simple text search - in production, use PostgreSQL full-text search
        stmt = (
            select(Message)
            .where(Message.user_id == user_id)
            .where(Message.content.ilike(f"%{query}%"))
            .order_by(desc(Message.created_at))
            .limit(limit)
        )

        result = await db.execute(stmt)
        messages = result.scalars().all()

        return [
            MessageSearchResult(
                message_id=msg.id,
                content=msg.content,
                sender="user" if msg.is_from_user else "assistant",
                timestamp=msg.created_at,
            )
            for msg in messages
        ]

    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        return []


# Apply decorator to create the tool
search_messages = function_tool(search_messages_impl)


async def get_recent_messages_impl(
    ctx: RunContextWrapper[dict[str, Any]],
    count: int = 20,
) -> list[MessageSearchResult]:
    """
    Get the most recent messages from the conversation.

    Args:
        count: Number of recent messages to retrieve (default: 20)

    Returns:
        List of recent messages in chronological order
    """
    db: AsyncSession = ctx.context.get("db_session")
    user_id: int = ctx.context.get("user_id")

    if not db or not user_id:
        logger.error("Missing database session or user_id in context")
        return []

    try:
        stmt = (
            select(Message)
            .where(Message.user_id == user_id)
            .order_by(desc(Message.created_at))
            .limit(count)
        )

        result = await db.execute(stmt)
        messages = result.scalars().all()

        # Reverse to get chronological order
        messages.reverse()

        return [
            MessageSearchResult(
                message_id=msg.id,
                content=msg.content,
                sender="user" if msg.is_from_user else "assistant",
                timestamp=msg.created_at,
            )
            for msg in messages
        ]

    except Exception as e:
        logger.error(f"Error getting recent messages: {e}")
        return []


# Apply decorator to create the tool
get_recent_messages = function_tool(get_recent_messages_impl)


async def summarize_chat_impl(
    ctx: RunContextWrapper[dict[str, Any]],
    last_n_messages: int = 50,
) -> ChatSummary:
    """
    Generate a summary of recent conversation.

    Args:
        last_n_messages: Number of recent messages to summarize (default: 50)

    Returns:
        Summary of the conversation including key topics
    """
    # Get recent messages
    messages = await get_recent_messages_impl(ctx, last_n_messages)

    if not messages:
        return ChatSummary(
            summary="No messages found to summarize.",
            message_count=0,
            date_range={},
            key_topics=[],
        )

    # Extract content for summary (could be used for more advanced summary)
    # conversation_text = "\n".join([f"{msg.sender}: {msg.content}" for msg in messages])

    # Simple summary (in production, use another LLM call)
    summary = f"Conversation between user and assistant covering {len(messages)} messages."

    # Extract date range
    date_range = {
        "start": messages[0].timestamp,
        "end": messages[-1].timestamp,
    }

    # Extract key topics (simple keyword extraction)
    # In production, use NLP techniques
    key_topics = ["general conversation"]

    return ChatSummary(
        summary=summary,
        message_count=len(messages),
        date_range=date_range,
        key_topics=key_topics,
    )


# Apply decorator to create the tool
summarize_chat = function_tool(summarize_chat_impl)


async def extract_tasks_impl(
    ctx: RunContextWrapper[dict[str, Any]],
    last_n_messages: int = 100,
) -> list[ExtractedTask]:
    """
    Extract actionable tasks mentioned in the conversation.

    Args:
        last_n_messages: Number of recent messages to analyze (default: 100)

    Returns:
        List of tasks mentioned in the conversation
    """
    messages = await get_recent_messages_impl(ctx, last_n_messages)

    tasks = []

    # Simple task extraction - look for action words
    # In production, use NLP or another LLM call
    action_keywords = [
        "todo",
        "task",
        "remind",
        "need to",
        "should",
        "must",
        "have to",
        "don't forget",
        "remember to",
    ]

    for msg in messages:
        content_lower = msg.content.lower()
        if any(keyword in content_lower for keyword in action_keywords):
            tasks.append(
                ExtractedTask(
                    task=msg.content[:100],  # First 100 chars
                    mentioned_at=msg.timestamp,
                    priority="medium",
                    completed=False,
                )
            )

    return tasks


# Apply decorator to create the tool
extract_tasks = function_tool(extract_tasks_impl)


async def get_conversation_stats_impl(
    ctx: RunContextWrapper[dict[str, Any]],
) -> ConversationStats:
    """
    Get statistics about the entire conversation history.

    Returns:
        Statistics including message counts and date ranges
    """
    db: AsyncSession = ctx.context.get("db_session")
    user_id: int = ctx.context.get("user_id")

    if not db or not user_id:
        logger.error("Missing database session or user_id in context")
        return ConversationStats(
            total_messages=0,
            user_messages=0,
            assistant_messages=0,
            date_range={},
            average_messages_per_day=0.0,
        )

    try:
        # Get total message count
        total_stmt = select(func.count(Message.id)).where(Message.user_id == user_id)
        total_result = await db.execute(total_stmt)
        total_messages = total_result.scalar() or 0

        # Get user message count
        user_stmt = (
            select(func.count(Message.id))
            .where(Message.user_id == user_id)
            .where(Message.is_from_user.is_(True))
        )
        user_result = await db.execute(user_stmt)
        user_messages = user_result.scalar() or 0

        # Get date range
        date_stmt = select(
            func.min(Message.created_at).label("first"),
            func.max(Message.created_at).label("last"),
        ).where(Message.user_id == user_id)
        date_result = await db.execute(date_stmt)
        date_row = date_result.one_or_none()

        if date_row and date_row.first and date_row.last:
            date_range = {
                "start": date_row.first,
                "end": date_row.last,
            }

            # Calculate average messages per day
            days_diff = (date_row.last - date_row.first).days + 1
            avg_per_day = total_messages / days_diff if days_diff > 0 else 0
        else:
            date_range = {}
            avg_per_day = 0.0

        return ConversationStats(
            total_messages=total_messages,
            user_messages=user_messages,
            assistant_messages=total_messages - user_messages,
            date_range=date_range,
            average_messages_per_day=avg_per_day,
        )

    except Exception as e:
        logger.error(f"Error getting conversation stats: {e}")
        return ConversationStats(
            total_messages=0,
            user_messages=0,
            assistant_messages=0,
            date_range={},
            average_messages_per_day=0.0,
        )


# Apply decorator to create the tool
get_conversation_stats = function_tool(get_conversation_stats_impl)
