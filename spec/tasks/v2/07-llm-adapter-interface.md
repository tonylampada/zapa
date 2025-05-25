# Task 07: LLM Adapter Interface and Implementations

## Objective
Create a unified LLM adapter interface with implementations for OpenAI, Anthropic, and Google, including comprehensive unit tests and skippable integration tests.

## Prerequisites
- Tasks 01-06 completed
- WhatsApp Bridge adapter working
- All previous tests passing in CI/CD

## Success Criteria
- [ ] Abstract LLM adapter interface defined
- [ ] OpenAI, Anthropic, and Google implementations
- [ ] Function calling support for all providers
- [ ] Unit tests with mocked responses
- [ ] Integration tests (skippable by default)
- [ ] Error handling and retry logic
- [ ] Tests passing locally and in CI/CD

## Files to Create

### services/private/app/adapters/llm/__init__.py
```python
from .interface import LLMAdapter, LLMError, FunctionCall, Message
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .google_adapter import GoogleAdapter
from .factory import LLMAdapterFactory

__all__ = [
    "LLMAdapter",
    "LLMError", 
    "FunctionCall",
    "Message",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GoogleAdapter",
    "LLMAdapterFactory",
]
```

### services/private/app/adapters/llm/interface.py
```python
"""Abstract interface for LLM adapters."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


class Message(BaseModel):
    """Standardized message format across all LLM providers."""
    role: MessageRole
    content: str
    name: Optional[str] = None  # For function messages
    function_call: Optional[Dict[str, Any]] = None  # For assistant function calls


class FunctionDefinition(BaseModel):
    """Function definition for LLM function calling."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema


class FunctionCall(BaseModel):
    """Function call from LLM."""
    name: str
    arguments: Dict[str, Any]


class LLMError(Exception):
    """Base exception for LLM adapter errors."""
    
    def __init__(self, message: str, provider: str, original_error: Optional[Exception] = None):
        self.provider = provider
        self.original_error = original_error
        super().__init__(message)


class LLMAdapter(ABC):
    """Abstract base class for LLM adapters."""
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize LLM adapter.
        
        Args:
            api_key: API key for the LLM provider
            **kwargs: Provider-specific configuration
        """
        self.api_key = api_key
        self.config = kwargs
        self._client = None
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass
    
    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate a text completion.
        
        Args:
            messages: Conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters
            
        Returns:
            Generated text response
        """
        pass
    
    @abstractmethod
    async def complete_with_functions(
        self,
        messages: List[Message],
        functions: List[FunctionDefinition],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Union[str, FunctionCall]:
        """
        Generate completion with function calling support.
        
        Args:
            messages: Conversation messages
            functions: Available function definitions
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters
            
        Returns:
            Either text response or function call
        """
        pass
    
    @abstractmethod
    async def validate_api_key(self) -> bool:
        """
        Validate the API key.
        
        Returns:
            True if API key is valid
        """
        pass
    
    async def health_check(self) -> bool:
        """
        Check if the LLM service is available.
        
        Returns:
            True if service is healthy
        """
        try:
            return await self.validate_api_key()
        except Exception as e:
            logger.error(f"Health check failed for {self.provider_name}: {e}")
            return False
    
    def _standardize_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert standard messages to provider format.
        Override in subclasses for provider-specific formatting.
        
        Args:
            messages: Standard message format
            
        Returns:
            Provider-specific message format
        """
        return [msg.model_dump(exclude_none=True) for msg in messages]
    
    def _extract_function_call(self, response: Dict[str, Any]) -> Optional[FunctionCall]:
        """
        Extract function call from provider response.
        Override in subclasses for provider-specific extraction.
        
        Args:
            response: Provider response
            
        Returns:
            Function call if present
        """
        return None
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if hasattr(self._client, 'close'):
            await self._client.close()
```

