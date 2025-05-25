# Task 12: Public Service Authentication Flow

## Overview
Implement the WhatsApp-based authentication flow for Zapa Public. Users authenticate by receiving a code via WhatsApp from the main service number, establishing trust without passwords.

## Prerequisites
- Task 04: Authentication Service (JWT generation)
- Task 06: WhatsApp Bridge Adapter (for sending auth codes)
- Task 10: Admin API Endpoints (to reuse auth patterns)

## Acceptance Criteria
1. POST /auth/request-code endpoint initiates auth flow
2. Auth codes sent via WhatsApp from main number
3. POST /auth/verify endpoint validates code and returns JWT
4. Codes expire after 5 minutes
5. Rate limiting prevents abuse
6. Users identified by phone number
7. Auto-creates user account on first auth
8. Secure code generation (6 digits)

## Test-Driven Development Steps

### Step 1: Create Auth Models
```python
# backend/zapa_public/models/auth.py
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
import re

class AuthCodeRequest(BaseModel):
    phone_number: str = Field(..., description="User's WhatsApp number")
    
    @validator('phone_number')
    def validate_phone(cls, v):
        # Remove any formatting
        cleaned = re.sub(r'[^\d+]', '', v)
        # Must start with + and country code
        if not re.match(r'^\+\d{10,15}$', cleaned):
            raise ValueError('Invalid phone number format. Use international format: +1234567890')
        return cleaned

class AuthCodeVerify(BaseModel):
    phone_number: str
    code: str = Field(..., min_length=6, max_length=6)
    
    @validator('code')
    def validate_code(cls, v):
        if not v.isdigit():
            raise ValueError('Code must be 6 digits')
        return v

class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours
    user_id: int
    phone_number: str
```

**Tests:**
```python
# backend/tests/unit/test_auth_models.py
def test_phone_validation():
    # Valid formats
    assert AuthCodeRequest(phone_number="+1234567890").phone_number == "+1234567890"
    assert AuthCodeRequest(phone_number="+1 (234) 567-8900").phone_number == "+12345678900"
    
    # Invalid formats
    with pytest.raises(ValidationError):
        AuthCodeRequest(phone_number="1234567890")  # Missing +
    with pytest.raises(ValidationError):
        AuthCodeRequest(phone_number="+123")  # Too short

def test_code_validation():
    # Valid
    assert AuthCodeVerify(phone_number="+1234567890", code="123456").code == "123456"
    
    # Invalid
    with pytest.raises(ValidationError):
        AuthCodeVerify(phone_number="+1234567890", code="12345")  # Too short
    with pytest.raises(ValidationError):
        AuthCodeVerify(phone_number="+1234567890", code="abcdef")  # Not digits
```

### Step 2: Create Auth Code Storage
```python
# backend/zapa_public/services/auth_store.py
from typing import Optional
from datetime import datetime, timedelta
import secrets
from redis import Redis
import json

class AuthCodeStore:
    """Store auth codes in Redis with expiration."""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.code_ttl = 300  # 5 minutes
        self.max_attempts = 3
        
    def generate_code(self) -> str:
        """Generate secure 6-digit code."""
        return ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    
    async def store_code(
        self, 
        phone_number: str, 
        code: Optional[str] = None
    ) -> str:
        """Store auth code for phone number."""
        if code is None:
            code = self.generate_code()
            
        key = f"auth_code:{phone_number}"
        data = {
            "code": code,
            "created_at": datetime.utcnow().isoformat(),
            "attempts": 0
        }
        
        await self.redis.setex(
            key, 
            self.code_ttl, 
            json.dumps(data)
        )
        
        return code
    
    async def verify_code(
        self, 
        phone_number: str, 
        code: str
    ) -> bool:
        """Verify auth code and increment attempts."""
        key = f"auth_code:{phone_number}"
        data_str = await self.redis.get(key)
        
        if not data_str:
            return False
            
        data = json.loads(data_str)
        
        # Check attempts
        if data["attempts"] >= self.max_attempts:
            await self.redis.delete(key)
            return False
        
        # Increment attempts
        data["attempts"] += 1
        await self.redis.setex(
            key,
            self.code_ttl,
            json.dumps(data)
        )
        
        # Check code
        if data["code"] == code:
            await self.redis.delete(key)  # One-time use
            return True
            
        return False
    
    async def get_rate_limit_key(self, phone_number: str) -> str:
        """Get rate limit key for phone number."""
        return f"auth_rate:{phone_number}"
    
    async def check_rate_limit(self, phone_number: str) -> bool:
        """Check if phone number is rate limited."""
        key = await self.get_rate_limit_key(phone_number)
        count = await self.redis.get(key)
        
        if count and int(count) >= 3:  # Max 3 requests per hour
            return False
            
        # Increment counter with 1 hour expiration
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 3600)
        await pipe.execute()
        
        return True
```

