# Task 04: Backend Adapters Implementation

## Objective
Implement adapter layer for external service integrations following the plumbing pattern.

## Requirements
- Create adapters for WhatsApp Bridge, OpenAI, and Database
- Ensure adapters abstract external dependencies
- Handle errors and retries appropriately
- Keep business logic out of adapters

## Files to Create

### backend/app/adapters/whatsapp_client.py
```python
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger

class WhatsAppClient:
    def __init__(self):
        self.base_url = settings.WHATSAPP_API_URL
        self.api_key = settings.WHATSAPP_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new WhatsApp session and get QR code"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sessions",
                json={"id": session_id},
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session status"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/sessions/{session_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a WhatsApp session"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/sessions/{session_id}",
                headers=self.headers
            )
            return response.status_code == 200
    
    async def send_message(self, session_id: str, to: str, message: str, 
                          message_type: str = "text") -> Dict[str, Any]:
        """Send a message via WhatsApp"""
        async with httpx.AsyncClient() as client:
            payload = {
                "to": to,
                "type": message_type,
                "content": message
            }
            response = await client.post(
                f"{self.base_url}/sessions/{session_id}/messages",
                json=payload,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
```

### backend/app/adapters/openai_client.py
```python
import openai
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger

class OpenAIClient:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        functions: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate chat completion with optional function calling"""
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
            
            if functions:
                kwargs["functions"] = functions
                kwargs["function_call"] = "auto"
            
            response = await self.client.chat.completions.create(**kwargs)
            
            # Extract the relevant parts
            choice = response.choices[0]
            result = {
                "content": choice.message.content,
                "role": choice.message.role,
                "finish_reason": choice.finish_reason
            }
            
            # Check for function call
            if hasattr(choice.message, 'function_call') and choice.message.function_call:
                result["function_call"] = {
                    "name": choice.message.function_call.name,
                    "arguments": choice.message.function_call.arguments
                }
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
    
    async def create_embedding(self, text: str, model: str = "text-embedding-ada-002") -> List[float]:
        """Create text embedding for vector search"""
        try:
            response = await self.client.embeddings.create(
                input=text,
                model=model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI Embedding error: {str(e)}")
            raise
    
    async def moderate_content(self, text: str) -> Dict[str, Any]:
        """Check content for policy violations"""
        try:
            response = await self.client.moderations.create(input=text)
            return response.results[0].model_dump()
        except Exception as e:
            logger.error(f"OpenAI Moderation error: {str(e)}")
            raise
```

### backend/app/adapters/db_repository.py
```python
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.models import (
    User, Agent, Session as SessionModel, Message, Log,
    SessionStatus, MessageDirection
)

class UserRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()
    
    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

class AgentRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Agent]:
        return self.db.query(Agent).filter(Agent.is_active == True).offset(skip).limit(limit).all()
    
    def get_by_id(self, agent_id: int) -> Optional[Agent]:
        return self.db.query(Agent).filter(Agent.id == agent_id).first()
    
    def create(self, agent: Agent) -> Agent:
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent
    
    def update(self, agent: Agent) -> Agent:
        self.db.commit()
        self.db.refresh(agent)
        return agent

class SessionRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[SessionModel]:
        return self.db.query(SessionModel).offset(skip).limit(limit).all()
    
    def get_by_id(self, session_id: str) -> Optional[SessionModel]:
        return self.db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    def get_active_sessions(self) -> List[SessionModel]:
        return self.db.query(SessionModel).filter(
            SessionModel.status == SessionStatus.CONNECTED
        ).all()
    
    def create(self, session: SessionModel) -> SessionModel:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def update(self, session: SessionModel) -> SessionModel:
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def delete(self, session_id: str) -> bool:
        session = self.get_by_id(session_id)
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False

class MessageRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, message: Message) -> Message:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
    
    def get_conversation(
        self, 
        session_id: str, 
        contact_jid: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Message]:
        return self.db.query(Message).filter(
            and_(
                Message.session_id == session_id,
                Message.contact_jid == contact_jid
            )
        ).order_by(desc(Message.timestamp)).limit(limit).offset(offset).all()
    
    def get_recent_messages(
        self,
        session_id: str,
        contact_jid: str,
        last_n: int = 20
    ) -> List[Message]:
        return self.db.query(Message).filter(
            and_(
                Message.session_id == session_id,
                Message.contact_jid == contact_jid
            )
        ).order_by(desc(Message.timestamp)).limit(last_n).all()
    
    def search_messages(
        self,
        session_id: str,
        query: str,
        limit: int = 10
    ) -> List[Message]:
        # Simple text search, can be enhanced with full-text search
        return self.db.query(Message).filter(
            and_(
                Message.session_id == session_id,
                Message.content.contains(query)
            )
        ).order_by(desc(Message.timestamp)).limit(limit).all()

class LogRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, log: Log) -> Log:
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
    
    def get_recent_logs(
        self,
        limit: int = 100,
        level: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[Log]:
        query = self.db.query(Log)
        
        if level:
            query = query.filter(Log.level == level)
        if session_id:
            query = query.filter(Log.session_id == session_id)
        
        return query.order_by(desc(Log.timestamp)).limit(limit).all()
```

### backend/app/adapters/vector_store.py (Optional)
```python
import numpy as np
from typing import List, Tuple, Optional
from app.core.config import settings

class VectorStore:
    """Simple in-memory vector store, can be replaced with pgvector or other solutions"""
    
    def __init__(self):
        self.vectors: Dict[str, np.ndarray] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
    
    def add_vector(self, id: str, vector: List[float], metadata: Dict[str, Any] = None):
        """Add a vector with metadata"""
        self.vectors[id] = np.array(vector)
        if metadata:
            self.metadata[id] = metadata
    
    def search(self, query_vector: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
        """Find top-k most similar vectors"""
        query = np.array(query_vector)
        similarities = []
        
        for id, vector in self.vectors.items():
            # Cosine similarity
            similarity = np.dot(query, vector) / (np.linalg.norm(query) * np.linalg.norm(vector))
            similarities.append((id, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def delete_vector(self, id: str):
        """Remove a vector"""
        if id in self.vectors:
            del self.vectors[id]
            if id in self.metadata:
                del self.metadata[id]
```

## Success Criteria
- [ ] WhatsApp client adapter with all necessary methods
- [ ] OpenAI client adapter with chat completion and embeddings
- [ ] Database repository pattern implemented for all models
- [ ] Vector store adapter for semantic search (optional)
- [ ] All adapters handle errors gracefully
- [ ] No business logic in adapters (pure I/O operations)