### services/private/app/adapters/llm/openai_adapter.py
```python
"""OpenAI LLM adapter."""
import json
from typing import List, Dict, Any, Optional, Union
import httpx
import logging

from .interface import LLMAdapter, LLMError, Message, FunctionDefinition, FunctionCall, MessageRole

logger = logging.getLogger(__name__)


class OpenAIAdapter(LLMAdapter):
    """OpenAI LLM adapter."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        **kwargs
    ):
        super().__init__(api_key, **kwargs)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        return self._client
    
    async def complete(
        self,
        messages: List[Message],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text completion using OpenAI API."""
        try:
            payload = {
                "model": self.model,
                "messages": self._standardize_messages(messages),
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature
            
            # Add any provider-specific kwargs
            payload.update(kwargs)
            
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except httpx.HTTPStatusError as e:
            error_msg = f"OpenAI API error: {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg = "Invalid OpenAI API key"
            elif e.response.status_code == 429:
                error_msg = "OpenAI rate limit exceeded"
            raise LLMError(error_msg, self.provider_name, e)
        except Exception as e:
            raise LLMError(f"OpenAI request failed: {str(e)}", self.provider_name, e)
    
    async def complete_with_functions(
        self,
        messages: List[Message],
        functions: List[FunctionDefinition],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Union[str, FunctionCall]:
        """Generate completion with function calling support."""
        try:
            payload = {
                "model": self.model,
                "messages": self._standardize_messages(messages),
                "functions": [self._format_function(func) for func in functions],
                "function_call": "auto",
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature
            
            payload.update(kwargs)
            
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            
            result = response.json()
            choice = result["choices"][0]
            message = choice["message"]
            
            # Check if function was called
            if "function_call" in message:
                func_call = message["function_call"]
                return FunctionCall(
                    name=func_call["name"],
                    arguments=json.loads(func_call["arguments"])
                )
            else:
                return message["content"]
                
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid function arguments from OpenAI: {str(e)}", self.provider_name, e)
        except httpx.HTTPStatusError as e:
            error_msg = f"OpenAI API error: {e.response.status_code}"
            raise LLMError(error_msg, self.provider_name, e)
        except Exception as e:
            raise LLMError(f"OpenAI function call failed: {str(e)}", self.provider_name, e)
    
    async def validate_api_key(self) -> bool:
        """Validate OpenAI API key."""
        try:
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception:
            return False
    
    def _format_function(self, func: FunctionDefinition) -> Dict[str, Any]:
        """Format function for OpenAI API."""
        return {
            "name": func.name,
            "description": func.description,
            "parameters": func.parameters,
        }
    
    def _standardize_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert messages to OpenAI format."""
        formatted = []
        for msg in messages:
            formatted_msg = {
                "role": msg.role.value,
                "content": msg.content,
            }
            if msg.name:
                formatted_msg["name"] = msg.name
            if msg.function_call:
                formatted_msg["function_call"] = msg.function_call
            formatted.append(formatted_msg)
        return formatted
```

