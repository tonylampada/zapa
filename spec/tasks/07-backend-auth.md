# Task 07: Backend Authentication Service Implementation

## Objective
Implement the authentication service layer with user management, JWT tokens, and comprehensive security features.

## Prerequisites
- Tasks 01-06 completed
- API endpoints structure in place
- All previous tests passing

## Requirements
- Create AuthService for user authentication
- Implement user management (create, authenticate)
- Add password security best practices
- Create comprehensive tests
- Implement rate limiting for login attempts

## Files to Create

### backend/app/services/auth_service.py
```python
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models.models import User
from app.models.schemas import UserCreate
from app.adapters.db_repository import UserRepository
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.logging import logger

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.max_login_attempts = 5
        self.lockout_duration = timedelta(minutes=15)
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password."""
        user = self.user_repo.get_by_username(username)
        
        if not user:
            logger.warning(f"Login attempt for non-existent user: {username}")
            return None
        
        if not user.is_active:
            logger.warning(f"Login attempt for inactive user: {username}")
            return None
        
        # Check if account is locked
        if self._is_account_locked(user):
            logger.warning(f"Login attempt for locked account: {username}")
            return None
        
        if not verify_password(password, user.hashed_password):
            # Record failed attempt
            self._record_failed_attempt(user)
            logger.warning(f"Invalid password for user: {username}")
            return None
        
        # Reset failed attempts on successful login
        self._reset_failed_attempts(user)
        logger.info(f"Successful login for user: {username}")
        
        return user
    
    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        # Hash the password
        hashed_password = get_password_hash(user_data.password)
        
        # Create user object
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password
        )
        
        # Save to database
        created_user = self.user_repo.create(user)
        logger.info(f"Created new user: {user_data.username}")
        
        return created_user
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.user_repo.get_by_username(username)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.user_repo.get_by_email(email)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        return create_access_token(data, expires_delta)
    
    def _is_account_locked(self, user: User) -> bool:
        """Check if account is locked due to failed attempts."""
        if not hasattr(user, 'failed_login_attempts'):
            return False
        
        if user.failed_login_attempts >= self.max_login_attempts:
            if user.last_failed_login:
                lockout_end = user.last_failed_login + self.lockout_duration
                if datetime.utcnow() < lockout_end:
                    return True
                else:
                    # Lockout period expired, reset attempts
                    self._reset_failed_attempts(user)
        
        return False
    
    def _record_failed_attempt(self, user: User):
        """Record a failed login attempt."""
        if not hasattr(user, 'failed_login_attempts'):
            user.failed_login_attempts = 0
        
        user.failed_login_attempts += 1
        user.last_failed_login = datetime.utcnow()
        self.db.commit()
    
    def _reset_failed_attempts(self, user: User):
        """Reset failed login attempts."""
        user.failed_login_attempts = 0
        user.last_failed_login = None
        self.db.commit()
```

### backend/app/models/models.py (update User model)
```python
# Add to User model
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0)
    last_failed_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### backend/tests/test_auth_service.py
```python
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.models import User
from app.services.auth_service import AuthService
from app.core.security import get_password_hash

