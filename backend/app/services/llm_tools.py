"""LLM tools for accessing conversation history."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.services.message_service import MessageService


class LLMTools:
    """Tools available to LLM for accessing conversation data."""

    def __init__(self, user_id: int, message_service: MessageService):
        """Initialize with user context and message service."""
        self.user_id = user_id
        self.message_service = message_service

        # Map tool names to methods
        self.tools: dict[str, Callable] = {
            "search_messages": self.search_messages,
            "get_recent_messages": self.get_recent_messages,
            "get_messages_by_date_range": self.get_messages_by_date_range,
            "get_conversation_stats": self.get_conversation_stats,
        }

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool definitions for function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_messages",
                    "description": "Search through the user's conversation history",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for finding relevant messages",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 10,
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_recent_messages",
                    "description": "Get the most recent messages from the conversation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {
                                "type": "integer",
                                "description": "Number of recent messages to retrieve",
                                "default": 20,
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_messages_by_date_range",
                    "description": "Get messages within a specific date range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {
                                "type": "string",
                                "description": "Start date in ISO format (YYYY-MM-DD)",
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date in ISO format (YYYY-MM-DD)",
                            },
                        },
                        "required": ["start_date", "end_date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_conversation_stats",
                    "description": "Get statistics about the conversation",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name with given arguments."""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_method = self.tools[tool_name]
        return await tool_method(**arguments)

    async def search_messages(
        self, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Search through conversation history."""
        messages = await self.message_service.search_messages(
            self.user_id, query, limit
        )

        return [
            {
                "content": msg.content,
                "direction": msg.direction,
                "timestamp": msg.created_at.isoformat(),
                "message_id": msg.id,
            }
            for msg in messages
        ]

    async def get_recent_messages(self, count: int = 20) -> list[dict[str, Any]]:
        """Get recent messages from conversation."""
        messages = await self.message_service.get_recent_messages(self.user_id, count)

        return [
            {
                "content": msg.content,
                "direction": msg.direction,
                "timestamp": msg.created_at.isoformat(),
                "message_id": msg.id,
            }
            for msg in messages
        ]

    async def get_messages_by_date_range(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Get messages within a specific date range."""
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        messages = await self.message_service.get_messages_by_date_range(
            self.user_id, start, end
        )

        return [
            {
                "content": msg.content,
                "direction": msg.direction,
                "timestamp": msg.created_at.isoformat(),
                "message_id": msg.id,
            }
            for msg in messages
        ]

    async def get_conversation_stats(self) -> dict[str, Any]:
        """Get conversation statistics."""
        stats = await self.message_service.get_conversation_stats(self.user_id)

        return {
            "total_messages": stats.total_messages,
            "messages_sent": stats.messages_sent,
            "messages_received": stats.messages_received,
            "first_message_date": (
                stats.first_message_date.isoformat()
                if stats.first_message_date
                else None
            ),
            "last_message_date": (
                stats.last_message_date.isoformat() if stats.last_message_date else None
            ),
            "average_messages_per_day": stats.average_messages_per_day,
        }