### services/private/app/adapters/llm/anthropic_adapter.py
```python
"""Anthropic Claude LLM adapter."""
import json
from typing import List, Dict, Any, Optional, Union
import httpx
import logging

from .interface import LLMAdapter, LLMError, Message, FunctionDefinition, FunctionCall, MessageRole

logger = logging.getLogger(__name__)


class AnthropicAdapter(LLMAdapter):
    """Anthropic Claude LLM adapter."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        base_url: str = "https://api.anthropic.com",
        timeout: float = 60.0,
        **kwargs
    ):
        super().__init__(api_key, **kwargs)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                timeout=self.timeout,
            )
        return self._client
    
    async def complete(
        self,
        messages: List[Message],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text completion using Anthropic API."""
        try:
            # Convert messages to Anthropic format
            system_message, formatted_messages = self._format_messages(messages)
            
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "max_tokens": max_tokens or 1000,
            }
            
            if system_message:
                payload["system"] = system_message
            if temperature is not None:
                payload["temperature"] = temperature
            
            payload.update(kwargs)
            
            response = await self.client.post("/v1/messages", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result["content"][0]["text"]
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Anthropic API error: {e.response.status_code}"
            if e.response.status_code == 401:
                error_msg = "Invalid Anthropic API key"
            elif e.response.status_code == 429:
                error_msg = "Anthropic rate limit exceeded"
            raise LLMError(error_msg, self.provider_name, e)
        except Exception as e:
            raise LLMError(f"Anthropic request failed: {str(e)}", self.provider_name, e)
    
    async def complete_with_functions(
        self,
        messages: List[Message],
        functions: List[FunctionDefinition],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Union[str, FunctionCall]:
        """
        Generate completion with function calling support.
        
        Note: Anthropic doesn't have native function calling, so we simulate it
        by including function definitions in the system prompt and parsing responses.
        """
        try:
            # Add function definitions to system message
            system_message, formatted_messages = self._format_messages(messages)
            function_prompt = self._create_function_prompt(functions)
            
            if system_message:
                system_message = f"{system_message}\n\n{function_prompt}"
            else:
                system_message = function_prompt
            
            payload = {
                "model": self.model,
                "messages": formatted_messages,
                "system": system_message,
                "max_tokens": max_tokens or 1000,
            }
            
            if temperature is not None:
                payload["temperature"] = temperature
            
            payload.update(kwargs)
            
            response = await self.client.post("/v1/messages", json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result["content"][0]["text"]
            
            # Try to parse function call from response
            function_call = self._parse_function_call(content)
            if function_call:
                return function_call
            else:
                return content
                
        except httpx.HTTPStatusError as e:
            error_msg = f"Anthropic API error: {e.response.status_code}"
            raise LLMError(error_msg, self.provider_name, e)
        except Exception as e:
            raise LLMError(f"Anthropic function call failed: {str(e)}", self.provider_name, e)
    
    async def validate_api_key(self) -> bool:
        """Validate Anthropic API key."""
        try:
            # Make a minimal request to test the key
            payload = {
                "model": "claude-3-haiku-20240307",
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 1,
            }
            response = await self.client.post("/v1/messages", json=payload)
            return response.status_code == 200
        except Exception:
            return False
    
    def _format_messages(self, messages: List[Message]) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Format messages for Anthropic API.
        
        Returns:
            Tuple of (system_message, formatted_messages)
        """
        system_message = None
        formatted_messages = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_message = msg.content
            elif msg.role in [MessageRole.USER, MessageRole.ASSISTANT]:
                formatted_messages.append({
                    "role": msg.role.value,
                    "content": msg.content,
                })
            # Skip function messages as Anthropic doesn't support them natively
        
        return system_message, formatted_messages
    
    def _create_function_prompt(self, functions: List[FunctionDefinition]) -> str:
        """Create function calling prompt for Anthropic."""
        prompt = "You have access to the following functions:\n\n"
        
        for func in functions:
            prompt += f"Function: {func.name}\n"
            prompt += f"Description: {func.description}\n"
            prompt += f"Parameters: {json.dumps(func.parameters, indent=2)}\n\n"
        
        prompt += (
            "To call a function, respond with a JSON object in this exact format:\n"
            '{"function_call": {"name": "function_name", "arguments": {...}}}\n\n'
            "If you don't need to call a function, respond normally."
        )
        
        return prompt
    
    def _parse_function_call(self, content: str) -> Optional[FunctionCall]:
        """Parse function call from Anthropic response."""
        try:
            # Look for JSON function call in response
            if '{"function_call":' in content:
                start = content.find('{"function_call":')
                end = content.find('}', start)
                if end != -1:
                    end = content.find('}', end + 1) + 1  # Find the closing brace
                    json_str = content[start:end]
                    parsed = json.loads(json_str)
                    
                    if "function_call" in parsed:
                        func_data = parsed["function_call"]
                        return FunctionCall(
                            name=func_data["name"],
                            arguments=func_data["arguments"]
                        )
        except (json.JSONDecodeError, KeyError):
            pass
        
        return None
```