**Tests:**
```python
# backend/tests/unit/test_auth_store.py
@pytest.mark.asyncio
async def test_code_generation_and_storage(mock_redis):
    store = AuthCodeStore(mock_redis)
    
    code = await store.store_code("+1234567890")
    
    assert len(code) == 6
    assert code.isdigit()
    mock_redis.setex.assert_called_once()

@pytest.mark.asyncio
async def test_code_verification(mock_redis):
    store = AuthCodeStore(mock_redis)
    
    # Simulate stored code
    mock_redis.get.return_value = json.dumps({
        "code": "123456",
        "created_at": datetime.utcnow().isoformat(),
        "attempts": 0
    })
    
    # Correct code
    assert await store.verify_code("+1234567890", "123456") is True
    mock_redis.delete.assert_called_once()
    
    # Wrong code
    mock_redis.get.return_value = json.dumps({
        "code": "123456",
        "created_at": datetime.utcnow().isoformat(),
        "attempts": 1
    })
    assert await store.verify_code("+1234567890", "654321") is False
```

### Step 3: Create Public Auth Service
```python
# backend/zapa_public/services/public_auth_service.py
from typing import Optional, Tuple
from datetime import datetime, timedelta
from backend.shared.models import User
from backend.shared.database import get_db
from backend.zapa_public.services.auth_store import AuthCodeStore
from backend.zapa_private.adapters.whatsapp_bridge import WhatsAppBridgeAdapter
from backend.zapa_private.services.auth_service import AuthService
import logging

logger = logging.getLogger(__name__)

class PublicAuthService:
    def __init__(
        self,
        auth_store: AuthCodeStore,
        whatsapp_adapter: WhatsAppBridgeAdapter,
        auth_service: AuthService,
        main_phone_number: str
    ):
        self.auth_store = auth_store
        self.whatsapp = whatsapp_adapter
        self.auth_service = auth_service
        self.main_phone_number = main_phone_number
    
    async def request_auth_code(
        self, 
        phone_number: str
    ) -> Tuple[bool, str]:
        """Request auth code for phone number."""
        # Check rate limit
        if not await self.auth_store.check_rate_limit(phone_number):
            return False, "Rate limit exceeded. Try again later."
        
        # Generate and store code
        code = await self.auth_store.store_code(phone_number)
        
        # Send via WhatsApp
        message = (
            f"Your Zapa verification code is: {code}\n\n"
            "This code expires in 5 minutes.\n"
            "If you didn't request this, please ignore."
        )
        
        try:
            await self.whatsapp.send_message(
                to_number=phone_number,
                message=message,
                from_number=self.main_phone_number
            )
            
            logger.info(f"Auth code sent to {phone_number}")
            return True, "Code sent via WhatsApp"
            
        except Exception as e:
            logger.error(f"Failed to send auth code: {e}")
            # Still return success to prevent user enumeration
            return True, "Code sent via WhatsApp"
    
    async def verify_code_and_authenticate(
        self, 
        phone_number: str, 
        code: str,
        db_session
    ) -> Optional[AuthTokenResponse]:
        """Verify code and return JWT token."""
        # Verify code
        if not await self.auth_store.verify_code(phone_number, code):
            logger.warning(f"Invalid code attempt for {phone_number}")
            return None
        
        # Get or create user
        user = db_session.query(User).filter_by(
            phone_number=phone_number
        ).first()
        
        if not user:
            # Auto-create user on first auth
            user = User(
                phone_number=phone_number,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db_session.add(user)
            db_session.commit()
            logger.info(f"Created new user for {phone_number}")
        
        # Generate JWT token
        token = self.auth_service.create_access_token(
            user_id=user.id,
            phone_number=user.phone_number,
            is_admin=False  # Public users are never admins
        )
        
        return AuthTokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=86400,
            user_id=user.id,
            phone_number=user.phone_number
        )
```

