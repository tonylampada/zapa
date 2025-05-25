# Task 05: Backend Services Implementation

## Objective
Implement the service layer containing all business logic and orchestration.

## Requirements
- Create services for sessions, messages, agents, and commands
- Services should orchestrate between adapters
- All business logic goes in services
- Services should be testable with mocked adapters

## Files to Create

### backend/app/services/session_service.py
```python
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import SessionModel, SessionStatus, SessionCreate, SessionResponse
from app.adapters.db_repository import SessionRepository, AgentRepository
from app.adapters.whatsapp_client import WhatsAppClient
from app.core.logging import logger

class SessionService:
    def __init__(self, db: Session):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.agent_repo = AgentRepository(db)
        self.whatsapp_client = WhatsAppClient()
    
    async def create_session(self, data: SessionCreate) -> SessionResponse:
        """Create a new WhatsApp session"""
        # Verify agent exists
        agent = self.agent_repo.get_by_id(data.agent_id)
        if not agent:
            raise ValueError(f"Agent with id {data.agent_id} not found")
        
        # Generate session ID if not provided
        session_id = data.session_id or f"session_{datetime.now().timestamp()}"
        
        # Create session in database
        session = SessionModel(
            id=session_id,
            agent_id=data.agent_id,
            status=SessionStatus.QR_PENDING
        )
        session = self.session_repo.create(session)
        
        try:
            # Request QR code from WhatsApp Bridge
            whatsapp_response = await self.whatsapp_client.create_session(session_id)
            
            # Update session with QR code
            session.qr_code = whatsapp_response.get("qr_code")
            session = self.session_repo.update(session)
            
            logger.info(f"Created session {session_id} with QR code")
            
        except Exception as e:
            # Update session status to error
            session.status = SessionStatus.ERROR
            self.session_repo.update(session)
            logger.error(f"Failed to create WhatsApp session: {str(e)}")
            raise
        
        return SessionResponse.from_orm(session)
    
    async def get_sessions(self, skip: int = 0, limit: int = 100) -> List[SessionResponse]:
        """Get all sessions"""
        sessions = self.session_repo.get_all(skip, limit)
        return [SessionResponse.from_orm(s) for s in sessions]
    
    async def get_session(self, session_id: str) -> Optional[SessionResponse]:
        """Get a specific session"""
        session = self.session_repo.get_by_id(session_id)
        if session:
            return SessionResponse.from_orm(session)
        return None
    
    async def update_session_status(self, session_id: str, status: SessionStatus, 
                                   phone_number: Optional[str] = None):
        """Update session status (called by webhook)"""
        session = self.session_repo.get_by_id(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for status update")
            return
        
        session.status = status
        
        if status == SessionStatus.CONNECTED:
            session.connected_at = datetime.utcnow()
            if phone_number:
                session.phone_number = phone_number
        elif status == SessionStatus.DISCONNECTED:
            session.disconnected_at = datetime.utcnow()
        
        self.session_repo.update(session)
        logger.info(f"Updated session {session_id} status to {status}")
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            # First disconnect from WhatsApp
            await self.whatsapp_client.delete_session(session_id)
        except Exception as e:
            logger.warning(f"Failed to disconnect WhatsApp session: {str(e)}")
        
        # Delete from database
        return self.session_repo.delete(session_id)
```

