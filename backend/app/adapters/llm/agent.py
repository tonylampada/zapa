"""Zapa Agent implementation using OpenAI Agents SDK."""
import logging
from typing import Optional

from agents import Agent, ModelSettings, OpenAIProvider, RunConfig, Runner
from sqlalchemy.ext.asyncio import AsyncSession

from .tools import (
    extract_tasks,
    get_conversation_stats,
    get_recent_messages,
    search_messages,
    summarize_chat,
)

logger = logging.getLogger(__name__)


class ZapaAgent:
    """WhatsApp agent with message history tools."""

    DEFAULT_INSTRUCTIONS = """You are a helpful WhatsApp assistant with access to the user's message history.

    You can:
    - Search through past messages
    - Retrieve recent conversations
    - Summarize chat history
    - Extract tasks from conversations
    - Provide conversation statistics

    Be conversational and helpful. When users ask about their message history, use the available tools to provide accurate information."""

    def __init__(
        self,
        name: str = "Zapa Assistant",
        instructions: Optional[str] = None,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize Zapa Agent.

        Args:
            name: Agent name
            instructions: Custom instructions (uses default if not provided)
            model: Model to use
            api_key: OpenAI API key (uses env var if not provided)
            base_url: Custom API base URL for OpenAI-compatible providers
            temperature: Sampling temperature
        """
        self.name = name
        self.instructions = instructions or self.DEFAULT_INSTRUCTIONS
        self.model = model
        self.temperature = temperature

        # Configure model provider if custom client needed
        self.model_provider = None
        if api_key or base_url:
            self.model_provider = OpenAIProvider(
                api_key=api_key,
                base_url=base_url,
            )

        # Create agent with tools
        self.agent = Agent(
            name=self.name,
            instructions=self.instructions,
            model=self.model,
            model_settings=ModelSettings(temperature=self.temperature),
            tools=[
                search_messages,
                get_recent_messages,
                summarize_chat,
                extract_tasks,
                get_conversation_stats,
            ],
        )

    async def process_message(
        self,
        message: str,
        db_session: AsyncSession,
        user_id: int,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """
        Process a user message and generate response.

        Args:
            message: User's message
            db_session: Database session for tools
            user_id: User ID for context
            conversation_history: Optional previous messages

        Returns:
            Agent's response
        """
        # Create context for tools
        context = {
            "db_session": db_session,
            "user_id": user_id,
        }

        # Build message list
        messages = []
        if conversation_history:
            for msg in conversation_history:
                messages.append(
                    {
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", ""),
                    }
                )

        # Add current message
        messages.append(
            {
                "role": "user",
                "content": message,
            }
        )

        try:
            # Create run config with custom provider if needed
            run_config = None
            if self.model_provider:
                run_config = RunConfig(model_provider=self.model_provider)

            # Run agent
            result = await Runner.run(
                self.agent,
                messages=messages,
                context=context,
                run_config=run_config,
            )

            return result.final_output

        except Exception as e:
            logger.error(f"Error processing message with agent: {e}")
            return (
                "I apologize, but I encountered an error processing your message. Please try again."
            )

    def update_instructions(self, instructions: str):
        """Update agent instructions."""
        self.instructions = instructions
        self.agent.instructions = instructions

    def update_model(self, model: str):
        """Update the model used by the agent."""
        self.model = model
        # Note: Agent model is immutable after creation in the SDK
        # To change model, you would need to recreate the agent


def create_agent(
    provider: str = "openai", api_key: str = None, model: str = None, **kwargs
) -> ZapaAgent:
    """
    Factory function to create agents for different providers.

    Args:
        provider: LLM provider (openai, anthropic, google, etc.)
        api_key: API key for the provider
        model: Model to use
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured ZapaAgent instance
    """
    # Provider-specific configurations
    provider_configs = {
        "openai": {
            "base_url": None,
            "model": model or "gpt-4o",
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "model": model or "claude-3-opus-20240229",
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "model": model or "gemini-pro",
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "model": model or "llama2",
        },
        # Add more providers as needed
    }

    config = provider_configs.get(provider, provider_configs["openai"])
    config.update(kwargs)

    return ZapaAgent(api_key=api_key, **config)