### services/private/app/adapters/llm/google_adapter.py
```python
"""Google AI (Gemini) LLM adapter."""
import json
from typing import List, Dict, Any, Optional, Union
import httpx
import logging

from .interface import LLMAdapter, LLMError, Message, FunctionDefinition, FunctionCall, MessageRole

logger = logging.getLogger(__name__)


class GoogleAdapter(LLMAdapter):
    """Google AI (Gemini) LLM adapter."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-pro",
        base_url: str = "https://generativelanguage.googleapis.com",
        timeout: float = 60.0,
        **kwargs
    ):
        super().__init__(api_key, **kwargs)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    @property
    def provider_name(self) -> str:
        return "google"
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client
    
    async def complete(
        self,
        messages: List[Message],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate text completion using Google AI API."""
        try:
            formatted_messages = self._format_messages(messages)
            
            payload = {
                "contents": formatted_messages,
                "generationConfig": {},
            }
            
            if max_tokens:
                payload["generationConfig"]["maxOutputTokens"] = max_tokens
            if temperature is not None:
                payload["generationConfig"]["temperature"] = temperature
            
            # Add API key as query parameter
            url = f"/v1beta/models/{self.model}:generateContent"
            params = {"key": self.api_key}
            
            response = await self.client.post(url, json=payload, params=params)
            response.raise_for_status()
            
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"]
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Google AI API error: {e.response.status_code}"
            if e.response.status_code == 400:
                error_msg = "Invalid Google AI API key or request"
            elif e.response.status_code == 429:
                error_msg = "Google AI rate limit exceeded"
            raise LLMError(error_msg, self.provider_name, e)
        except Exception as e:
            raise LLMError(f"Google AI request failed: {str(e)}", self.provider_name, e)
    
    async def complete_with_functions(
        self,
        messages: List[Message],
        functions: List[FunctionDefinition],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Union[str, FunctionCall]:
        """
        Generate completion with function calling support.
        
        Note: Using function calling pattern similar to Anthropic since
        Google AI's function calling implementation varies.
        """
        try:
            # Add function information to the conversation
            system_prompt = self._create_function_prompt(functions)
            messages_with_functions = [
                Message(role=MessageRole.USER, content=system_prompt)
            ] + messages
            
            formatted_messages = self._format_messages(messages_with_functions)
            
            payload = {
                "contents": formatted_messages,
                "generationConfig": {},
            }
            
            if max_tokens:
                payload["generationConfig"]["maxOutputTokens"] = max_tokens
            if temperature is not None:
                payload["generationConfig"]["temperature"] = temperature
            
            url = f"/v1beta/models/{self.model}:generateContent"
            params = {"key": self.api_key}
            
            response = await self.client.post(url, json=payload, params=params)
            response.raise_for_status()
            
            result = response.json()
            content = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Try to parse function call from response
            function_call = self._parse_function_call(content)
            if function_call:
                return function_call
            else:
                return content
                
        except httpx.HTTPStatusError as e:
            error_msg = f"Google AI API error: {e.response.status_code}"
            raise LLMError(error_msg, self.provider_name, e)
        except Exception as e:
            raise LLMError(f"Google AI function call failed: {str(e)}", self.provider_name, e)
    
    async def validate_api_key(self) -> bool:
        """Validate Google AI API key."""
        try:
            payload = {
                "contents": [{"parts": [{"text": "Hi"}]}],
                "generationConfig": {"maxOutputTokens": 1},
            }
            
            url = f"/v1beta/models/{self.model}:generateContent"
            params = {"key": self.api_key}
            
            response = await self.client.post(url, json=payload, params=params)
            return response.status_code == 200
        except Exception:
            return False
    
    def _format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Format messages for Google AI API."""
        formatted_messages = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Google AI doesn't have system role, add as user message
                formatted_messages.append({
                    "role": "user",
                    "parts": [{"text": f"System: {msg.content}"}]
                })
            elif msg.role == MessageRole.USER:
                formatted_messages.append({
                    "role": "user",
                    "parts": [{"text": msg.content}]
                })
            elif msg.role == MessageRole.ASSISTANT:
                formatted_messages.append({
                    "role": "model",
                    "parts": [{"text": msg.content}]
                })
            # Skip function messages
        
        return formatted_messages
    
    def _create_function_prompt(self, functions: List[FunctionDefinition]) -> str:
        """Create function calling prompt for Google AI."""
        prompt = "You have access to the following functions:\n\n"
        
        for func in functions:
            prompt += f"Function: {func.name}\n"
            prompt += f"Description: {func.description}\n"
            prompt += f"Parameters: {json.dumps(func.parameters, indent=2)}\n\n"
        
        prompt += (
            "To call a function, respond with a JSON object in this exact format:\n"
            '{"function_call": {"name": "function_name", "arguments": {...}}}\n\n'
            "If you don't need to call a function, respond normally."
        )
        
        return prompt
    
    def _parse_function_call(self, content: str) -> Optional[FunctionCall]:
        """Parse function call from Google AI response."""
        try:
            # Look for JSON function call in response
            if '{"function_call":' in content:
                start = content.find('{"function_call":')
                end = content.find('}', start)
                if end != -1:
                    end = content.find('}', end + 1) + 1
                    json_str = content[start:end]
                    parsed = json.loads(json_str)
                    
                    if "function_call" in parsed:
                        func_data = parsed["function_call"]
                        return FunctionCall(
                            name=func_data["name"],
                            arguments=func_data["arguments"]
                        )
        except (json.JSONDecodeError, KeyError):
            pass
        
        return None
```

