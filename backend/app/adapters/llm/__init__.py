"""LLM adapter using OpenAI Agents SDK."""
from .agent import ZapaAgent, create_agent
from .tools import (
    extract_tasks,
    extract_tasks_impl,
    get_conversation_stats,
    get_conversation_stats_impl,
    get_recent_messages,
    get_recent_messages_impl,
    search_messages,
    # Implementation functions for testing
    search_messages_impl,
    summarize_chat,
    summarize_chat_impl,
)

__all__ = [
    "ZapaAgent",
    "create_agent",
    "search_messages",
    "get_recent_messages",
    "summarize_chat",
    "extract_tasks",
    "get_conversation_stats",
    # Implementation functions for testing
    "search_messages_impl",
    "get_recent_messages_impl",
    "summarize_chat_impl",
    "extract_tasks_impl",
    "get_conversation_stats_impl",
]
