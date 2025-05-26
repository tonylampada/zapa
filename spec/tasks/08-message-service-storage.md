# Task 08: Message Service and Storage

**Dependencies**: Task 07 (LLM Adapter Interface)
**Estimated Time**: 2-3 hours
**CI Required**: ✅ All tests must pass

## Objective

Create the Message Service that handles storing, retrieving, and managing WhatsApp messages with semantic search capabilities. This service will be used by LLM tools to access conversation history.

## Requirements

### Core Message Operations
- Store incoming and outgoing messages
- Retrieve messages with pagination
- Search messages by content (text search initially, semantic later)
- Get conversation statistics
- Extract tasks/todos from messages

### Message Storage
- Store messages with proper metadata (timestamp, direction, user_id, etc.)
- Handle different message types (text, media, system messages)
- Efficient querying for conversation history

### Search Functionality
- Text-based search through message content
- Recent message retrieval
- Conversation summarization support
- Task extraction from messages

## Test Strategy

### Unit Tests (Always Run)
- Message storage and retrieval
- Search functionality with mocked data
- Pagination logic
- Statistics calculation
- Task extraction logic

### Integration Tests (Skippable)
- Database operations with real PostgreSQL
- Performance tests with large message volumes

## Files to Create

### Service Implementation
```
backend/zapa_private/app/services/message_service.py
```

### Schemas
```
backend/shared/app/schemas/message_schemas.py
```

### Tests
```
backend/zapa_private/tests/services/test_message_service.py
backend/zapa_private/tests/integration/test_message_integration.py
```

## Implementation Details

### MessageService Class

```python
# backend/zapa_private/app/services/message_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_

from shared.app.models.models import Message, User
from shared.app.schemas.message_schemas import (
    MessageCreate, MessageResponse, MessageSearchParams,
    ConversationStats, TaskItem
)


class MessageService:
    def __init__(self, db: Session):
        self.db = db
    
    async def store_message(
        self, 
        user_id: int, 
        message_data: MessageCreate
    ) -> MessageResponse:
        """Store a new message in the database."""
        pass
    
    async def get_recent_messages(
        self, 
        user_id: int, 
        count: int = 20
    ) -> List[MessageResponse]:
        """Get the N most recent messages for a user."""
        pass
    
    async def search_messages(
        self, 
        user_id: int, 
        query: str, 
        limit: int = 10
    ) -> List[MessageResponse]:
        """Search messages by content (text search)."""
        pass
    
    async def get_conversation_stats(
        self, 
        user_id: int
    ) -> ConversationStats:
        """Get statistics about the user's conversation."""
        pass
    
    async def extract_tasks(
        self, 
        user_id: int, 
        last_n: int = 50
    ) -> List[TaskItem]:
        """Extract potential tasks from recent messages."""
        pass
    
    async def summarize_conversation(
        self, 
        user_id: int, 
        last_n: int = 20
    ) -> str:
        """Generate a summary of recent messages."""
        pass
```

### Message Schemas

```python
# backend/shared/app/schemas/message_schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MessageDirection(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    SYSTEM = "system"

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"
    SYSTEM = "system"

class MessageCreate(BaseModel):
    content: str
    direction: MessageDirection
    message_type: MessageType = MessageType.TEXT
    whatsapp_message_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MessageResponse(BaseModel):
    id: int
    user_id: int
    content: str
    direction: MessageDirection
    message_type: MessageType
    whatsapp_message_id: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True

class MessageSearchParams(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

class ConversationStats(BaseModel):
    total_messages: int
    messages_sent: int
    messages_received: int
    first_message_date: Optional[datetime]
    last_message_date: Optional[datetime]
    average_messages_per_day: float

class TaskItem(BaseModel):
    content: str
    extracted_from_message_id: int
    confidence_score: float = Field(ge=0.0, le=1.0)
    suggested_due_date: Optional[datetime] = None
```

## Acceptance Criteria

### Core Functionality
- [ ] Messages can be stored with all required metadata
- [ ] Recent messages can be retrieved with pagination
- [ ] Text search works across message content
- [ ] Conversation statistics are calculated correctly
- [ ] Task extraction identifies potential todos from messages

### Data Integrity
- [ ] Messages are properly associated with users
- [ ] Timestamps are stored correctly in UTC
- [ ] WhatsApp message IDs are unique when provided
- [ ] Metadata is stored as valid JSON

### Performance
- [ ] Message retrieval is fast (< 100ms for 20 messages)
- [ ] Search is reasonably fast (< 500ms for text search)
- [ ] Database queries are optimized with proper indexes

### Testing
- [ ] Unit tests cover all service methods
- [ ] Integration tests verify database operations
- [ ] Error cases are properly handled and tested
- [ ] Performance tests validate response times

### Error Handling
- [ ] Invalid user_id returns appropriate error
- [ ] Empty search queries are handled gracefully
- [ ] Database connection errors are caught and logged
- [ ] Invalid message data is rejected with clear error messages

## Test Examples

### Unit Test Structure
```python
# backend/zapa_private/tests/services/test_message_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from app.services.message_service import MessageService
from shared.app.schemas.message_schemas import MessageCreate, MessageDirection

class TestMessageService:
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def message_service(self, mock_db):
        return MessageService(mock_db)
    
    async def test_store_message_success(self, message_service, mock_db):
        # Test successful message storage
        pass
    
    async def test_get_recent_messages(self, message_service, mock_db):
        # Test retrieving recent messages
        pass
    
    async def test_search_messages_text_query(self, message_service, mock_db):
        # Test text search functionality
        pass
    
    async def test_conversation_stats_calculation(self, message_service, mock_db):
        # Test stats calculation
        pass
    
    async def test_extract_tasks_from_messages(self, message_service, mock_db):
        # Test task extraction logic
        pass
```

### Integration Test Structure
```python
# backend/zapa_private/tests/integration/test_message_integration.py
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_DATABASE", "false").lower() != "true",
    reason="Database integration tests disabled. Set INTEGRATION_TEST_DATABASE=true to run."
)

class TestMessageIntegration:
    async def test_message_storage_and_retrieval(self, real_db_session):
        # Test with real database
        pass
    
    async def test_search_performance_large_dataset(self, real_db_session):
        # Performance test with many messages
        pass
```

## Next Steps

After completing this task:
1. Verify all tests pass in CI
2. Test message storage and retrieval manually
3. Ensure search functionality works correctly
4. Move to Task 09: Agent Service with LLM Tools

## Notes

- Start with simple text search; semantic search can be added later
- Focus on correctness first, then optimize for performance
- Ensure proper error handling for all edge cases
- Keep the service focused on data operations only