### services/private/app/adapters/llm/factory.py
```python
"""Factory for creating LLM adapters."""
from typing import Dict, Type, Any
from zapa_shared.models.llm_config import LLMProvider

from .interface import LLMAdapter
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .google_adapter import GoogleAdapter


class LLMAdapterFactory:
    """Factory for creating LLM adapters."""
    
    _adapters: Dict[LLMProvider, Type[LLMAdapter]] = {
        LLMProvider.OPENAI: OpenAIAdapter,
        LLMProvider.ANTHROPIC: AnthropicAdapter,
        LLMProvider.GOOGLE: GoogleAdapter,
    }
    
    @classmethod
    def create_adapter(
        self,
        provider: LLMProvider,
        api_key: str,
        model_settings: Dict[str, Any],
    ) -> LLMAdapter:
        """
        Create an LLM adapter instance.
        
        Args:
            provider: LLM provider type
            api_key: API key for the provider
            model_settings: Provider-specific settings
            
        Returns:
            LLM adapter instance
            
        Raises:
            ValueError: If provider is not supported
        """
        if provider not in self._adapters:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        
        adapter_class = self._adapters[provider]
        return adapter_class(api_key=api_key, **model_settings)
    
    @classmethod
    def get_supported_providers(cls) -> list[LLMProvider]:
        """Get list of supported providers."""
        return list(cls._adapters.keys())
    
    @classmethod
    def register_adapter(cls, provider: LLMProvider, adapter_class: Type[LLMAdapter]):
        """Register a new adapter class."""
        cls._adapters[provider] = adapter_class
```

### services/private/tests/adapters/llm/test_interface.py
```python
"""Tests for LLM adapter interface."""
import pytest
from datetime import datetime

from app.adapters.llm.interface import (
    Message, MessageRole, FunctionDefinition, FunctionCall, LLMAdapter, LLMError
)


def test_message_model():
    """Test Message model validation."""
    # Basic message
    msg = Message(role=MessageRole.USER, content="Hello")
    assert msg.role == MessageRole.USER
    assert msg.content == "Hello"
    assert msg.name is None
    assert msg.function_call is None
    
    # System message
    system_msg = Message(role=MessageRole.SYSTEM, content="You are helpful")
    assert system_msg.role == MessageRole.SYSTEM
    
    # Function message
    func_msg = Message(
        role=MessageRole.FUNCTION,
        content="Result: success",
        name="search_messages"
    )
    assert func_msg.name == "search_messages"


def test_function_definition():
    """Test FunctionDefinition model."""
    func_def = FunctionDefinition(
        name="search_messages",
        description="Search through messages",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
    )
    
    assert func_def.name == "search_messages"
    assert func_def.parameters["type"] == "object"
    assert "query" in func_def.parameters["required"]


def test_function_call():
    """Test FunctionCall model."""
    call = FunctionCall(
        name="search_messages",
        arguments={"query": "hello", "limit": 5}
    )
    
    assert call.name == "search_messages"
    assert call.arguments["query"] == "hello"
    assert call.arguments["limit"] == 5


def test_llm_error():
    """Test LLMError exception."""
    original = ValueError("Original error")
    error = LLMError("Test error", "openai", original)
    
    assert str(error) == "Test error"
    assert error.provider == "openai"
    assert error.original_error == original


class MockLLMAdapter(LLMAdapter):
    """Mock adapter for testing interface."""
    
    @property
    def provider_name(self) -> str:
        return "mock"
    
    async def complete(self, messages, max_tokens=None, temperature=None, **kwargs):
        return "Mock response"
    
    async def complete_with_functions(self, messages, functions, max_tokens=None, temperature=None, **kwargs):
        return "Mock function response"
    
    async def validate_api_key(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_llm_adapter_interface():
    """Test LLM adapter interface methods."""
    adapter = MockLLMAdapter("test-key")
    
    assert adapter.api_key == "test-key"
    assert adapter.provider_name == "mock"
    
    # Test complete method
    messages = [Message(role=MessageRole.USER, content="Hello")]
    response = await adapter.complete(messages)
    assert response == "Mock response"
    
    # Test health check
    health = await adapter.health_check()
    assert health is True


@pytest.mark.asyncio
async def test_llm_adapter_context_manager():
    """Test async context manager."""
    async with MockLLMAdapter("test-key") as adapter:
        assert adapter.provider_name == "mock"


def test_message_role_enum():
    """Test MessageRole enum values."""
    assert MessageRole.SYSTEM.value == "system"
    assert MessageRole.USER.value == "user"
    assert MessageRole.ASSISTANT.value == "assistant"
    assert MessageRole.FUNCTION.value == "function"


def test_standardize_messages():
    """Test message standardization."""
    adapter = MockLLMAdapter("test-key")
    
    messages = [
        Message(role=MessageRole.SYSTEM, content="System prompt"),
        Message(role=MessageRole.USER, content="User message"),
        Message(role=MessageRole.ASSISTANT, content="Assistant response"),
    ]
    
    standardized = adapter._standardize_messages(messages)
    
    assert len(standardized) == 3
    assert standardized[0]["role"] == "system"
    assert standardized[0]["content"] == "System prompt"
    assert standardized[1]["role"] == "user"
    assert standardized[2]["role"] == "assistant"
```

