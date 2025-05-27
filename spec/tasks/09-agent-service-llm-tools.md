# Task 09: Agent Service with LLM Tools

**Dependencies**: Task 08 (Message Service and Storage)
**Estimated Time**: 3-4 hours
**CI Required**: ✅ All tests must pass

## Objective

Create the Agent Service that orchestrates LLM interactions with function calling tools to access conversation history. This is the core intelligence layer that processes user messages and generates responses using the configured LLM provider.

## Requirements

### Core Agent Functionality
- Process incoming user messages
- Load user's LLM configuration and API keys
- Call LLM with conversation context and available tools
- Handle LLM function calls to access message history
- Generate and return appropriate responses

### LLM Tools Implementation
- `search_messages(query: str, limit: int)` - Semantic search through conversation
- `get_recent_messages(count: int)` - Retrieve recent messages
- `summarize_chat(last_n: int)` - Generate conversation summary
- `extract_tasks()` - Extract to-do items from conversation
- `get_conversation_stats()` - Get message statistics

### Response Processing
- Parse LLM responses and function calls
- Execute requested tools with user context
- Format final response for WhatsApp delivery
- Handle errors gracefully with fallback responses

## Test Strategy

### Unit Tests (Always Run)
- Agent service methods with mocked dependencies
- Tool function execution with mocked message service
- LLM response parsing and error handling
- Function call validation and execution

### Integration Tests (Skippable)
- End-to-end message processing with real LLM
- Tool integration with real message database
- Error handling with actual API failures

## Files to Create

### Service Implementation
```
backend/app/services/agent_service.py
```

### LLM Tools
```
backend/app/services/llm_tools.py
```

### Schemas
```
backend/app/schemas/agent.py
```

### Tests
```
backend/tests/unit/services/test_agent_service.py
backend/tests/unit/services/test_llm_tools.py
backend/tests/integration/services/test_agent_integration.py
```

## Implementation Details

### Agent Service Class

```python
# backend/app/services/agent_service.py
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import json
import logging

from app.services.message_service import MessageService
from app.services.llm_tools import LLMTools
from app.adapters.llm.agent import create_agent
from app.models import User, LLMConfig
from app.schemas.agent import (
    AgentRequest, AgentResponse, ToolCall, ToolResult
)

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, db: Session):
        self.db = db
        self.message_service = MessageService(db)
        self.llm_adapter_factory = LLMAdapterFactory()
    
    async def process_message(
        self, 
        user_id: int, 
        message_content: str
    ) -> AgentResponse:
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
            
            # Call LLM with tools
            llm_adapter = self.llm_adapter_factory.create_adapter(
                llm_config.provider,
                llm_config.api_key_decrypted
            )
            
            response = await llm_adapter.chat_with_tools(
                messages=context,
                tools=tools.get_tool_definitions(),
                model_settings=llm_config.model_settings
            )
            
            # Execute tool calls if any
            if response.tool_calls:
                tool_results = await self._execute_tool_calls(
                    response.tool_calls, 
                    tools
                )
                
                # Call LLM again with tool results
                response = await llm_adapter.chat_with_tools(
                    messages=context + [response.message] + tool_results,
                    tools=tools.get_tool_definitions(),
                    model_settings=llm_config.model_settings
                )
            
            # Store outgoing message
            await self._store_outgoing_message(user_id, response.content)
            
            return AgentResponse(
                content=response.content,
                success=True,
                metadata={"tool_calls_executed": len(response.tool_calls or [])}
            )
            
        except Exception as e:
            logger.error(f"Error processing message for user {user_id}: {e}")
            return self._create_error_response("Failed to process message")
    
    async def _execute_tool_calls(
        self, 
        tool_calls: List[ToolCall], 
        tools: LLMTools
    ) -> List[Dict[str, Any]]:
        """Execute LLM tool calls and return results."""
        results = []
        
        for tool_call in tool_calls:
            try:
                result = await tools.execute_tool(
                    tool_call.function_name,
                    tool_call.arguments
                )
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                results.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": str(e)})
                })
        
        return results
```

### LLM Tools Implementation