**Tests:**
```python
# backend/tests/unit/test_public_auth_service.py
@pytest.mark.asyncio
async def test_request_auth_code_success(mock_services):
    service = PublicAuthService(
        auth_store=mock_services.auth_store,
        whatsapp_adapter=mock_services.whatsapp,
        auth_service=mock_services.auth,
        main_phone_number="+1234567890"
    )
    
    mock_services.auth_store.check_rate_limit.return_value = True
    mock_services.auth_store.store_code.return_value = "123456"
    mock_services.whatsapp.send_message.return_value = None
    
    success, message = await service.request_auth_code("+9876543210")
    
    assert success is True
    assert message == "Code sent via WhatsApp"
    mock_services.whatsapp.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_verify_code_creates_user(mock_services, test_db):
    service = PublicAuthService(
        auth_store=mock_services.auth_store,
        whatsapp_adapter=mock_services.whatsapp,
        auth_service=mock_services.auth,
        main_phone_number="+1234567890"
    )
    
    mock_services.auth_store.verify_code.return_value = True
    mock_services.auth.create_access_token.return_value = "jwt_token"
    
    result = await service.verify_code_and_authenticate(
        "+9876543210",
        "123456",
        test_db
    )
    
    assert result is not None
    assert result.access_token == "jwt_token"
    assert result.phone_number == "+9876543210"
    
    # Verify user was created
    user = test_db.query(User).filter_by(phone_number="+9876543210").first()
    assert user is not None
```

### Step 4: Create Public Auth API Endpoints
```python
# backend/zapa_public/api/auth.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.zapa_public.models.auth import (
    AuthCodeRequest,
    AuthCodeVerify,
    AuthTokenResponse
)
from backend.zapa_public.services.public_auth_service import PublicAuthService
from backend.zapa_public.core.dependencies import (
    get_public_auth_service,
    get_db
)

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/request-code", response_model=dict)
async def request_auth_code(
    request: AuthCodeRequest,
    auth_service: PublicAuthService = Depends(get_public_auth_service)
):
    """Request authentication code via WhatsApp."""
    success, message = await auth_service.request_auth_code(
        request.phone_number
    )
    
    if not success:
        raise HTTPException(status_code=429, detail=message)
    
    return {
        "success": True,
        "message": message,
        "phone_number": request.phone_number
    }

@router.post("/verify", response_model=AuthTokenResponse)
async def verify_auth_code(
    request: AuthCodeVerify,
    auth_service: PublicAuthService = Depends(get_public_auth_service),
    db: Session = Depends(get_db)
):
    """Verify authentication code and receive JWT token."""
    result = await auth_service.verify_code_and_authenticate(
        request.phone_number,
        request.code,
        db
    )
    
    if not result:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired code"
        )
    
    return result

@router.get("/me", response_model=dict)
async def get_current_user(
    current_user: dict = Depends(get_current_user)
):
    """Get current authenticated user info."""
    return {
        "user_id": current_user["user_id"],
        "phone_number": current_user["phone_number"],
        "is_authenticated": True
    }
```

**Tests:**
```python
# backend/tests/integration/test_public_auth_api.py
@pytest.mark.asyncio
async def test_auth_flow_complete(test_client, test_db, mock_redis):
    """Test complete authentication flow."""
    phone_number = "+1234567890"
    
    # Step 1: Request code
    response = await test_client.post(
        "/auth/request-code",
        json={"phone_number": phone_number}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    # Step 2: Get code from Redis (in real scenario from WhatsApp)
    key = f"auth_code:{phone_number}"
    stored_data = json.loads(await mock_redis.get(key))
    code = stored_data["code"]
    
    # Step 3: Verify code
    response = await test_client.post(
        "/auth/verify",
        json={
            "phone_number": phone_number,
            "code": code
        }
    )
    
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["phone_number"] == phone_number
    
    # Step 4: Use token to access protected endpoint
    response = await test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"}
    )
    
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["phone_number"] == phone_number
```