### services/private/tests/adapters/llm/test_openai_unit.py
```python
"""Unit tests for OpenAI adapter."""
import pytest
from unittest.mock import patch, AsyncMock
import httpx
import json

from app.adapters.llm.openai_adapter import OpenAIAdapter
from app.adapters.llm.interface import Message, MessageRole, FunctionDefinition, FunctionCall, LLMError


@pytest.fixture
def openai_adapter():
    """Create OpenAI adapter for testing."""
    return OpenAIAdapter(
        api_key="test-api-key",
        model="gpt-4",
        timeout=30.0
    )


@pytest.fixture
def mock_response():
    """Create mock HTTP response."""
    def _mock_response(json_data=None, status_code=200):
        response = AsyncMock()
        response.json.return_value = json_data or {}
        response.status_code = status_code
        response.raise_for_status = AsyncMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Error", request=None, response=response
            )
        return response
    return _mock_response


@pytest.mark.asyncio
async def test_openai_complete_success(openai_adapter, mock_response):
    """Test successful completion."""
    with patch.object(openai_adapter, 'client') as mock_client:
        mock_client.post.return_value = mock_response({
            "choices": [{
                "message": {"content": "Hello! How can I help you?"}
            }]
        })
        
        messages = [Message(role=MessageRole.USER, content="Hello")]
        response = await openai_adapter.complete(messages)
        
        assert response == "Hello! How can I help you?"
        
        # Verify API call
        mock_client.post.assert_called_once_with(
            "/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}]
            }
        )


@pytest.mark.asyncio
async def test_openai_complete_with_parameters(openai_adapter, mock_response):
    """Test completion with parameters."""
    with patch.object(openai_adapter, 'client') as mock_client:
        mock_client.post.return_value = mock_response({
            "choices": [{"message": {"content": "Response"}}]
        })
        
        messages = [Message(role=MessageRole.USER, content="Hello")]
        await openai_adapter.complete(
            messages,
            max_tokens=100,
            temperature=0.7,
            custom_param="test"
        )
        
        call_args = mock_client.post.call_args[1]["json"]
        assert call_args["max_tokens"] == 100
        assert call_args["temperature"] == 0.7
        assert call_args["custom_param"] == "test"


@pytest.mark.asyncio
async def test_openai_complete_with_functions(openai_adapter, mock_response):
    """Test completion with function calling."""
    with patch.object(openai_adapter, 'client') as mock_client:
        mock_client.post.return_value = mock_response({
            "choices": [{
                "message": {
                    "function_call": {
                        "name": "search_messages",
                        "arguments": '{"query": "hello", "limit": 5}'
                    }
                }
            }]
        })
        
        messages = [Message(role=MessageRole.USER, content="Search for hello")]
        functions = [FunctionDefinition(
            name="search_messages",
            description="Search messages",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["query"]
            }
        )]
        
        response = await openai_adapter.complete_with_functions(messages, functions)
        
        assert isinstance(response, FunctionCall)
        assert response.name == "search_messages"
        assert response.arguments["query"] == "hello"
        assert response.arguments["limit"] == 5


@pytest.mark.asyncio
async def test_openai_complete_with_functions_text_response(openai_adapter, mock_response):
    """Test function completion that returns text."""
    with patch.object(openai_adapter, 'client') as mock_client:
        mock_client.post.return_value = mock_response({
            "choices": [{
                "message": {"content": "I don't need to call any functions."}
            }]
        })
        
        messages = [Message(role=MessageRole.USER, content="Just say hello")]
        functions = [FunctionDefinition(
            name="search_messages",
            description="Search messages",
            parameters={"type": "object", "properties": {}}
        )]
        
        response = await openai_adapter.complete_with_functions(messages, functions)
        
        assert isinstance(response, str)
        assert response == "I don't need to call any functions."


@pytest.mark.asyncio
async def test_openai_api_error_handling(openai_adapter, mock_response):
    """Test API error handling."""
    with patch.object(openai_adapter, 'client') as mock_client:
        # Test 401 Unauthorized
        mock_client.post.return_value = mock_response(status_code=401)
        
        messages = [Message(role=MessageRole.USER, content="Hello")]
        
        with pytest.raises(LLMError) as exc_info:
            await openai_adapter.complete(messages)
        
        assert "Invalid OpenAI API key" in str(exc_info.value)
        assert exc_info.value.provider == "openai"


@pytest.mark.asyncio
async def test_openai_rate_limit_error(openai_adapter, mock_response):
    """Test rate limit error handling."""
    with patch.object(openai_adapter, 'client') as mock_client:
        mock_client.post.return_value = mock_response(status_code=429)
        
        messages = [Message(role=MessageRole.USER, content="Hello")]
        
        with pytest.raises(LLMError) as exc_info:
            await openai_adapter.complete(messages)
        
        assert "rate limit exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_openai_validate_api_key(openai_adapter, mock_response):
    """Test API key validation."""
    with patch.object(openai_adapter, 'client') as mock_client:
        # Valid key
        mock_client.get.return_value = mock_response({"data": []}, 200)
        assert await openai_adapter.validate_api_key() is True
        
        # Invalid key
        mock_client.get.return_value = mock_response(status_code=401)
        assert await openai_adapter.validate_api_key() is False


def test_openai_message_formatting(openai_adapter):
    """Test message formatting for OpenAI API."""
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are helpful"),
        Message(role=MessageRole.USER, content="Hello"),
        Message(role=MessageRole.ASSISTANT, content="Hi there!"),
        Message(role=MessageRole.FUNCTION, content="Result", name="search"),
    ]
    
    formatted = openai_adapter._standardize_messages(messages)
    
    assert len(formatted) == 4
    assert formatted[0]["role"] == "system"
    assert formatted[0]["content"] == "You are helpful"
    assert formatted[3]["name"] == "search"


def test_openai_function_formatting(openai_adapter):
    """Test function formatting for OpenAI API."""
    func_def = FunctionDefinition(
        name="test_function",
        description="A test function",
        parameters={"type": "object", "properties": {}}
    )
    
    formatted = openai_adapter._format_function(func_def)
    
    assert formatted["name"] == "test_function"
    assert formatted["description"] == "A test function"
    assert formatted["parameters"]["type"] == "object"


@pytest.mark.asyncio
async def test_openai_invalid_json_in_function_call(openai_adapter, mock_response):
    """Test handling of invalid JSON in function arguments."""
    with patch.object(openai_adapter, 'client') as mock_client:
        mock_client.post.return_value = mock_response({
            "choices": [{
                "message": {
                    "function_call": {
                        "name": "search_messages",
                        "arguments": "invalid json"
                    }
                }
            }]
        })
        
        messages = [Message(role=MessageRole.USER, content="Search")]
        functions = [FunctionDefinition(
            name="search_messages",
            description="Search",
            parameters={"type": "object"}
        )]
        
        with pytest.raises(LLMError) as exc_info:
            await openai_adapter.complete_with_functions(messages, functions)
        
        assert "Invalid function arguments" in str(exc_info.value)


def test_openai_provider_name(openai_adapter):
    """Test provider name."""
    assert openai_adapter.provider_name == "openai"


def test_openai_client_initialization(openai_adapter):
    """Test HTTP client initialization."""
    client = openai_adapter.client
    
    assert client.base_url == "https://api.openai.com/v1"
    assert client.headers["Authorization"] == "Bearer test-api-key"
    assert client.headers["Content-Type"] == "application/json"
```

