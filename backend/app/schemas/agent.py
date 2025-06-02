"""Agent schemas for AI service interactions."""

from typing import Any

from pydantic import BaseModel


class AgentRequest(BaseModel):
    """Request to process a message through the agent."""

    user_id: int
    message_content: str
    metadata: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    """Response from agent processing."""

    content: str
    success: bool
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


class ToolCall(BaseModel):
    """LLM tool call request."""

    id: str
    function_name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result from executing a tool call."""

    tool_call_id: str
    result: Any
    error: str | None = None


class LLMResponse(BaseModel):
    """Response from LLM including potential tool calls."""

    content: str
    tool_calls: list[ToolCall] | None = None
    message: dict[str, Any]  # Full message object for context