### backend/app/services/message_service.py
```python
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import json

from app.models import Message, MessageDirection, WebhookMessage
from app.adapters.db_repository import MessageRepository, SessionRepository
from app.services.agent_service import AgentService
from app.core.logging import logger

class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.session_repo = SessionRepository(db)
        self.agent_service = AgentService(db)
    
    async def process_incoming_message(self, webhook_data: WebhookMessage) -> Dict[str, Any]:
        """Process incoming message from WhatsApp webhook"""
        # Save message to database
        message = Message(
            session_id=webhook_data.session_id,
            contact_jid=webhook_data.contact_jid,
            direction=MessageDirection.INCOMING,
            message_type=webhook_data.message_type,
            content=webhook_data.content,
            metadata=webhook_data.metadata,
            timestamp=webhook_data.timestamp
        )
        self.message_repo.create(message)
        
        logger.info(f"Received message from {webhook_data.contact_jid} in session {webhook_data.session_id}")
        
        # Check if this is a command or regular message
        if self._is_command(webhook_data.content):
            # Process as command
            response = await self._process_command(webhook_data)
        else:
            # Generate AI response
            response = await self.agent_service.generate_response(
                session_id=webhook_data.session_id,
                contact_jid=webhook_data.contact_jid,
                user_message=webhook_data.content
            )
        
        # Save and send response if generated
        if response:
            await self._send_response(
                session_id=webhook_data.session_id,
                contact_jid=webhook_data.contact_jid,
                content=response
            )
        
        return {"status": "processed", "response_sent": bool(response)}
    
    def _is_command(self, content: str) -> bool:
        """Check if message is a command"""
        command_prefixes = ["#summarize", "#tasks", "#search"]
        return any(content.lower().startswith(prefix) for prefix in command_prefixes)
    
    async def _process_command(self, webhook_data: WebhookMessage) -> Optional[str]:
        """Process command messages"""
        content = webhook_data.content.lower()
        
        if content.startswith("#summarize"):
            # Delegate to command service
            from app.services.command_service import CommandService
            command_service = CommandService(self.db)
            return await command_service.summarize_chat(
                session_id=webhook_data.session_id,
                contact_jid=webhook_data.contact_jid
            )
        
        elif content.startswith("#tasks"):
            from app.services.command_service import CommandService
            command_service = CommandService(self.db)
            return await command_service.extract_tasks(
                session_id=webhook_data.session_id,
                contact_jid=webhook_data.contact_jid
            )
        
        elif content.startswith("#search"):
            query = content.replace("#search", "").strip()
            if query:
                from app.services.command_service import CommandService
                command_service = CommandService(self.db)
                return await command_service.search_messages(
                    session_id=webhook_data.session_id,
                    contact_jid=webhook_data.contact_jid,
                    query=query
                )
        
        return None
    
    async def _send_response(self, session_id: str, contact_jid: str, content: str):
        """Send response message via WhatsApp"""
        from app.adapters.whatsapp_client import WhatsAppClient
        whatsapp_client = WhatsAppClient()
        
        try:
            # Send via WhatsApp
            await whatsapp_client.send_message(
                session_id=session_id,
                to=contact_jid,
                message=content
            )
            
            # Save to database
            message = Message(
                session_id=session_id,
                contact_jid=contact_jid,
                direction=MessageDirection.OUTGOING,
                message_type="text",
                content=content,
                metadata={"generated_by": "agent"}
            )
            self.message_repo.create(message)
            
            logger.info(f"Sent response to {contact_jid}")
            
        except Exception as e:
            logger.error(f"Failed to send response: {str(e)}")
    
    def get_conversation(self, session_id: str, contact_jid: str, 
                        limit: int = 50, offset: int = 0):
        """Get conversation history"""
        messages = self.message_repo.get_conversation(
            session_id, contact_jid, limit, offset
        )
        return messages
```

### backend/app/services/agent_service.py
```python
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import json

from app.models import SessionModel, Agent, Message
from app.adapters.db_repository import SessionRepository, MessageRepository, AgentRepository
from app.adapters.openai_client import OpenAIClient
from app.core.logging import logger

class AgentService:
    def __init__(self, db: Session):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.message_repo = MessageRepository(db)
        self.agent_repo = AgentRepository(db)
        self.openai_client = OpenAIClient()
    
    async def generate_response(self, session_id: str, contact_jid: str, 
                               user_message: str) -> Optional[str]:
        """Generate AI response for user message"""
        # Get session and agent configuration
        session = self.session_repo.get_by_id(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return None
        
        agent = session.agent
        
        # Get conversation history
        recent_messages = self.message_repo.get_recent_messages(
            session_id, contact_jid, last_n=10
        )
        
        # Build conversation context
        messages = self._build_conversation_context(
            agent.system_prompt,
            recent_messages,
            user_message
        )
        
        try:
            # Call OpenAI with function definitions if available
            response = await self.openai_client.generate_chat_completion(
                messages=messages,
                model=agent.model,
                functions=agent.functions if agent.functions else None
            )
            
            # Handle function calls
            if "function_call" in response:
                result = await self._handle_function_call(
                    response["function_call"],
                    session_id,
                    contact_jid
                )
                
                # Get final response after function execution
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": response["function_call"]
                })
                messages.append({
                    "role": "function",
                    "name": response["function_call"]["name"],
                    "content": json.dumps(result)
                })
                
                final_response = await self.openai_client.generate_chat_completion(
                    messages=messages,
                    model=agent.model
                )
                return final_response["content"]
            
            return response["content"]
            
        except Exception as e:
            logger.error(f"Failed to generate AI response: {str(e)}")
            return "I apologize, but I'm having trouble processing your request right now."
    
    def _build_conversation_context(self, system_prompt: str, 
                                   recent_messages: List[Message], 
                                   current_message: str) -> List[Dict[str, str]]:
        """Build conversation context for LLM"""
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add recent messages in chronological order
        for msg in reversed(recent_messages):
            role = "user" if msg.direction == MessageDirection.INCOMING else "assistant"
            messages.append({
                "role": role,
                "content": msg.content
            })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": current_message
        })
        
        return messages
    
    async def _handle_function_call(self, function_call: Dict[str, Any], 
                                   session_id: str, contact_jid: str) -> Dict[str, Any]:
        """Handle OpenAI function calls"""
        function_name = function_call["name"]
        arguments = json.loads(function_call["arguments"])
        
        logger.info(f"Executing function: {function_name} with args: {arguments}")
        
        # Import command service to handle functions
        from app.services.command_service import CommandService
        command_service = CommandService(self.db)
        
        if function_name == "summarize_chat":
            last_n = arguments.get("last_n", 20)
            summary = await command_service.summarize_chat(
                session_id, contact_jid, last_n
            )
            return {"summary": summary}
        
        elif function_name == "extract_tasks":
            tasks = await command_service.extract_tasks(
                session_id, contact_jid
            )
            return {"tasks": tasks}
        
        elif function_name == "search_messages":
            query = arguments.get("query", "")
            results = await command_service.search_messages(
                session_id, contact_jid, query
            )
            return {"results": results}
        
        else:
            return {"error": f"Unknown function: {function_name}"}
```