### Step 5: Add Security Middleware
```python
# backend/zapa_public/core/security.py
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict
from backend.zapa_private.services.auth_service import AuthService

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> Dict:
    """Validate JWT token and return user info."""
    token = credentials.credentials
    
    try:
        payload = auth_service.verify_access_token(token)
        
        # Public tokens should not have admin access
        if payload.get("is_admin", False):
            raise HTTPException(
                status_code=403,
                detail="Invalid token type"
            )
        
        return {
            "user_id": payload["user_id"],
            "phone_number": payload["phone_number"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

# Optional: Add rate limiting middleware
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Apply to auth endpoints
@router.post("/request-code", response_model=dict)
@limiter.limit("3/hour")
async def request_auth_code(...):
    # existing code
```

### Step 6: Add Phone Number Validation Service
```python
# backend/zapa_public/services/phone_validator.py
import phonenumbers
from phonenumbers import carrier, geocoder
from typing import Optional, Dict

class PhoneValidator:
    """Validate and normalize phone numbers."""
    
    @staticmethod
    def validate_and_format(phone_number: str) -> Optional[str]:
        """Validate phone number and return E.164 format."""
        try:
            # Parse number
            parsed = phonenumbers.parse(phone_number, None)
            
            # Check if valid
            if not phonenumbers.is_valid_number(parsed):
                return None
            
            # Return E.164 format
            return phonenumbers.format_number(
                parsed, 
                phonenumbers.PhoneNumberFormat.E164
            )
            
        except phonenumbers.NumberParseException:
            return None
    
    @staticmethod
    def get_number_info(phone_number: str) -> Dict:
        """Get carrier and location info for number."""
        try:
            parsed = phonenumbers.parse(phone_number, None)
            
            return {
                "carrier": carrier.name_for_number(parsed, "en"),
                "country": geocoder.country_name_for_number(parsed, "en"),
                "is_mobile": carrier.name_for_number(parsed, "en") != ""
            }
            
        except:
            return {}

# Use in auth service
async def request_auth_code(self, phone_number: str) -> Tuple[bool, str]:
    # Validate number format
    formatted = PhoneValidator.validate_and_format(phone_number)
    if not formatted:
        return False, "Invalid phone number format"
    
    # Check if mobile (optional)
    info = PhoneValidator.get_number_info(formatted)
    if not info.get("is_mobile", True):
        logger.warning(f"Non-mobile number: {formatted}")
    
    # Continue with auth flow...
```

## Integration Tests

```python
# backend/tests/integration/test_public_auth_integration.py
@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST_WHATSAPP", "false").lower() != "true",
    reason="WhatsApp integration tests disabled"
)
@pytest.mark.asyncio
async def test_real_whatsapp_code_delivery(
    test_client, 
    real_whatsapp_bridge,
    test_phone_number
):
    """Test actual WhatsApp code delivery."""
    response = await test_client.post(
        "/auth/request-code",
        json={"phone_number": test_phone_number}
    )
    
    assert response.status_code == 200
    
    # In real test, would check if message received
    # For now, just verify the flow completed

@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_rate_limiting(test_client):
    """Test rate limiting on auth endpoints."""
    phone_number = "+1234567890"
    
    # Make 3 requests (should succeed)
    for i in range(3):
        response = await test_client.post(
            "/auth/request-code",
            json={"phone_number": phone_number}
        )
        assert response.status_code == 200
    
    # 4th request should fail
    response = await test_client.post(
        "/auth/request-code",
        json={"phone_number": phone_number}
    )
    assert response.status_code == 429
```

## Implementation Notes

1. **Security**: 
   - Use cryptographically secure code generation
   - Implement rate limiting at multiple levels
   - One-time use codes with expiration
   - No user enumeration (always return success)

2. **User Experience**:
   - Clear messaging in WhatsApp notifications
   - Fast code delivery (async sending)
   - Auto-format phone numbers for consistency

3. **Scalability**:
   - Redis for distributed code storage
   - Stateless JWT tokens
   - Rate limiting per phone number

4. **Privacy**:
   - Minimal user data collection
   - Phone numbers hashed in logs
   - No password storage

## Dependencies
- Redis for auth code storage
- WhatsApp Bridge for code delivery
- JWT Auth Service for token generation
- FastAPI for API endpoints
- phonenumbers library for validation

## Next Steps
- Task 13: WhatsApp Bridge Integration
- Task 14: Frontend User Dashboard