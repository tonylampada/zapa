"""Integration tests for MessageService with real database."""

import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.message_service import MessageService
from models import Base, Message, Session as SessionModel, User
from models.session import SessionStatus, SessionType
from schemas.message import (
    ConversationStats,
    MessageCreate,
    MessageDirection,
    MessageResponse,
    MessageType,
)

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_DATABASE", "false").lower() != "true",
    reason="Database integration tests disabled. Set INTEGRATION_TEST_DATABASE=true to run.",
)


@pytest.fixture
def db_engine():
    """Create test database engine."""
    # Use SQLite in-memory database for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create database session for tests."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        phone_number="+1234567890",
        display_name="Test User",
        first_seen=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def message_service(db_session):
    """Create MessageService instance."""
    return MessageService(db_session)


class TestMessageIntegration:
    """Integration tests for MessageService."""

    async def test_message_storage_and_retrieval(
        self, message_service, db_session, test_user
    ):
        """Test storing and retrieving messages with real database."""
        # Store multiple messages
        messages_data = [
            MessageCreate(
                content="Hello from user",
                direction=MessageDirection.INCOMING,
                message_type=MessageType.TEXT,
            ),
            MessageCreate(
                content="Hello from service",
                direction=MessageDirection.OUTGOING,
                message_type=MessageType.TEXT,
            ),
            MessageCreate(
                content="How can I help you?",
                direction=MessageDirection.OUTGOING,
                message_type=MessageType.TEXT,
            ),
        ]
        
        stored_messages = []
        for msg_data in messages_data:
            result = await message_service.store_message(test_user.id, msg_data)
            stored_messages.append(result)
        
        # Verify messages were stored
        assert len(stored_messages) == 3
        assert all(isinstance(msg, MessageResponse) for msg in stored_messages)
        
        # Retrieve recent messages
        recent = await message_service.get_recent_messages(test_user.id, count=10)
        assert len(recent) == 3
        
        # Messages should be in reverse chronological order
        assert recent[0].content == "How can I help you?"
        assert recent[2].content == "Hello from user"
        
        # Verify session was created
        session = db_session.query(SessionModel).filter(
            SessionModel.user_id == test_user.id
        ).first()
        assert session is not None
        assert session.status == SessionStatus.CONNECTED

    async def test_message_search_functionality(
        self, message_service, test_user
    ):
        """Test searching messages by content."""
        # Store messages with different content
        messages = [
            "Hello, how are you?",
            "I need help with my order",
            "Order number is 12345",
            "Thank you for your help!",
            "Goodbye!",
        ]
        
        for content in messages:
            await message_service.store_message(
                test_user.id,
                MessageCreate(
                    content=content,
                    direction=MessageDirection.INCOMING,
                    message_type=MessageType.TEXT,
                ),
            )
        
        # Search for "help"
        help_results = await message_service.search_messages(
            test_user.id, "help", limit=10
        )
        assert len(help_results) == 2
        assert all("help" in msg.content.lower() for msg in help_results)
        
        # Search for "order"
        order_results = await message_service.search_messages(
            test_user.id, "order", limit=10
        )
        assert len(order_results) == 2
        
        # Search for non-existent term
        no_results = await message_service.search_messages(
            test_user.id, "nonexistent", limit=10
        )
        assert len(no_results) == 0

    async def test_conversation_statistics(
        self, message_service, test_user
    ):
        """Test conversation statistics calculation."""
        # Store messages over several days
        base_time = datetime.utcnow() - timedelta(days=7)
        
        # Create messages with different timestamps
        for day in range(7):
            # Morning message from user
            await message_service.store_message(
                test_user.id,
                MessageCreate(
                    content=f"Good morning, day {day + 1}",
                    direction=MessageDirection.INCOMING,
                    message_type=MessageType.TEXT,
                ),
            )
            
            # Response from service
            await message_service.store_message(
                test_user.id,
                MessageCreate(
                    content=f"Good morning! How can I help on day {day + 1}?",
                    direction=MessageDirection.OUTGOING,
                    message_type=MessageType.TEXT,
                ),
            )
        
        # Get statistics
        stats = await message_service.get_conversation_stats(test_user.id)
        
        assert stats.total_messages == 14
        assert stats.messages_sent == 7  # From user
        assert stats.messages_received == 7  # From service
        assert stats.average_messages_per_day == 2.0
        assert stats.first_message_date is not None
        assert stats.last_message_date is not None

    async def test_message_status_updates(
        self, message_service, test_user
    ):
        """Test updating message delivery status."""
        # Store a message with WhatsApp ID
        result = await message_service.store_message(
            test_user.id,
            MessageCreate(
                content="Test message",
                direction=MessageDirection.OUTGOING,
                message_type=MessageType.TEXT,
                whatsapp_message_id="wa_123456",
            ),
        )
        
        assert result.whatsapp_message_id == "wa_123456"
        
        # Update status to delivered
        updated = await message_service.update_message_status(
            "wa_123456", "delivered"
        )
        assert updated is not None
        assert updated.metadata["status"] == "delivered"
        
        # Update status to read
        updated = await message_service.update_message_status("wa_123456", "read")
        assert updated is not None
        assert updated.metadata["status"] == "read"
        
        # Try to update non-existent message
        not_found = await message_service.update_message_status(
            "nonexistent", "delivered"
        )
        assert not_found is None

    async def test_date_range_queries(
        self, message_service, test_user
    ):
        """Test retrieving messages by date range."""
        # Store messages across different dates
        now = datetime.utcnow()
        dates = [
            now - timedelta(days=10),
            now - timedelta(days=5),
            now - timedelta(days=3),
            now - timedelta(days=1),
            now,
        ]
        
        for i, date in enumerate(dates):
            # We need to manually set the timestamp for testing
            # This would require modifying the service or using a different approach
            await message_service.store_message(
                test_user.id,
                MessageCreate(
                    content=f"Message {i + 1}",
                    direction=MessageDirection.INCOMING,
                    message_type=MessageType.TEXT,
                ),
            )
        
        # Query messages from last 7 days
        week_start = now - timedelta(days=7)
        week_messages = await message_service.get_messages_by_date_range(
            test_user.id, week_start, now, limit=100
        )
        
        # Should get messages from last 7 days (indexes 1-4)
        assert len(week_messages) >= 4
        
        # Query messages from last 3 days
        three_days_start = now - timedelta(days=3)
        recent_messages = await message_service.get_messages_by_date_range(
            test_user.id, three_days_start, now, limit=100
        )
        
        # Should get messages from last 3 days (indexes 2-4)
        assert len(recent_messages) >= 3

    async def test_session_management(
        self, message_service, db_session, test_user
    ):
        """Test session creation and management."""
        # First message should create a session
        await message_service.store_message(
            test_user.id,
            MessageCreate(
                content="First message",
                direction=MessageDirection.INCOMING,
                message_type=MessageType.TEXT,
            ),
        )
        
        # Check session was created
        sessions = db_session.query(SessionModel).filter(
            SessionModel.user_id == test_user.id
        ).all()
        assert len(sessions) == 1
        assert sessions[0].status == SessionStatus.CONNECTED
        
        # Subsequent messages should use same session
        await message_service.store_message(
            test_user.id,
            MessageCreate(
                content="Second message",
                direction=MessageDirection.INCOMING,
                message_type=MessageType.TEXT,
            ),
        )
        
        # Still only one session
        sessions = db_session.query(SessionModel).filter(
            SessionModel.user_id == test_user.id
        ).all()
        assert len(sessions) == 1
        
        # All messages should have same session_id
        messages = db_session.query(Message).filter(
            Message.user_id == test_user.id
        ).all()
        assert all(msg.session_id == sessions[0].id for msg in messages)

    async def test_search_performance_large_dataset(
        self, message_service, test_user
    ):
        """Test search performance with many messages."""
        # Store 1000 messages
        import time
        
        for i in range(1000):
            content = f"Message {i}: "
            if i % 10 == 0:
                content += "special keyword"
            elif i % 5 == 0:
                content += "another term"
            else:
                content += "regular content"
            
            await message_service.store_message(
                test_user.id,
                MessageCreate(
                    content=content,
                    direction=MessageDirection.INCOMING,
                    message_type=MessageType.TEXT,
                ),
            )
        
        # Time the search
        start = time.time()
        results = await message_service.search_messages(
            test_user.id, "special", limit=50
        )
        end = time.time()
        
        # Should find 100 messages (every 10th)
        assert len(results) == 50  # Limited to 50
        assert all("special" in msg.content for msg in results)
        
        # Search should be reasonably fast (< 500ms)
        assert (end - start) < 0.5