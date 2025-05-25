# Task 06: Backend API Endpoints Implementation with Tests

## Objective
Implement FastAPI endpoints (surface layer) with comprehensive test coverage, following REST best practices.

## Prerequisites
- Tasks 01-05 completed
- Services and adapters fully tested
- All previous tests passing in CI/CD

## Requirements
- Create all API endpoints for sessions, messages, commands, and auth
- Implement proper request/response validation
- Add authentication middleware
- Write comprehensive API tests
- Ensure proper error handling and status codes

## Files to Create

### backend/app/api/dependencies.py
```python
from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import verify_token
from app.core.exceptions import UnauthorizedException

security = HTTPBearer()

def get_db() -> Generator:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> dict:
    """Dependency to get current authenticated user."""
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload:
        raise UnauthorizedException("Invalid authentication credentials")
    
    # In real app, would fetch user from DB
    # For now, return payload
    return payload

async def verify_webhook_auth(
    authorization: str = Depends(HTTPBearer(auto_error=False))
) -> bool:
    """Verify webhook authentication."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing webhook authentication"
        )
    
    # Check against configured webhook key
    from app.core.config import settings
    if authorization.credentials != settings.WHATSAPP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook authentication"
        )
    
    return True
```

### backend/app/api/sessions.py
```python
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.schemas import SessionCreate, SessionResponse
from app.services.session_service import SessionService
from app.core.exceptions import NotFoundException

router = APIRouter()

@router.post("/", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new WhatsApp session."""
    service = SessionService(db)
    try:
        return await service.create_session(session_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[SessionResponse])
async def list_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all WhatsApp sessions."""
    service = SessionService(db)
    return await service.get_sessions(skip, limit)

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific session by ID."""
    service = SessionService(db)
    session = await service.get_session(session_id)
    if not session:
        raise NotFoundException(f"Session {session_id} not found")
    return session

@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a WhatsApp session."""
    service = SessionService(db)
    success = await service.delete_session(session_id)
    if not success:
        raise NotFoundException(f"Session {session_id} not found")
    return {"message": "Session deleted successfully"}
```

### backend/app/api/messages.py
```python
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user, verify_webhook_auth
from app.models.schemas import MessageResponse, WebhookMessage, WebhookEvent
from app.services.message_service import MessageService
from app.services.session_service import SessionService

router = APIRouter()

@router.post("/webhook", include_in_schema=False)
async def webhook_handler(
    event: WebhookEvent,
    db: Session = Depends(get_db),
    auth: bool = Depends(verify_webhook_auth)
):
    """Handle incoming webhooks from WhatsApp Bridge."""
    if event.event_type == "message.received":
        # Process incoming message
        service = MessageService(db)
        webhook_msg = WebhookMessage(**event.data)
        result = await service.process_incoming_message(webhook_msg)
        return {"status": "ok", "result": result}
    
    elif event.event_type == "session.connected":
        # Update session status
        session_service = SessionService(db)
        await session_service.update_session_status(
            event.session_id,
            "connected",
            event.data.get("phone_number")
        )
        return {"status": "ok"}
    
    elif event.event_type == "session.disconnected":
        # Update session status
        session_service = SessionService(db)
        await session_service.update_session_status(
            event.session_id,
            "disconnected"
        )
        return {"status": "ok"}
    
    return {"status": "ignored", "reason": "Unknown event type"}

@router.get("/{session_id}/{contact_jid}", response_model=List[MessageResponse])
async def get_conversation(
    session_id: str,
    contact_jid: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get conversation history for a specific contact."""
    service = MessageService(db)
    messages = service.get_conversation(session_id, contact_jid, limit, offset)
    return messages
```

### backend/app/api/commands.py
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_current_user
from app.models.schemas import CommandRequest, CommandResponse
from app.services.command_service import CommandService

router = APIRouter()