@pytest.fixture
def db_session():
    """Create test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def auth_service(db_session):
    """Create AuthService instance."""
    return AuthService(db_session)

@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123")
    )
    db_session.add(user)
    db_session.commit()
    return user

def test_authenticate_user_success(auth_service, test_user):
    """Test successful user authentication."""
    result = auth_service.authenticate_user("testuser", "testpass123")
    
    assert result is not None
    assert result.username == "testuser"
    assert result.failed_login_attempts == 0

def test_authenticate_user_wrong_password(auth_service, test_user):
    """Test authentication with wrong password."""
    result = auth_service.authenticate_user("testuser", "wrongpass")
    
    assert result is None
    # Check failed attempt was recorded
    assert test_user.failed_login_attempts == 1
    assert test_user.last_failed_login is not None

def test_authenticate_nonexistent_user(auth_service):
    """Test authentication for non-existent user."""
    result = auth_service.authenticate_user("nouser", "pass")
    assert result is None

def test_authenticate_inactive_user(auth_service, test_user):
    """Test authentication for inactive user."""
    test_user.is_active = False
    auth_service.db.commit()
    
    result = auth_service.authenticate_user("testuser", "testpass123")
    assert result is None

def test_account_lockout(auth_service, test_user):
    """Test account lockout after failed attempts."""
    # Make 5 failed attempts
    for _ in range(5):
        auth_service.authenticate_user("testuser", "wrongpass")
    
    # Account should be locked
    result = auth_service.authenticate_user("testuser", "testpass123")
    assert result is None
    assert test_user.failed_login_attempts == 5

def test_account_lockout_expiry(auth_service, test_user):
    """Test account lockout expiry."""
    # Lock the account
    test_user.failed_login_attempts = 5
    test_user.last_failed_login = datetime.utcnow() - timedelta(minutes=20)
    auth_service.db.commit()
    
    # Should be able to login after lockout period
    result = auth_service.authenticate_user("testuser", "testpass123")
    assert result is not None
    assert test_user.failed_login_attempts == 0

def test_create_user(auth_service):
    """Test user creation."""
    from app.models.schemas import UserCreate
    
    user_data = UserCreate(
        username="newuser",
        email="new@example.com",
        password="securepass123"
    )
    
    created_user = auth_service.create_user(user_data)
    
    assert created_user.id is not None
    assert created_user.username == "newuser"
    assert created_user.email == "new@example.com"
    assert created_user.hashed_password != "securepass123"
    
    # Verify can authenticate
    result = auth_service.authenticate_user("newuser", "securepass123")
    assert result is not None

def test_get_user_by_username(auth_service, test_user):
    """Test getting user by username."""
    found = auth_service.get_user_by_username("testuser")
    assert found is not None
    assert found.id == test_user.id
    
    not_found = auth_service.get_user_by_username("nouser")
    assert not_found is None

def test_get_user_by_email(auth_service, test_user):
    """Test getting user by email."""
    found = auth_service.get_user_by_email("test@example.com")
    assert found is not None
    assert found.id == test_user.id
    
    not_found = auth_service.get_user_by_email("no@example.com")
    assert not_found is None

def test_create_access_token(auth_service):
    """Test JWT token creation."""
    data = {"sub": "testuser", "user_id": 1}
    token = auth_service.create_access_token(data)
    
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Test with custom expiration
    token_short = auth_service.create_access_token(
        data, 
        expires_delta=timedelta(minutes=5)
    )
    assert isinstance(token_short, str)
```

### backend/tests/test_password_security.py
```python
import pytest
from app.core.security import get_password_hash, verify_password

def test_password_hash_uniqueness():
    """Test that same password produces different hashes."""
    password = "testpassword123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)
    
    # Hashes should be different due to salt
    assert hash1 != hash2
    
    # But both should verify correctly
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)

def test_password_complexity():
    """Test password complexity requirements."""
    # This would be implemented in the schema validation
    from pydantic import ValidationError
    from app.models.schemas import UserCreate
    
    # Test weak password (if we implement validation)
    # with pytest.raises(ValidationError):
    #     UserCreate(
    #         username="user",
    #         email="test@example.com",
    #         password="123"  # Too short
    #     )

def test_password_timing_attack_resistance():
    """Test that password verification is timing-attack resistant."""
    import time
    
    password = "correctpassword"
    wrong_password = "wrongpassword"
    hash_val = get_password_hash(password)
    
    # Time correct password verification
    start = time.time()
    for _ in range(100):
        verify_password(password, hash_val)
    correct_time = time.time() - start
    
    # Time wrong password verification
    start = time.time()
    for _ in range(100):
        verify_password(wrong_password, hash_val)
    wrong_time = time.time() - start
    
    # Times should be similar (within 20% difference)
    # bcrypt is designed to be timing-attack resistant
    time_diff = abs(correct_time - wrong_time)
    avg_time = (correct_time + wrong_time) / 2
    
    assert time_diff < (avg_time * 0.2)
```

### backend/app/middleware/rate_limit.py
```python
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

class RateLimitMiddleware:
    """Rate limiting middleware for login attempts."""
    
    def __init__(self, app, calls: int = 5, period: timedelta = timedelta(minutes=1)):
        self.app = app
        self.calls = calls
        self.period = period
        self.clients = defaultdict(list)
        
        # Start cleanup task
        asyncio.create_task(self._cleanup())
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Only rate limit login endpoint
            if request.url.path == "/api/v1/auth/login":
                client_ip = request.client.host
                now = datetime.utcnow()
                
                # Clean old entries
                self.clients[client_ip] = [
                    timestamp for timestamp in self.clients[client_ip]
                    if now - timestamp < self.period
                ]
                
                # Check rate limit
                if len(self.clients[client_ip]) >= self.calls:
                    response = JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"detail": "Too many login attempts. Please try again later."}
                    )
                    await response(scope, receive, send)
                    return
                
                # Record this request
                self.clients[client_ip].append(now)
        
        await self.app(scope, receive, send)
    
    async def _cleanup(self):
        """Periodic cleanup of old entries."""
        while True:
            await asyncio.sleep(60)  # Clean every minute
            now = datetime.utcnow()
            
            for client_ip in list(self.clients.keys()):
                self.clients[client_ip] = [
                    timestamp for timestamp in self.clients[client_ip]
                    if now - timestamp < self.period
                ]
                
                if not self.clients[client_ip]:
                    del self.clients[client_ip]
```

### backend/tests/test_rate_limit.py
```python
import pytest
import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware.rate_limit import RateLimitMiddleware

@pytest.fixture
def app_with_rate_limit():
    """Create app with rate limiting."""
    app = FastAPI()
    
    @app.post("/api/v1/auth/login")
    async def login():
        return {"token": "test"}
    
    @app.get("/other")
    async def other():
        return {"data": "test"}
    
    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware, calls=3, period=timedelta(minutes=1))
    
    return app

def test_rate_limit_login(app_with_rate_limit):
    """Test rate limiting on login endpoint."""
    client = TestClient(app_with_rate_limit)
    
    # First 3 requests should succeed
    for i in range(3):
        response = client.post("/api/v1/auth/login")
        assert response.status_code == 200
    
    # 4th request should be rate limited
    response = client.post("/api/v1/auth/login")
    assert response.status_code == 429
    assert "Too many login attempts" in response.json()["detail"]

def test_rate_limit_other_endpoints(app_with_rate_limit):
    """Test that other endpoints are not rate limited."""
    client = TestClient(app_with_rate_limit)
    
    # Many requests to other endpoint should work
    for i in range(10):
        response = client.get("/other")
        assert response.status_code == 200
```

### Updated backend/app/main.py
```python
# Add to main.py
from app.middleware.rate_limit import RateLimitMiddleware

# Add after CORS middleware
app.add_middleware(RateLimitMiddleware, calls=5, period=timedelta(minutes=1))
```

## Database Migration
```sql
-- Add columns to users table
ALTER TABLE users 
ADD COLUMN failed_login_attempts INTEGER DEFAULT 0,
ADD COLUMN last_failed_login TIMESTAMP;
```

## Success Criteria
- [ ] AuthService fully implemented with security features
- [ ] Password hashing and verification working
- [ ] Account lockout after failed attempts
- [ ] JWT token generation working
- [ ] Rate limiting on login endpoint
- [ ] All tests passing
- [ ] Code coverage above 90%

## Commands to Run
```bash
cd backend

# Run auth tests
uv run pytest tests/test_auth_service.py -v
uv run pytest tests/test_password_security.py -v
uv run pytest tests/test_rate_limit.py -v

# Run security tests
uv run pytest tests/test_security.py -v

# Create migration for user updates
uv run alembic revision --autogenerate -m "Add login attempt tracking to users"
uv run alembic upgrade head
```