## Integration Tests (Skippable)

### services/private/tests/adapters/llm/test_openai_integration.py
```python
"""Integration tests for OpenAI adapter."""
import pytest
import os

from app.adapters.llm.openai_adapter import OpenAIAdapter
from app.adapters.llm.interface import Message, MessageRole, FunctionDefinition

# Skip integration tests by default
pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_OPENAI", "false").lower() != "true",
    reason="OpenAI integration tests disabled. Set INTEGRATION_TEST_OPENAI=true to run."
)


@pytest.fixture
async def openai_adapter():
    """Create real OpenAI adapter."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    
    return OpenAIAdapter(api_key=api_key, model="gpt-3.5-turbo")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_openai_completion(openai_adapter):
    """Test real OpenAI completion."""
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Say hello in exactly 3 words.")
    ]
    
    response = await openai_adapter.complete(messages, max_tokens=50)
    
    assert isinstance(response, str)
    assert len(response) > 0
    # Should be roughly 3 words
    word_count = len(response.split())
    assert 2 <= word_count <= 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_openai_function_calling(openai_adapter):
    """Test real OpenAI function calling."""
    messages = [
        Message(role=MessageRole.USER, content="Get the weather for San Francisco")
    ]
    
    functions = [
        FunctionDefinition(
            name="get_weather",
            description="Get weather for a city",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["city"]
            }
        )
    ]
    
    response = await openai_adapter.complete_with_functions(messages, functions)
    
    # Should call the function
    from app.adapters.llm.interface import FunctionCall
    assert isinstance(response, FunctionCall)
    assert response.name == "get_weather"
    assert "city" in response.arguments
    assert "san francisco" in response.arguments["city"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_openai_api_key_validation(openai_adapter):
    """Test real API key validation."""
    # Valid key
    assert await openai_adapter.validate_api_key() is True
    
    # Invalid key
    invalid_adapter = OpenAIAdapter(api_key="invalid-key")
    assert await invalid_adapter.validate_api_key() is False
```

