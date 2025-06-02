"""Agent schemas for AI service interactions."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Request to process a message through the agent."""

    user_id: int
    message_content: str
    metadata: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    """Response from agent processing."""

    content: str
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ToolCall(BaseModel):
    """LLM tool call request."""

    id: str
    function_name: str
    arguments: Dict[str, Any]


class ToolResult(BaseModel):
    """Result from executing a tool call."""

    tool_call_id: str
    result: Any
    error: Optional[str] = None


class LLMResponse(BaseModel):
    """Response from LLM including potential tool calls."""

    content: str
    tool_calls: Optional[List[ToolCall]] = None
    message: Dict[str, Any]  # Full message object for context
