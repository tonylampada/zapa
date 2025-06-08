"""Message Service for data access operations."""

from datetime import datetime

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.models import Message, User
from app.models import Session as SessionModel
from app.schemas.message import (
    ConversationStats,
    MessageCreate,
    MessageDirection,
    MessageResponse,
    MessageType,
)


class MessageService:
    """Service for message data operations."""

    def __init__(self, db: Session = None):
        """Initialize MessageService with database session."""
        self.db = db

    async def store_message(self, user_id: int, message_data: MessageCreate) -> MessageResponse:
        """Store a new message in the database."""
        # Get or create session
        session = await self.get_or_create_session(user_id)

        # Get user to determine phone number
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User with id {user_id} not found")

        # Use provided JIDs if available, otherwise determine based on direction
        if message_data.sender_jid and message_data.recipient_jid:
            sender_jid = message_data.sender_jid
            recipient_jid = message_data.recipient_jid
        else:
            # Fallback to old behavior for backward compatibility
            if message_data.direction == MessageDirection.INCOMING:
                sender_jid = f"{user.phone_number}@s.whatsapp.net"
                recipient_jid = "service@s.whatsapp.net"
            elif message_data.direction == MessageDirection.OUTGOING:
                sender_jid = "service@s.whatsapp.net"
                recipient_jid = f"{user.phone_number}@s.whatsapp.net"
            else:  # SYSTEM
                sender_jid = "system"
                recipient_jid = "system"

        # Create message
        db_message = Message(
            user_id=user_id,
            session_id=session.id,
            sender_jid=sender_jid,
            recipient_jid=recipient_jid,
            message_type=message_data.message_type.value,
            content=message_data.content,
            timestamp=datetime.utcnow(),
            media_metadata=message_data.metadata,
        )

        # Store WhatsApp message ID if provided
        if message_data.whatsapp_message_id:
            if not db_message.media_metadata:
                db_message.media_metadata = {}
            db_message.media_metadata["whatsapp_message_id"] = message_data.whatsapp_message_id

        self.db.add(db_message)
        self.db.commit()
        self.db.refresh(db_message)

        # Convert to response
        return self._message_to_response(db_message, user.phone_number)

    async def get_recent_messages(self, user_id: int, count: int = 20) -> list[MessageResponse]:
        """Get the N most recent messages for a user."""
        messages = (
            self.db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(desc(Message.timestamp))
            .limit(count)
            .all()
        )

        # Get user phone for direction determination
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        return [self._message_to_response(msg, user.phone_number) for msg in messages]

    async def search_messages(
        self, user_id: int, query: str, limit: int = 10
    ) -> list[MessageResponse]:
        """Search messages by content (text search)."""
        if not query.strip():
            return []

        # Use case-insensitive search
        search_pattern = f"%{query}%"

        messages = (
            self.db.query(Message)
            .filter(
                Message.user_id == user_id,
                or_(
                    Message.content.ilike(search_pattern),
                    Message.caption.ilike(search_pattern),
                ),
            )
            .order_by(desc(Message.timestamp))
            .limit(limit)
            .all()
        )

        # Get user phone for direction determination
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        return [self._message_to_response(msg, user.phone_number) for msg in messages]

    async def get_conversation_stats(self, user_id: int) -> ConversationStats:
        """Get statistics about the user's conversation."""
        # Total messages
        total_messages = (
            self.db.query(func.count(Message.id)).filter(Message.user_id == user_id).scalar() or 0
        )

        if total_messages == 0:
            return ConversationStats(
                total_messages=0,
                messages_sent=0,
                messages_received=0,
                first_message_date=None,
                last_message_date=None,
                average_messages_per_day=0.0,
            )

        # Get user phone
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return ConversationStats(
                total_messages=0,
                messages_sent=0,
                messages_received=0,
                first_message_date=None,
                last_message_date=None,
                average_messages_per_day=0.0,
            )

        user_jid = f"{user.phone_number}@s.whatsapp.net"

        # Messages sent (from user)
        messages_sent = (
            self.db.query(func.count(Message.id))
            .filter(
                Message.user_id == user_id,
                Message.sender_jid == user_jid,
            )
            .scalar()
            or 0
        )

        # Messages received (to user)
        messages_received = (
            self.db.query(func.count(Message.id))
            .filter(
                Message.user_id == user_id,
                Message.recipient_jid == user_jid,
            )
            .scalar()
            or 0
        )

        # First and last message dates
        first_message_date = (
            self.db.query(func.min(Message.timestamp)).filter(Message.user_id == user_id).scalar()
        )

        last_message_date = (
            self.db.query(func.max(Message.timestamp)).filter(Message.user_id == user_id).scalar()
        )

        # Calculate average messages per day
        if first_message_date and last_message_date:
            days_active = (last_message_date - first_message_date).days + 1
            average_messages_per_day = total_messages / max(days_active, 1)
        else:
            average_messages_per_day = 0.0

        return ConversationStats(
            total_messages=total_messages,
            messages_sent=messages_sent,
            messages_received=messages_received,
            first_message_date=first_message_date,
            last_message_date=last_message_date,
            average_messages_per_day=round(average_messages_per_day, 2),
        )

    async def get_messages_by_date_range(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100,
    ) -> list[MessageResponse]:
        """Get messages within a specific date range."""
        messages = (
            self.db.query(Message)
            .filter(
                Message.user_id == user_id,
                Message.timestamp >= start_date,
                Message.timestamp <= end_date,
            )
            .order_by(desc(Message.timestamp))
            .limit(limit)
            .all()
        )

        # Get user phone for direction determination
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        return [self._message_to_response(msg, user.phone_number) for msg in messages]

    async def update_message_status(
        self, whatsapp_message_id: str, status: str
    ) -> MessageResponse | None:
        """Update the delivery status of a message."""
        # Find message by WhatsApp ID in metadata
        message = (
            self.db.query(Message)
            .filter(Message.media_metadata.op("->>")("whatsapp_message_id") == whatsapp_message_id)
            .first()
        )

        if not message:
            return None

        # Update status in metadata
        if not message.media_metadata:
            message.media_metadata = {}
        message.media_metadata["status"] = status

        self.db.commit()
        self.db.refresh(message)

        # Get user phone for response
        user = self.db.query(User).filter(User.id == message.user_id).first()
        if not user:
            return None

        return self._message_to_response(message, user.phone_number)

    def get_user_messages(
        self,
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        search: str = None,
    ) -> list[MessageResponse]:
        """Get user's messages with pagination and optional search."""
        query = db.query(Message).filter(Message.user_id == user_id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Message.content.ilike(search_pattern),
                    Message.caption.ilike(search_pattern),
                )
            )

        messages = query.order_by(desc(Message.timestamp)).offset(skip).limit(limit).all()

        # Get user phone for direction determination
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        return [self._message_to_response(msg, user.phone_number) for msg in messages]

    def search_user_messages(
        self, db: Session, user_id: int, query: str, skip: int = 0, limit: int = 20
    ) -> list[MessageResponse]:
        """Search user's messages by content."""
        if not query.strip():
            return []

        search_pattern = f"%{query}%"
        messages = (
            db.query(Message)
            .filter(
                Message.user_id == user_id,
                or_(
                    Message.content.ilike(search_pattern),
                    Message.caption.ilike(search_pattern),
                ),
            )
            .order_by(desc(Message.timestamp))
            .offset(skip)
            .limit(limit)
            .all()
        )

        # Get user phone for direction determination
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        return [self._message_to_response(msg, user.phone_number) for msg in messages]

    def get_user_message_stats(self, db: Session, user_id: int) -> ConversationStats:
        """Get user's message statistics."""
        # Total messages
        total_messages = (
            db.query(func.count(Message.id)).filter(Message.user_id == user_id).scalar() or 0
        )

        if total_messages == 0:
            return ConversationStats(
                total_messages=0,
                messages_sent=0,
                messages_received=0,
                first_message_date=None,
                last_message_date=None,
                average_messages_per_day=0.0,
            )

        # Get user phone
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return ConversationStats(
                total_messages=0,
                messages_sent=0,
                messages_received=0,
                first_message_date=None,
                last_message_date=None,
                average_messages_per_day=0.0,
            )

        user_jid = f"{user.phone_number}@s.whatsapp.net"

        # Messages sent (from user)
        messages_sent = (
            db.query(func.count(Message.id))
            .filter(
                Message.user_id == user_id,
                Message.sender_jid == user_jid,
            )
            .scalar()
            or 0
        )

        # Messages received (to user)
        messages_received = (
            db.query(func.count(Message.id))
            .filter(
                Message.user_id == user_id,
                Message.recipient_jid == user_jid,
            )
            .scalar()
            or 0
        )

        # First and last message dates
        first_message_date = (
            db.query(func.min(Message.timestamp)).filter(Message.user_id == user_id).scalar()
        )

        last_message_date = (
            db.query(func.max(Message.timestamp)).filter(Message.user_id == user_id).scalar()
        )

        # Calculate average messages per day
        if first_message_date and last_message_date:
            days_active = (last_message_date - first_message_date).days + 1
            average_messages_per_day = total_messages / max(days_active, 1)
        else:
            average_messages_per_day = 0.0

        return ConversationStats(
            total_messages=total_messages,
            messages_sent=messages_sent,
            messages_received=messages_received,
            first_message_date=first_message_date,
            last_message_date=last_message_date,
            average_messages_per_day=round(average_messages_per_day, 2),
        )

    def export_user_messages(self, db: Session, user_id: int, format: str = "json"):
        """Export user's messages in specified format."""
        messages = (
            db.query(Message).filter(Message.user_id == user_id).order_by(Message.timestamp).all()
        )

        # Get user phone for direction determination
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return [] if format == "json" else ""

        message_responses = [self._message_to_response(msg, user.phone_number) for msg in messages]

        if format == "json":
            return [msg.model_dump() for msg in message_responses]
        elif format == "csv":
            # Create CSV content
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(
                [
                    "id",
                    "timestamp",
                    "direction",
                    "content",
                    "message_type",
                    "whatsapp_id",
                ]
            )

            # Write data
            for msg in message_responses:
                writer.writerow(
                    [
                        msg.id,
                        msg.created_at.isoformat(),
                        msg.direction,
                        msg.content,
                        msg.message_type,
                        msg.whatsapp_message_id or "",
                    ]
                )

            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    async def get_or_create_session(self, user_id: int) -> SessionModel:
        """Get active session or create a new one."""
        from models.session import SessionStatus, SessionType

        # Check for existing connected session
        session = (
            self.db.query(SessionModel)
            .filter(
                SessionModel.user_id == user_id,
                SessionModel.status == SessionStatus.CONNECTED,
                SessionModel.session_type == SessionType.MAIN,
            )
            .first()
        )

        if session:
            return session

        # Create new session
        session = SessionModel(
            user_id=user_id,
            session_type=SessionType.MAIN,
            status=SessionStatus.CONNECTED,
            connected_at=datetime.utcnow(),
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def _message_to_response(self, message: Message, user_phone: str) -> MessageResponse:
        """Convert Message model to MessageResponse schema."""
        # Determine direction based on sender/recipient
        user_jid = f"{user_phone}@s.whatsapp.net"

        if message.sender_jid == user_jid:
            direction = MessageDirection.INCOMING
        elif message.recipient_jid == user_jid:
            direction = MessageDirection.OUTGOING
        else:
            direction = MessageDirection.SYSTEM

        # Extract WhatsApp message ID from metadata
        whatsapp_message_id = None
        if message.media_metadata and "whatsapp_message_id" in message.media_metadata:
            whatsapp_message_id = message.media_metadata["whatsapp_message_id"]

        # Handle both enum and string types (for tests and production)
        if hasattr(message.message_type, "value"):
            message_type_value = message.message_type.value
        else:
            message_type_value = message.message_type

        return MessageResponse(
            id=message.id,
            user_id=message.user_id,
            content=message.content or "",
            direction=direction,
            message_type=MessageType(message_type_value),
            whatsapp_message_id=whatsapp_message_id,
            metadata=message.media_metadata,
            created_at=message.created_at,
        )