## Commands to Run

```bash
# Run unit tests only
cd services/private
uv run pytest tests/adapters/llm/test_interface.py -v
uv run pytest tests/adapters/llm/test_openai_unit.py -v

# Run integration tests (requires API keys)
INTEGRATION_TEST_OPENAI=true OPENAI_API_KEY=sk-... uv run pytest tests/adapters/llm/test_openai_integration.py -v
INTEGRATION_TEST_ANTHROPIC=true ANTHROPIC_API_KEY=sk-... uv run pytest tests/adapters/llm/test_anthropic_integration.py -v
INTEGRATION_TEST_GOOGLE=true GOOGLE_API_KEY=... uv run pytest tests/adapters/llm/test_google_integration.py -v

# Run all LLM adapter tests
uv run pytest tests/adapters/llm/ -v --cov=app.adapters.llm

# Test factory
uv run python -c "
from app.adapters.llm.factory import LLMAdapterFactory
from zapa_shared.models.llm_config import LLMProvider
adapter = LLMAdapterFactory.create_adapter(
    LLMProvider.OPENAI, 
    'test-key', 
    {'model': 'gpt-4'}
)
print(f'Created {adapter.provider_name} adapter')
"
```

## Verification

1. All three LLM adapters implement the interface correctly
2. Unit tests pass without any external API calls
3. Integration tests are skipped by default
4. Function calling works for all providers (with different implementations)
5. Error handling works for various failure scenarios
6. Factory creates correct adapter instances
7. Code coverage ≥ 90% from unit tests alone

## Next Steps

After LLM adapters are complete, proceed to Task 08: Message Service and Storage.