```python
# backend/app/services/llm_tools.py
from typing import Dict, Any, List, Callable
import json
from datetime import datetime, timedelta

from app.services.message_service import MessageService


class LLMTools:
    def __init__(self, user_id: int, message_service: MessageService):
        self.user_id = user_id
        self.message_service = message_service
        
        # Map tool names to methods
        self.tools: Dict[str, Callable] = {
            "search_messages": self.search_messages,
            "get_recent_messages": self.get_recent_messages,
            "summarize_chat": self.summarize_chat,
            "extract_tasks": self.extract_tasks,
            "get_conversation_stats": self.get_conversation_stats,
        }
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
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
                                "description": "Search query for finding relevant messages"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
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
                                "default": 20
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_chat",
                    "description": "Generate a summary of recent conversation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "last_n": {
                                "type": "integer",
                                "description": "Number of recent messages to summarize",
                                "default": 20
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "extract_tasks",
                    "description": "Extract potential tasks or to-dos from the conversation",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_conversation_stats",
                    "description": "Get statistics about the conversation",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name with given arguments."""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        tool_method = self.tools[tool_name]
        return await tool_method(**arguments)
    
    async def search_messages(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search through conversation history."""
        messages = await self.message_service.search_messages(
            self.user_id, query, limit
        )
        
        return [
            {
                "content": msg.content,
                "direction": msg.direction,
                "timestamp": msg.created_at.isoformat(),
                "message_id": msg.id
            }
            for msg in messages
        ]
    
    async def get_recent_messages(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get recent messages from conversation."""
        messages = await self.message_service.get_recent_messages(
            self.user_id, count
        )
        
        return [
            {
                "content": msg.content,
                "direction": msg.direction,
                "timestamp": msg.created_at.isoformat(),
                "message_id": msg.id
            }
            for msg in messages
        ]
    
    async def summarize_chat(self, last_n: int = 20) -> str:
        """Generate a summary of recent conversation."""
        summary = await self.message_service.summarize_conversation(
            self.user_id, last_n
        )
        return summary
    
    async def extract_tasks(self) -> List[Dict[str, Any]]:
        """Extract potential tasks from conversation."""
        tasks = await self.message_service.extract_tasks(self.user_id)
        
        return [
            {
                "content": task.content,
                "confidence": task.confidence_score,
                "from_message_id": task.extracted_from_message_id,
                "suggested_due_date": task.suggested_due_date.isoformat() if task.suggested_due_date else None
            }
            for task in tasks
        ]
    
    async def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        stats = await self.message_service.get_conversation_stats(self.user_id)
        
        return {
            "total_messages": stats.total_messages,
            "messages_sent": stats.messages_sent,
            "messages_received": stats.messages_received,
            "first_message_date": stats.first_message_date.isoformat() if stats.first_message_date else None,
            "last_message_date": stats.last_message_date.isoformat() if stats.last_message_date else None,
            "average_messages_per_day": stats.average_messages_per_day
        }
```

### Agent Schemas

```python
# backend/app/schemas/agent.py
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class AgentRequest(BaseModel):
    user_id: int
    message_content: str
    metadata: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    content: str
    success: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ToolCall(BaseModel):
    id: str
    function_name: str
    arguments: Dict[str, Any]


class ToolResult(BaseModel):
    tool_call_id: str
    result: Any
    error: Optional[str] = None


class LLMResponse(BaseModel):
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    message: Dict[str, Any]  # Full message object for context
```

## Acceptance Criteria

### Core Functionality
- [ ] Agent can process user messages end-to-end
- [ ] LLM configuration is loaded correctly for each user
- [ ] Function calling works with all tool definitions
- [ ] Tool execution results are passed back to LLM correctly
- [ ] Final responses are generated and stored

### Tool Integration
- [ ] All 5 LLM tools are implemented and functional
- [ ] Tool definitions match OpenAI function calling format
- [ ] Tool execution handles errors gracefully
- [ ] Tool results are properly formatted for LLM consumption

### Error Handling
- [ ] Missing LLM configuration is handled gracefully
- [ ] API errors from LLM providers are caught and logged
- [ ] Tool execution errors don't crash the agent
- [ ] Fallback responses are provided when LLM fails

### Performance
- [ ] Message processing completes within reasonable time (< 10s)
- [ ] Multiple tool calls are handled efficiently
- [ ] Database queries are optimized

### Testing
- [ ] Unit tests cover all agent methods
- [ ] Tool functions are thoroughly tested
- [ ] Integration tests verify end-to-end flow
- [ ] Error scenarios are tested

## Test Examples

### Unit Test Structure
```python
# backend/tests/unit/services/test_agent_service.py
import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.agent_service import AgentService
from app.schemas.agent import AgentResponse

class TestAgentService:
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def agent_service(self, mock_db):
        return AgentService(mock_db)
    
    async def test_process_message_success(self, agent_service):
        # Mock all dependencies and test successful processing
        pass
    
    async def test_process_message_no_llm_config(self, agent_service):
        # Test when user has no LLM configuration
        pass
    
    async def test_process_message_with_tool_calls(self, agent_service):
        # Test message processing that includes tool calls
        pass
```

## Next Steps

After completing this task:
1. Verify all tests pass in CI
2. Test agent functionality with mock LLM responses
3. Ensure tool execution works correctly
4. Move to Task 10: Admin API Endpoints

## Notes

- Focus on robust error handling - LLM APIs can be unreliable
- Ensure tool definitions are compatible with all LLM providers
- Keep tool execution lightweight and fast
- Log all LLM interactions for debugging purposes