@router.post("/summarize", response_model=CommandResponse)
async def summarize_chat(
    request: CommandRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Summarize a chat conversation."""
    service = CommandService(db)
    try:
        last_n = request.parameters.get("last_n", 20)
        summary = await service.summarize_chat(
            request.session_id,
            request.contact_jid,
            last_n
        )
        return CommandResponse(success=True, result=summary)
    except Exception as e:
        return CommandResponse(success=False, error=str(e))

@router.post("/extract-tasks", response_model=CommandResponse)
async def extract_tasks(
    request: CommandRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Extract tasks from a conversation."""
    service = CommandService(db)
    try:
        tasks = await service.extract_tasks(
            request.session_id,
            request.contact_jid
        )
        return CommandResponse(success=True, result=tasks)
    except Exception as e:
        return CommandResponse(success=False, error=str(e))

@router.post("/search", response_model=CommandResponse)
async def search_messages(
    request: CommandRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Search messages in a conversation."""
    service = CommandService(db)
    try:
        query = request.parameters.get("query", "")
        if not query:
            raise ValueError("Query parameter is required")
        
        results = await service.search_messages(
            request.session_id,
            request.contact_jid,
            query
        )
        return CommandResponse(success=True, result=results)
    except Exception as e:
        return CommandResponse(success=False, error=str(e))
```

### backend/app/api/auth.py
```python
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.schemas import UserLogin, Token, UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.core.config import settings

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    user_credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """Login and receive access token."""
    service = AuthService(db)
    user = service.authenticate_user(
        user_credentials.username,
        user_credentials.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = service.create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new admin user."""
    service = AuthService(db)
    
    # Check if user exists
    if service.get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered"
        )
    
    if service.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    user = service.create_user(user_data)
    return user
```

### backend/tests/test_api_sessions.py
```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from app.main import app
from app.models.schemas import SessionResponse

@pytest.fixture
def authorized_client(client):
    """Client with authorization header."""
    token = "test-token"
    with patch("app.core.security.verify_token") as mock_verify:
        mock_verify.return_value = {"sub": "testuser", "user_id": 1}
        client.headers = {"Authorization": f"Bearer {token}"}
        yield client

@pytest.mark.asyncio
async def test_create_session(authorized_client, db_session):
    """Test session creation endpoint."""
    with patch("app.services.session_service.SessionService.create_session") as mock_create:
        mock_response = SessionResponse(
            id="session123",
            status="qr_pending",
            phone_number=None,
            qr_code="mock_qr_code",
            agent_id=1,
            agent={"id": 1, "name": "Test Agent"},
            connected_at=None,
            created_at="2024-01-01T00:00:00"
        )
        mock_create.return_value = mock_response
        
        response = authorized_client.post(
            "/api/v1/sessions/",
            json={"agent_id": 1}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "session123"
        assert data["status"] == "qr_pending"

def test_create_session_unauthorized(client):
    """Test session creation without auth."""
    response = client.post(
        "/api/v1/sessions/",
        json={"agent_id": 1}
    )
    assert response.status_code == 403  # Forbidden without auth

def test_list_sessions(authorized_client):
    """Test listing sessions."""
    with patch("app.services.session_service.SessionService.get_sessions") as mock_get:
        mock_get.return_value = [
            {"id": "s1", "status": "connected"},
            {"id": "s2", "status": "qr_pending"}
        ]
        
        response = authorized_client.get("/api/v1/sessions/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "s1"

def test_get_session_not_found(authorized_client):
    """Test getting non-existent session."""
    with patch("app.services.session_service.SessionService.get_session") as mock_get:
        mock_get.return_value = None
        
        response = authorized_client.get("/api/v1/sessions/nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

def test_delete_session(authorized_client):
    """Test session deletion."""
    with patch("app.services.session_service.SessionService.delete_session") as mock_delete:
        mock_delete.return_value = True
        
        response = authorized_client.delete("/api/v1/sessions/session123")
        
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]
```

### backend/tests/test_api_messages.py
```python
import pytest
from datetime import datetime
from unittest.mock import patch

def test_webhook_message_received(client):
    """Test webhook for incoming message."""
    with patch("app.services.message_service.MessageService.process_incoming_message") as mock_process:
        mock_process.return_value = {"status": "processed", "response_sent": True}
        
        # Add webhook auth
        headers = {"Authorization": "Bearer test-api-key"}
        
        webhook_data = {
            "event_type": "message.received",
            "session_id": "session123",
            "data": {
                "session_id": "session123",
                "contact_jid": "+1234567890",
                "message_type": "text",
                "content": "Hello",
                "timestamp": datetime.now().isoformat(),
                "metadata": {}
            }
        }
        
        response = client.post(
            "/api/v1/messages/webhook",
            json=webhook_data,
            headers=headers
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

def test_webhook_unauthorized(client):
    """Test webhook without proper auth."""
    webhook_data = {
        "event_type": "message.received",
        "session_id": "session123",
        "data": {}
    }
    
    response = client.post("/api/v1/messages/webhook", json=webhook_data)
    assert response.status_code == 403

def test_webhook_session_connected(client):
    """Test webhook for session connected event."""
    with patch("app.services.session_service.SessionService.update_session_status") as mock_update:
        headers = {"Authorization": "Bearer test-api-key"}
        
        webhook_data = {
            "event_type": "session.connected",
            "session_id": "session123",
            "data": {
                "phone_number": "+1234567890"
            }
        }
        
        response = client.post(
            "/api/v1/messages/webhook",
            json=webhook_data,
            headers=headers
        )
        
        assert response.status_code == 200
        mock_update.assert_called_once_with(
            "session123",
            "connected",
            "+1234567890"
        )

def test_get_conversation(authorized_client):
    """Test getting conversation history."""
    with patch("app.services.message_service.MessageService.get_conversation") as mock_get:
        mock_get.return_value = [
            {
                "id": 1,
                "content": "Hello",
                "direction": "incoming",
                "timestamp": datetime.now().isoformat()
            }
        ]
        
        response = authorized_client.get(
            "/api/v1/messages/session123/+1234567890?limit=10"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "Hello"
```

### backend/tests/test_api_commands.py
```python
import pytest
from unittest.mock import patch

def test_summarize_command(authorized_client):
    """Test summarize command endpoint."""
    with patch("app.services.command_service.CommandService.summarize_chat") as mock_summarize:
        mock_summarize.return_value = "This is a summary of the chat."
        
        request_data = {
            "session_id": "session123",
            "contact_jid": "+1234567890",
            "command": "summarize",
            "parameters": {"last_n": 10}
        }
        
        response = authorized_client.post(
            "/api/v1/commands/summarize",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "summary" in data["result"]

def test_extract_tasks_command(authorized_client):
    """Test extract tasks command."""
    with patch("app.services.command_service.CommandService.extract_tasks") as mock_extract:
        mock_extract.return_value = ["Task 1", "Task 2"]
        
        request_data = {
            "session_id": "session123",
            "contact_jid": "+1234567890",
            "command": "extract_tasks",
            "parameters": {}
        }
        
        response = authorized_client.post(
            "/api/v1/commands/extract-tasks",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["result"]) == 2

def test_search_command_missing_query(authorized_client):
    """Test search command without query parameter."""
    request_data = {
        "session_id": "session123",
        "contact_jid": "+1234567890",
        "command": "search",
        "parameters": {}
    }
    
    response = authorized_client.post(
        "/api/v1/commands/search",
        json=request_data
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Query parameter is required" in data["error"]

def test_command_error_handling(authorized_client):
    """Test command error handling."""
    with patch("app.services.command_service.CommandService.summarize_chat") as mock_summarize:
        mock_summarize.side_effect = Exception("Service error")
        
        request_data = {
            "session_id": "session123",
            "contact_jid": "+1234567890",
            "command": "summarize",
            "parameters": {}
        }
        
        response = authorized_client.post(
            "/api/v1/commands/summarize",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Service error" in data["error"]
```

### backend/tests/test_api_auth.py
```python
import pytest
from unittest.mock import patch, Mock

def test_login_success(client):
    """Test successful login."""
    with patch("app.services.auth_service.AuthService.authenticate_user") as mock_auth:
        mock_user = Mock(id=1, username="testuser")
        mock_auth.return_value = mock_user
        
        with patch("app.services.auth_service.AuthService.create_access_token") as mock_token:
            mock_token.return_value = "test-token-123"
            
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "testuser", "password": "testpass"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "test-token-123"
            assert data["token_type"] == "bearer"

def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    with patch("app.services.auth_service.AuthService.authenticate_user") as mock_auth:
        mock_auth.return_value = None
        
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "wrong", "password": "wrong"}
        )
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

def test_register_success(client):
    """Test successful registration."""
    with patch("app.services.auth_service.AuthService.get_user_by_username") as mock_get_user:
        mock_get_user.return_value = None
        
        with patch("app.services.auth_service.AuthService.get_user_by_email") as mock_get_email:
            mock_get_email.return_value = None
            
            with patch("app.services.auth_service.AuthService.create_user") as mock_create:
                mock_create.return_value = Mock(
                    id=1,
                    username="newuser",
                    email="new@example.com",
                    is_active=True,
                    created_at=datetime.now()
                )
                
                response = client.post(
                    "/api/v1/auth/register",
                    json={
                        "username": "newuser",
                        "email": "new@example.com",
                        "password": "securepass"
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["username"] == "newuser"

def test_register_duplicate_username(client):
    """Test registration with existing username."""
    with patch("app.services.auth_service.AuthService.get_user_by_username") as mock_get:
        mock_get.return_value = Mock()  # User exists
        
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "existing",
                "email": "new@example.com",
                "password": "pass"
            }
        )
        
        assert response.status_code == 409
        assert "Username already registered" in response.json()["detail"]
```

## Updated main.py
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, sessions, messages, commands
from app.core.config import settings
from app.core.exceptions import BadRequestException

app = FastAPI(
    title="WhatsApp Agent API",
    version="1.0.0",
    description="Backend API for WhatsApp Agent System"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(messages.router, prefix="/api/v1/messages", tags=["messages"])
app.include_router(commands.router, prefix="/api/v1/commands", tags=["commands"])

# Health check remains at root
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-agent-backend"}
```

## Success Criteria
- [ ] All API endpoints implemented
- [ ] Proper authentication on protected endpoints
- [ ] Webhook authentication working
- [ ] Request/response validation with Pydantic
- [ ] Comprehensive error handling
- [ ] All tests passing
- [ ] API documentation generated (OpenAPI)
- [ ] Code coverage above 90%

## Commands to Run
```bash
cd backend

# Run API tests
uv run pytest tests/test_api_sessions.py -v
uv run pytest tests/test_api_messages.py -v
uv run pytest tests/test_api_commands.py -v
uv run pytest tests/test_api_auth.py -v

# Run all tests
uv run pytest tests -v

# Test API manually
uv run uvicorn app.main:app --reload

# View API docs at http://localhost:8000/docs
```