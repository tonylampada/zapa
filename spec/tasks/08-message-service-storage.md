# Task 08: Message Service and Storage

**Dependencies**: Task 07 (LLM Adapter Interface)
**Estimated Time**: 2-3 hours
**CI Required**: ✅ All tests must pass

## Objective

Create the Message Service as a pure data access layer for WhatsApp messages. This service serves as a bridge between the database and the rest of the application, with two primary use cases:

1. **Webhook Handlers**: Store incoming/outgoing messages from WhatsApp into the database
2. **LLM Tools**: Provide data access methods that the LLM can use to read conversation history

**Important**: This service is purely for data operations. It should NOT perform any intelligent operations like summarization or task extraction - those behaviors should emerge from the LLM's use of the raw data.

## Requirements

### Core Message Operations
- Store incoming and outgoing messages
- Retrieve messages with pagination and filtering
- Search messages by content (text search initially, semantic later)
- Get basic conversation statistics (counts, dates)
- Update message status (delivered, read, failed)

### Message Storage
- Store messages with proper metadata (timestamp, direction, user_id, etc.)
- Handle different message types (text, media, system messages)
- Maintain session continuity for conversations
- Efficient querying for conversation history

### Data Retrieval
- Text-based search through message content
- Recent message retrieval with flexible filtering
- Time-range based queries
- Session-based message grouping

## Test Strategy

### Unit Tests (Always Run)
- Message storage and retrieval
- Search functionality with mocked data
- Pagination logic
- Statistics calculation (counts, date ranges)

### Integration Tests (Skippable)
- Database operations with real PostgreSQL
- Performance tests with large message volumes

## Files to Create

### Service Implementation
```
backend/app/services/message_service.py
```

### Tests
```
backend/tests/unit/services/test_message_service.py
backend/tests/integration/services/test_message_integration.py
```

## Implementation Details

### MessageService Class

```python
# backend/app/services/message_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_

from app.models import Message, User, Session as SessionModel
from app.schemas.message import (
    MessageCreate, MessageResponse, MessageSearchParams,
    ConversationStats
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
    
    async def get_messages_by_date_range(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100
    ) -> List[MessageResponse]:
        """Get messages within a specific date range."""
        pass
    
    async def update_message_status(
        self,
        whatsapp_message_id: str,
        status: str
    ) -> Optional[MessageResponse]:
        """Update the delivery status of a message."""
        pass
    
    async def get_or_create_session(
        self,
        user_id: int
    ) -> SessionModel:
        """Get active session or create a new one."""
        pass
```

### Message Schemas

```python
# backend/app/schemas/message.py
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

class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
```

## Acceptance Criteria

### Core Functionality
- [ ] Messages can be stored with all required metadata
- [ ] Recent messages can be retrieved with pagination
- [ ] Text search works across message content
- [ ] Conversation statistics are calculated correctly
- [ ] Messages can be retrieved by date range
- [ ] Message status can be updated

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
# backend/tests/unit/services/test_message_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from app.services.message_service import MessageService
from app.schemas.message import MessageCreate, MessageDirection

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
    
    async def test_get_messages_by_date_range(self, message_service, mock_db):
        # Test date range filtering
        pass
    
    async def test_update_message_status(self, message_service, mock_db):
        # Test message status updates
        pass
```

### Integration Test Structure
```python
# backend/tests/integration/services/test_message_integration.py
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
- No intelligent processing - that's the LLM's job
- The service is a dumb data layer that provides raw conversation data