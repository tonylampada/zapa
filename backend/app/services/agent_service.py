"""Agent Service for orchestrating LLM interactions."""

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.adapters.llm.agent import create_agent
from app.config.encryption import decrypt_api_key
from app.services.llm_tools import LLMTools
from app.services.message_service import MessageService
from app.models import LLMConfig, User
from app.schemas.agent import AgentRequest, AgentResponse, LLMResponse, ToolCall
from app.schemas.message import MessageCreate, MessageDirection, MessageType

logger = logging.getLogger(__name__)


class AgentService:
    """Service for processing messages through AI agents."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.message_service = MessageService(db)

    async def process_message(self, user_id: int, message_content: str) -> AgentResponse:
        """
        Process a user message and generate an AI response.

        1. Store the incoming message
        2. Load user's LLM configuration
        3. Get conversation context
        4. Call LLM with tools
        5. Execute any tool calls
        6. Store and return response
        """
        try:
            # Store incoming message
            await self._store_incoming_message(user_id, message_content)

            # Load user LLM config
            llm_config = await self._get_user_llm_config(user_id)
            if not llm_config:
                return self._create_error_response("LLM configuration not found")

            # Get conversation context
            context = await self._build_conversation_context(user_id)

            # Initialize LLM tools
            tools = LLMTools(user_id, self.message_service)

            # Create agent with user's configuration
            model_settings = llm_config.model_settings or {}
            agent = create_agent(
                provider=llm_config.provider,
                api_key=decrypt_api_key(llm_config.api_key_encrypted.encode()),
                model=model_settings.get("model", "gpt-4o"),
                temperature=model_settings.get("temperature", 0.7),
            )

            # Update agent with custom instructions if available
            if "custom_instructions" in model_settings:
                agent.update_instructions(model_settings["custom_instructions"])

            # Process message with agent
            response_content = await agent.process_message(
                message=message_content,
                db_session=self.db,
                user_id=user_id,
                conversation_history=context,
            )

            # Store outgoing message
            await self._store_outgoing_message(user_id, response_content)

            return AgentResponse(
                content=response_content,
                success=True,
                metadata={
                    "provider": llm_config.provider,
                    "model": model_settings.get("model", "gpt-4o"),
                },
            )

        except Exception as e:
            logger.error(f"Error processing message for user {user_id}: {e}")
            return self._create_error_response(f"Failed to process message: {str(e)}")

    async def _store_incoming_message(self, user_id: int, content: str) -> None:
        """Store incoming user message."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        message_data = MessageCreate(
            content=content,
            direction=MessageDirection.INCOMING,
            message_type=MessageType.TEXT,
        )

        await self.message_service.store_message(user_id, message_data)

    async def _store_outgoing_message(self, user_id: int, content: str) -> None:
        """Store outgoing AI message."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        message_data = MessageCreate(
            content=content,
            direction=MessageDirection.OUTGOING,
            message_type=MessageType.TEXT,
        )

        await self.message_service.store_message(user_id, message_data)

    async def _get_user_llm_config(self, user_id: int) -> Optional[LLMConfig]:
        """Get user's LLM configuration."""
        return (
            self.db.query(LLMConfig)
            .filter(LLMConfig.user_id == user_id, LLMConfig.is_active == True)
            .first()
        )

    async def _build_conversation_context(
        self, user_id: int, max_messages: int = 20
    ) -> List[Dict[str, str]]:
        """Build conversation context from recent messages."""
        recent_messages = await self.message_service.get_recent_messages(user_id, max_messages)

        context = []
        for msg in reversed(recent_messages):  # Oldest first
            if msg.direction == MessageDirection.INCOMING:
                role = "user"
            elif msg.direction == MessageDirection.OUTGOING:
                role = "assistant"
            else:
                continue  # Skip system messages

            context.append({"role": role, "content": msg.content})

        return context

    def _create_error_response(self, error_message: str) -> AgentResponse:
        """Create an error response."""
        return AgentResponse(
            content="I apologize, but I encountered an error processing your request.",
            success=False,
            error_message=error_message,
        )

    async def execute_tool_calls(
        self, tool_calls: List[ToolCall], tools: LLMTools
    ) -> List[Dict[str, Any]]:
        """Execute LLM tool calls and return results."""
        results = []

        for tool_call in tool_calls:
            try:
                result = await tools.execute_tool(tool_call.function_name, tool_call.arguments)
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": str(e)}),
                    }
                )

        return results