### backend/app/services/command_service.py
```python
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import Message
from app.adapters.db_repository import MessageRepository
from app.adapters.openai_client import OpenAIClient
from app.adapters.vector_store import VectorStore
from app.core.logging import logger

class CommandService:
    def __init__(self, db: Session):
        self.db = db
        self.message_repo = MessageRepository(db)
        self.openai_client = OpenAIClient()
        self.vector_store = VectorStore()  # In-memory for now
    
    async def summarize_chat(self, session_id: str, contact_jid: str, 
                            last_n: int = 20) -> str:
        """Summarize recent chat messages"""
        # Get recent messages
        messages = self.message_repo.get_recent_messages(
            session_id, contact_jid, last_n
        )
        
        if not messages:
            return "No messages to summarize."
        
        # Build conversation text
        conversation = self._format_conversation(messages)
        
        # Use LLM to summarize
        prompt = f"Please provide a concise summary of the following conversation:\n\n{conversation}"
        
        try:
            response = await self.openai_client.generate_chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes conversations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            return response["content"]
            
        except Exception as e:
            logger.error(f"Failed to summarize chat: {str(e)}")
            return "Failed to generate summary."
    
    async def extract_tasks(self, session_id: str, contact_jid: str) -> List[str]:
        """Extract tasks/todos from conversation"""
        # Get all messages
        messages = self.message_repo.get_conversation(
            session_id, contact_jid, limit=100
        )
        
        if not messages:
            return []
        
        conversation = self._format_conversation(messages)
        
        prompt = """Extract all tasks, to-dos, or action items mentioned in this conversation.
        Return them as a simple list, one per line. If no tasks found, return 'No tasks found.'
        
        Conversation:
        """ + conversation
        
        try:
            response = await self.openai_client.generate_chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts tasks from conversations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            content = response["content"]
            if "No tasks found" in content:
                return []
            
            # Split into lines and clean
            tasks = [line.strip() for line in content.split('\n') 
                    if line.strip() and not line.strip().startswith('-')]
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to extract tasks: {str(e)}")
            return []
    
    async def search_messages(self, session_id: str, contact_jid: str, 
                             query: str) -> str:
        """Search messages using semantic search"""
        # For now, use simple text search
        # In production, would use vector embeddings
        
        results = self.message_repo.search_messages(
            session_id, query, limit=5
        )
        
        if not results:
            return f"No messages found matching '{query}'"
        
        # Format results
        formatted_results = []
        for msg in results:
            sender = "User" if msg.direction == MessageDirection.INCOMING else "Agent"
            formatted_results.append(
                f"[{msg.timestamp.strftime('%Y-%m-%d %H:%M')}] {sender}: {msg.content[:100]}..."
            )
        
        return "Found messages:\n" + "\n".join(formatted_results)
    
    def _format_conversation(self, messages: List[Message]) -> str:
        """Format messages into conversation text"""
        lines = []
        for msg in reversed(messages):  # Chronological order
            sender = "User" if msg.direction == MessageDirection.INCOMING else "Agent"
            lines.append(f"{sender}: {msg.content}")
        
        return "\n".join(lines)
```

## Success Criteria
- [ ] Session service handles full session lifecycle
- [ ] Message service processes incoming messages and routes appropriately
- [ ] Agent service integrates with OpenAI for intelligent responses
- [ ] Command service implements summarization, task extraction, and search
- [ ] All services use dependency injection for adapters
- [ ] Business logic properly separated from infrastructure concerns