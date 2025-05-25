# Task 03: Backend Models Implementation

## Objective
Implement database models (SQLAlchemy) and Pydantic schemas for the WhatsApp Agent System.

## Requirements
- Create SQLAlchemy models for all database tables
- Create Pydantic schemas for request/response validation
- Ensure proper relationships between models
- Follow the data model from the PRD

## Database Tables
1. users - Admin user accounts
2. agents - Agent configurations
3. sessions - WhatsApp sessions
4. messages - Message history
5. logs - System logs

## Files to Create

### backend/app/models/models.py
```python
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base

class SessionStatus(str, enum.Enum):
    QR_PENDING = "qr_pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class MessageDirection(str, enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"

class LogLevel(str, enum.Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    model = Column(String, default="gpt-4")
    system_prompt = Column(Text, nullable=False)
    functions = Column(JSON, default=list)  # OpenAI function definitions
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    sessions = relationship("Session", back_populates="agent")

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True)  # Can be phone number or UUID
    status = Column(Enum(SessionStatus), default=SessionStatus.QR_PENDING)
    phone_number = Column(String, nullable=True)
    qr_code = Column(Text, nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    connected_at = Column(DateTime(timezone=True), nullable=True)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    agent = relationship("Agent", back_populates="sessions")
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    contact_jid = Column(String, nullable=False, index=True)
    direction = Column(Enum(MessageDirection), nullable=False)
    message_type = Column(String, default="text")  # text, image, document, etc.
    content = Column(Text)
    media_url = Column(String, nullable=True)
    metadata = Column(JSON, default=dict)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Relationships
    session = relationship("Session", back_populates="messages")

class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(Enum(LogLevel), nullable=False)
    source = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    session_id = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
```

### backend/app/models/schemas.py
```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

# Enums
class SessionStatus(str, Enum):
    QR_PENDING = "qr_pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class MessageDirection(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"

# User schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Agent schemas
class AgentBase(BaseModel):
    name: str
    description: Optional[str] = None
    model: str = "gpt-4"
    system_prompt: str
    functions: List[Dict[str, Any]] = []

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    functions: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None

class AgentResponse(AgentBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

# Session schemas
class SessionCreate(BaseModel):
    agent_id: int
    session_id: Optional[str] = None

class SessionResponse(BaseModel):
    id: str
    status: SessionStatus
    phone_number: Optional[str]
    qr_code: Optional[str]
    agent_id: int
    agent: AgentResponse
    connected_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Message schemas
class MessageBase(BaseModel):
    contact_jid: str
    message_type: str = "text"
    content: str
    media_url: Optional[str] = None

class MessageCreate(MessageBase):
    session_id: str
    direction: MessageDirection
    metadata: Dict[str, Any] = {}

class MessageResponse(MessageBase):
    id: int
    session_id: str
    direction: MessageDirection
    metadata: Dict[str, Any]
    timestamp: datetime
    
    class Config:
        from_attributes = True

# Webhook schemas
class WebhookMessage(BaseModel):
    session_id: str
    contact_jid: str
    message_type: str
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}

class WebhookEvent(BaseModel):
    event_type: str
    session_id: str
    data: Dict[str, Any]

# Command schemas
class CommandRequest(BaseModel):
    session_id: str
    contact_jid: str
    command: str
    parameters: Dict[str, Any] = {}

class CommandResponse(BaseModel):
    success: bool
    result: Any
    error: Optional[str] = None
```

### backend/app/models/__init__.py
```python
from app.models.models import User, Agent, Session, Message, Log
from app.models.schemas import (
    UserCreate, UserResponse, UserLogin, Token,
    AgentCreate, AgentUpdate, AgentResponse,
    SessionCreate, SessionResponse,
    MessageCreate, MessageResponse,
    WebhookMessage, WebhookEvent,
    CommandRequest, CommandResponse
)

__all__ = [
    # Models
    "User", "Agent", "Session", "Message", "Log",
    # Schemas
    "UserCreate", "UserResponse", "UserLogin", "Token",
    "AgentCreate", "AgentUpdate", "AgentResponse",
    "SessionCreate", "SessionResponse",
    "MessageCreate", "MessageResponse",
    "WebhookMessage", "WebhookEvent",
    "CommandRequest", "CommandResponse"
]
```

## Success Criteria
- [ ] All SQLAlchemy models created with proper relationships
- [ ] All Pydantic schemas created for API validation
- [ ] Enums defined for status fields
- [ ] Proper indexes on frequently queried fields
- [ ] Models match the PRD data model specification