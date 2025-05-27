"""User model."""
from sqlalchemy import Column, Integer, String, Boolean
from .base import BaseModel


class User(BaseModel):
    """User model for WhatsApp users."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    llm_provider = Column(String(50), default="openai")
    llm_model = Column(String(100), default="gpt-4o")
    llm_api_key = Column(String(500), nullable=True)  # Encrypted