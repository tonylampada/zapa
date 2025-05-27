"""Unit tests for MessageService."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.services.message_service import MessageService
from models import Message, Session as SessionModel, User
from models.session import SessionStatus
from schemas.message import (
    ConversationStats,
    MessageCreate,
    MessageDirection,
    MessageResponse,
    MessageType,
)


class TestMessageService:
    """Test MessageService class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock(spec=Session)
        db.query = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.scalar = Mock()
        return db

    @pytest.fixture
    def message_service(self, mock_db):
        """Create MessageService instance with mock db."""
        return MessageService(mock_db)

    @pytest.fixture
    def sample_user(self):
        """Create a sample user."""
        user = User(
            id=1,
            phone_number="+1234567890",
            display_name="Test User",
            first_seen=datetime.utcnow(),
        )
        return user

    @pytest.fixture
    def sample_session(self, sample_user):
        """Create a sample session."""
        from models.session import SessionStatus, SessionType
        
        session = SessionModel(
            id=1,
            user_id=sample_user.id,
            session_type=SessionType.MAIN,
            status=SessionStatus.CONNECTED,
            connected_at=datetime.utcnow(),
        )
        return session

    @pytest.fixture
    def sample_message(self, sample_user, sample_session):
        """Create a sample message."""
        return Message(
            id=1,
            user_id=sample_user.id,
            session_id=sample_session.id,
            sender_jid="+1234567890@s.whatsapp.net",
            recipient_jid="service@s.whatsapp.net",
            message_type="text",
            content="Hello, world!",
            timestamp=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

    async def test_store_message_success(self, message_service, mock_db, sample_user, sample_session):
        """Test successful message storage."""
        # Arrange
        message_data = MessageCreate(
            content="Test message",
            direction=MessageDirection.INCOMING,
            message_type=MessageType.TEXT,
            whatsapp_message_id="12345",
            metadata={"extra": "data"},
        )
        
        # Mock get_or_create_session - this is an async method that we'll mock
        async def mock_get_or_create_session(user_id):
            return sample_session
        message_service.get_or_create_session = AsyncMock(side_effect=mock_get_or_create_session)
        
        # Mock user query
        mock_user_query = Mock()
        mock_user_query.filter.return_value = mock_user_query
        mock_user_query.first.return_value = sample_user
        mock_db.query.return_value = mock_user_query
        
        # Mock db.refresh to set attributes on the created message
        def mock_refresh(obj):
            obj.id = 1
            obj.created_at = datetime.utcnow()
        mock_db.refresh = Mock(side_effect=mock_refresh)
        
        # Act
        result = await message_service.store_message(sample_user.id, message_data)
        
        # Assert
        assert mock_db.add.called
        assert mock_db.commit.called
        assert isinstance(result, MessageResponse)
        assert result.content == message_data.content
        assert result.direction == message_data.direction
        assert result.message_type == message_data.message_type

    async def test_get_recent_messages(self, message_service, mock_db, sample_user):
        """Test retrieving recent messages."""
        # Arrange
        messages = [
            Message(
                id=i,
                user_id=sample_user.id,
                session_id=1,
                sender_jid=f"{sample_user.phone_number}@s.whatsapp.net" if i % 2 == 0 else "service@s.whatsapp.net",
                recipient_jid="service@s.whatsapp.net" if i % 2 == 0 else f"{sample_user.phone_number}@s.whatsapp.net",
                message_type="text",
                content=f"Message {i}",
                timestamp=datetime.utcnow() - timedelta(minutes=i),
                created_at=datetime.utcnow() - timedelta(minutes=i),
            )
            for i in range(5)
        ]
        
        # Mock query for messages
        messages_query = Mock()
        messages_query.filter.return_value = messages_query
        messages_query.order_by.return_value = messages_query
        messages_query.limit.return_value = messages_query
        messages_query.all.return_value = messages
        
        # Mock query for user
        user_query = Mock()
        user_query.filter.return_value = user_query
        user_query.first.return_value = sample_user
        
        # Set up mock_db to return different queries based on the model
        mock_db.query.side_effect = lambda model: messages_query if model == Message else user_query
        
        # Act
        result = await message_service.get_recent_messages(sample_user.id, count=5)
        
        # Assert
        assert len(result) == 5
        assert all(isinstance(msg, MessageResponse) for msg in result)
        assert result[0].content == "Message 0"

    async def test_search_messages(self, message_service, mock_db, sample_user):
        """Test searching messages by content."""
        # Arrange
        search_query = "hello"
        matching_messages = [
            Message(
                id=1,
                user_id=sample_user.id,
                session_id=1,
                sender_jid=f"{sample_user.phone_number}@s.whatsapp.net",
                recipient_jid="service@s.whatsapp.net",
                message_type="text",
                content="Hello world",
                timestamp=datetime.utcnow(),
                created_at=datetime.utcnow(),
            ),
            Message(
                id=2,
                user_id=sample_user.id,
                session_id=1,
                sender_jid="service@s.whatsapp.net",
                recipient_jid=f"{sample_user.phone_number}@s.whatsapp.net",
                message_type="text",
                content="Hello there",
                timestamp=datetime.utcnow(),
                created_at=datetime.utcnow(),
            ),
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = matching_messages
        mock_db.query.return_value = mock_query
        
        # Act
        result = await message_service.search_messages(sample_user.id, search_query, limit=10)
        
        # Assert
        assert len(result) == 2
        assert all(isinstance(msg, MessageResponse) for msg in result)
        assert all("hello" in msg.content.lower() for msg in result)

    async def test_get_conversation_stats(self, message_service, mock_db, sample_user):
        """Test getting conversation statistics."""
        # Arrange
        total_count = 100
        sent_count = 40
        received_count = 60
        first_date = datetime.utcnow() - timedelta(days=30)
        last_date = datetime.utcnow()
        
        # Create separate query mocks for each operation
        query_mocks = []
        
        # Total count query
        total_query = Mock()
        total_query.filter.return_value = total_query
        total_query.scalar.return_value = total_count
        query_mocks.append(total_query)
        
        # User query for checking existence
        user_query = Mock()
        user_query.filter.return_value = user_query
        user_query.first.return_value = sample_user
        query_mocks.append(user_query)
        
        # Sent count query
        sent_query = Mock()
        sent_query.filter.return_value = sent_query
        sent_query.scalar.return_value = sent_count
        query_mocks.append(sent_query)
        
        # Received count query
        received_query = Mock()
        received_query.filter.return_value = received_query
        received_query.scalar.return_value = received_count
        query_mocks.append(received_query)
        
        # First date query
        first_date_query = Mock()
        first_date_query.filter.return_value = first_date_query
        first_date_query.scalar.return_value = first_date
        query_mocks.append(first_date_query)
        
        # Last date query
        last_date_query = Mock()
        last_date_query.filter.return_value = last_date_query
        last_date_query.scalar.return_value = last_date
        query_mocks.append(last_date_query)
        
        mock_db.query.side_effect = query_mocks
        
        # Act
        result = await message_service.get_conversation_stats(sample_user.id)
        
        # Assert
        assert isinstance(result, ConversationStats)
        assert result.total_messages == total_count
        assert result.messages_sent == sent_count
        assert result.messages_received == received_count
        assert result.first_message_date == first_date
        assert result.last_message_date == last_date
        assert result.average_messages_per_day > 0

    async def test_get_messages_by_date_range(self, message_service, mock_db, sample_user):
        """Test retrieving messages within a date range."""
        # Arrange
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()
        
        messages_in_range = [
            Message(
                id=i,
                user_id=sample_user.id,
                session_id=1,
                sender_jid=f"{sample_user.phone_number}@s.whatsapp.net",
                recipient_jid="service@s.whatsapp.net",
                message_type="text",
                content=f"Message {i}",
                timestamp=start_date + timedelta(days=i),
                created_at=start_date + timedelta(days=i),
            )
            for i in range(3)
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = messages_in_range
        mock_db.query.return_value = mock_query
        
        # Act
        result = await message_service.get_messages_by_date_range(
            sample_user.id, start_date, end_date, limit=50
        )
        
        # Assert
        assert len(result) == 3
        assert all(isinstance(msg, MessageResponse) for msg in result)
        
    async def test_update_message_status(self, message_service, mock_db, sample_user):
        """Test updating message delivery status."""
        # Arrange
        whatsapp_id = "msg123"
        new_status = "delivered"
        
        message = Message(
            id=1,
            user_id=1,
            session_id=1,
            sender_jid="service@s.whatsapp.net",
            recipient_jid="+1234567890@s.whatsapp.net",
            message_type="text",
            content="Test message",
            timestamp=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        message.media_metadata = {"status": "sent", "whatsapp_message_id": whatsapp_id}
        
        # Mock query for message
        mock_message_query = Mock()
        mock_message_query.filter.return_value = mock_message_query
        mock_message_query.first.return_value = message
        
        # Mock query for user
        mock_user_query = Mock()
        mock_user_query.filter.return_value = mock_user_query
        mock_user_query.first.return_value = sample_user
        
        # Set up mock_db to return different queries based on the model
        mock_db.query.side_effect = lambda model: mock_message_query if model == Message else mock_user_query
        
        # Act
        result = await message_service.update_message_status(whatsapp_id, new_status)
        
        # Assert
        assert mock_db.commit.called
        assert isinstance(result, MessageResponse)
        assert message.media_metadata["status"] == new_status

    async def test_update_message_status_not_found(self, message_service, mock_db):
        """Test updating status for non-existent message."""
        # Arrange
        whatsapp_id = "nonexistent"
        new_status = "delivered"
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Act
        result = await message_service.update_message_status(whatsapp_id, new_status)
        
        # Assert
        assert result is None
        assert not mock_db.commit.called

    async def test_get_or_create_session_existing(self, message_service, mock_db, sample_session):
        """Test getting existing active session."""
        # Arrange
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.first.return_value = sample_session
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query
        
        # Act
        result = await message_service.get_or_create_session(sample_session.user_id)
        
        # Assert
        assert result == sample_session
        assert not mock_db.add.called
        assert not mock_db.commit.called

    async def test_get_or_create_session_new(self, message_service, mock_db, sample_user):
        """Test creating new session when none exists."""
        # Arrange
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query
        
        # Act
        result = await message_service.get_or_create_session(sample_user.id)
        
        # Assert
        assert mock_db.add.called
        assert mock_db.commit.called
        assert isinstance(result, SessionModel)
        assert result.user_id == sample_user.id
        assert result.status == SessionStatus.CONNECTED

    async def test_search_messages_empty_query(self, message_service, mock_db):
        """Test searching with empty query returns empty list."""
        # Act
        result = await message_service.search_messages(1, "", limit=10)
        
        # Assert
        assert result == []
        assert not mock_db.query.called

    async def test_get_conversation_stats_no_messages(self, message_service, mock_db, sample_user):
        """Test stats when user has no messages."""
        # Arrange
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.scalar.return_value = None
        mock_db.query.return_value = mock_query
        
        # Act
        result = await message_service.get_conversation_stats(sample_user.id)
        
        # Assert
        assert result.total_messages == 0
        assert result.messages_sent == 0
        assert result.messages_received == 0
        assert result.first_message_date is None
        assert result.last_message_date is None
        assert result.average_messages_per_day == 0.0