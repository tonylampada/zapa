"""Message model."""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from .base import BaseModel


class Message(BaseModel):
    """Message model for storing WhatsApp messages."""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    is_from_user = Column(Boolean, nullable=False)
    whatsapp_message_id = Column(String(100), unique=True, nullable=True)
    
    # Relationship
    user = relationship("User", backref="messages")