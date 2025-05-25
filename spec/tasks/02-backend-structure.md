# Task 02: Backend Structure Implementation

## Objective
Create the FastAPI backend structure following the plumbing+intelligence architecture pattern.

## Requirements
- Set up FastAPI application with proper configuration
- Create base structure for API routers
- Implement dependency injection setup
- Create base exception handling

## Files to Create

### backend/app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, sessions, messages, commands
from app.core.config import settings

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

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### backend/app/core/config.py
```python
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Security
    SECRET_KEY: str
    ADMIN_TOKEN_SECRET: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # WhatsApp Bridge
    WHATSAPP_API_URL: str
    WHATSAPP_API_KEY: str
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Redis (optional)
    REDIS_URL: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:8080"]
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### backend/app/core/dependencies.py
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import verify_token

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user = verify_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return user
```

### backend/app/core/database.py
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
```

### backend/app/api/__init__.py
```python
# Empty file to make api a package
```

### backend/app/api/base.py
```python
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user

class AuthenticatedRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dependencies.append(Depends(get_current_user))
```

## Directory Structure After Task
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py ✓
│   ├── api/
│   │   ├── __init__.py ✓
│   │   ├── base.py ✓
│   │   ├── auth.py (placeholder)
│   │   ├── sessions.py (placeholder)
│   │   ├── messages.py (placeholder)
│   │   └── commands.py (placeholder)
│   └── core/
│       ├── __init__.py
│       ├── config.py ✓
│       ├── dependencies.py ✓
│       ├── database.py ✓
│       └── security.py (placeholder)
```

## Success Criteria
- [ ] FastAPI app initialized with proper configuration
- [ ] Core configuration management implemented
- [ ] Database connection setup
- [ ] Dependency injection pattern established
- [ ] Base router structure created
- [ ] All files follow the plumbing+intelligence separation