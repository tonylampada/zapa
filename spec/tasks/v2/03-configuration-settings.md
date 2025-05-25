# Task 03: Core Configuration and Settings

## Objective
Create a robust configuration system for both services with proper validation, environment-specific settings, and comprehensive tests.

## Prerequisites
- Tasks 01-02 completed
- Database models and schemas working
- All tests passing in CI/CD

## Success Criteria
- [ ] Configuration classes for both services
- [ ] Environment variable validation with Pydantic
- [ ] Development, test, and production configurations
- [ ] Encryption utilities for sensitive data
- [ ] Unit tests for all configuration scenarios
- [ ] Tests passing locally and in CI/CD

## Files to Create

### shared/config/__init__.py
```python
from .base import BaseSettings
from .encryption import EncryptionManager
from .database import DatabaseConfig

__all__ = ["BaseSettings", "EncryptionManager", "DatabaseConfig"]
```

### shared/config/base.py
```python
"""Base configuration settings."""
from typing import List, Optional, Literal
from pydantic import Field, validator
from pydantic_settings import BaseSettings as PydanticBaseSettings


class BaseSettings(PydanticBaseSettings):
    """Base settings for all services."""
    
    # Environment
    ENVIRONMENT: Literal["development", "test", "production"] = Field(
        default="development", description="Application environment"
    )
    DEBUG: bool = Field(default=True, description="Debug mode")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    
    # API Settings
    API_V1_STR: str = Field(default="/api/v1", description="API version prefix")
    PROJECT_NAME: str = Field(default="Zapa", description="Project name")
    
    # Security
    SECRET_KEY: str = Field(
        ..., min_length=32, description="Secret key for JWT signing"
    )
    ENCRYPTION_KEY: str = Field(
        ..., min_length=32, description="Key for encrypting user API keys"
    )
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3100",  # Private frontend
            "http://localhost:3200",  # Public frontend
        ]
    )
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("SECRET_KEY", "ENCRYPTION_KEY")
    def validate_keys(cls, v):
        """Validate that keys are strong enough."""
        if len(v) < 32:
            raise ValueError("Key must be at least 32 characters long")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
```

### shared/config/database.py
```python
"""Database configuration."""
from typing import Optional
from pydantic import Field, validator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .base import BaseSettings


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""
    
    # Database
    DATABASE_URL: str = Field(
        ..., description="PostgreSQL database URL"
    )
    DATABASE_POOL_SIZE: int = Field(
        default=5, ge=1, le=20, description="Database connection pool size"
    )
    DATABASE_MAX_OVERFLOW: int = Field(
        default=10, ge=0, le=50, description="Database max overflow connections"
    )
    DATABASE_ECHO: bool = Field(
        default=False, description="Echo SQL queries"
    )
    
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0", description="Redis URL"
    )
    REDIS_KEY_PREFIX: str = Field(
        default="zapa:", description="Redis key prefix"
    )
    REDIS_SESSION_TTL: int = Field(
        default=3600, ge=300, description="Session TTL in seconds"
    )
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v
    
    @validator("REDIS_URL")
    def validate_redis_url(cls, v):
        """Validate Redis URL format."""
        if not v.startswith("redis://"):
            raise ValueError("REDIS_URL must be a Redis URL")
        return v
    
    def get_database_engine(self):
        """Create SQLAlchemy engine."""
        return create_engine(
            self.DATABASE_URL,
            pool_size=self.DATABASE_POOL_SIZE,
            max_overflow=self.DATABASE_MAX_OVERFLOW,
            echo=self.DATABASE_ECHO,
        )
    
    def get_session_maker(self):
        """Create SQLAlchemy session maker."""
        engine = self.get_database_engine()
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### shared/config/encryption.py
```python
"""Encryption utilities for sensitive data."""
import base64
import secrets
from typing import str as String
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    """Handles encryption/decryption of sensitive data."""
    
    def __init__(self, encryption_key: String):
        """
        Initialize encryption manager.
        
        Args:
            encryption_key: Base encryption key (will be derived)
        """
        self.encryption_key = encryption_key
        self._fernet: Optional[Fernet] = None
    
    @property
    def fernet(self) -> Fernet:
        """Get Fernet cipher instance."""
        if self._fernet is None:
            # Derive key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"zapa_salt_2024",  # In production, use random salt per user
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.encryption_key.encode()))
            self._fernet = Fernet(key)
        return self._fernet
    
    def encrypt(self, plaintext: String) -> String:
        """
        Encrypt plaintext string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64 encoded encrypted string
        """
        if not plaintext:
            return ""
        
        encrypted_bytes = self.fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted_bytes).decode()
    
    def decrypt(self, ciphertext: String) -> String:
        """
        Decrypt ciphertext string.
        
        Args:
            ciphertext: Base64 encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""
        
        try:
            encrypted_bytes = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {e}")
    
    @classmethod
    def generate_key(cls) -> String:
        """Generate a secure random key."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
```

### services/private/app/core/config.py
```python
"""Private service configuration."""
from typing import Optional
from pydantic import Field
from zapa_shared.config import BaseSettings, DatabaseConfig


class PrivateServiceSettings(BaseSettings, DatabaseConfig):
    """Configuration for Zapa Private service."""
    
    # Service Info
    SERVICE_NAME: str = Field(default="zapa-private")
    VERSION: str = Field(default="0.1.0")
    
    # External Services
    WHATSAPP_BRIDGE_URL: str = Field(
        default="http://localhost:3000",
        description="WhatsApp Bridge (zapw) service URL"
    )
    WHATSAPP_BRIDGE_TIMEOUT: float = Field(
        default=30.0, ge=5.0, le=300.0, description="WhatsApp Bridge timeout"
    )
    
    # Webhook
    WEBHOOK_BASE_URL: str = Field(
        default="http://localhost:8001",
        description="Base URL for webhooks from external services"
    )
    
    # Admin Authentication
    ADMIN_TOKEN_SECRET: str = Field(
        ..., min_length=32, description="Admin JWT token secret"
    )
    ADMIN_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24, ge=30, description="Admin token expiry in minutes"
    )
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60, ge=1)
    
    # Integration Tests
    INTEGRATION_TEST_WHATSAPP: bool = Field(default=False)
    INTEGRATION_TEST_OPENAI: bool = Field(default=False)
    INTEGRATION_TEST_ANTHROPIC: bool = Field(default=False)
    INTEGRATION_TEST_GOOGLE: bool = Field(default=False)
    
    @property
    def webhook_url(self) -> str:
        """Get full webhook URL."""
        return f"{self.WEBHOOK_BASE_URL.rstrip('/')}/api/v1/webhooks/whatsapp"


# Global settings instance
settings = PrivateServiceSettings()
```

### services/public/app/core/config.py
```python
"""Public service configuration."""
from typing import List
from pydantic import Field, validator
from zapa_shared.config import BaseSettings, DatabaseConfig


class PublicServiceSettings(BaseSettings, DatabaseConfig):
    """Configuration for Zapa Public service."""
    
    # Service Info
    SERVICE_NAME: str = Field(default="zapa-public")
    VERSION: str = Field(default="0.1.0")
    
    # Authentication
    AUTH_CODE_LENGTH: int = Field(default=6, ge=4, le=8)
    AUTH_CODE_EXPIRE_MINUTES: int = Field(default=5, ge=1, le=15)
    JWT_TOKEN_EXPIRE_HOURS: int = Field(default=24, ge=1, le=168)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1, le=90)
    
    # Rate Limiting
    AUTH_RATE_LIMIT_PER_HOUR: int = Field(default=10, ge=1, le=100)
    API_RATE_LIMIT_PER_MINUTE: int = Field(default=100, ge=1)
    
    # Private Service Communication
    PRIVATE_SERVICE_URL: str = Field(
        default="http://localhost:8001",
        description="URL of private service for internal communication"
    )
    PRIVATE_SERVICE_TIMEOUT: float = Field(
        default=10.0, ge=1.0, le=60.0
    )
    PRIVATE_SERVICE_SECRET: str = Field(
        ..., min_length=32, description="Shared secret for service-to-service auth"
    )
    
    # Data Access
    MAX_MESSAGES_PER_REQUEST: int = Field(default=100, ge=1, le=1000)
    MAX_SEARCH_RESULTS: int = Field(default=50, ge=1, le=200)
    MESSAGE_HISTORY_DAYS: int = Field(default=365, ge=1)
    
    @validator("CORS_ORIGINS", pre=True)
    def set_public_cors_origins(cls, v):
        """Set CORS origins for public service."""
        if isinstance(v, str):
            origins = [origin.strip() for origin in v.split(",")]
        else:
            origins = v or []
        
        # Add default public frontend URL if not present
        default_public = "http://localhost:3200"
        if default_public not in origins:
            origins.append(default_public)
        
        return origins


# Global settings instance
settings = PublicServiceSettings()
```

### shared/tests/config/test_base.py
```python
"""Tests for base configuration."""
import pytest
from pydantic import ValidationError
import os

from config.base import BaseSettings


def test_base_settings_default_values():
    """Test base settings with default values."""
    settings = BaseSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
    )
    
    assert settings.ENVIRONMENT == "development"
    assert settings.DEBUG is True
    assert settings.LOG_LEVEL == "INFO"
    assert settings.API_V1_STR == "/api/v1"
    assert len(settings.CORS_ORIGINS) >= 2


def test_base_settings_validation():
    """Test base settings validation."""
    # Valid settings
    settings = BaseSettings(
        SECRET_KEY="very_long_secret_key_that_is_secure_123456789",
        ENCRYPTION_KEY="very_long_encryption_key_that_is_secure_123456789",
        ENVIRONMENT="production",
        DEBUG=False,
    )
    assert settings.ENVIRONMENT == "production"
    assert settings.DEBUG is False
    
    # Invalid secret key (too short)
    with pytest.raises(ValidationError) as exc_info:
        BaseSettings(
            SECRET_KEY="short",
            ENCRYPTION_KEY="b" * 32,
        )
    assert "at least 32 characters" in str(exc_info.value)
    
    # Invalid environment
    with pytest.raises(ValidationError):
        BaseSettings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            ENVIRONMENT="invalid",
        )


def test_cors_origins_parsing():
    """Test CORS origins parsing from string."""
    # String input
    settings = BaseSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        CORS_ORIGINS="http://localhost:3000,http://localhost:3100,https://example.com",
    )
    assert len(settings.CORS_ORIGINS) == 3
    assert "http://localhost:3000" in settings.CORS_ORIGINS
    assert "https://example.com" in settings.CORS_ORIGINS
    
    # List input
    settings = BaseSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        CORS_ORIGINS=["http://localhost:3000", "https://example.com"],
    )
    assert len(settings.CORS_ORIGINS) == 2


def test_environment_variable_loading(monkeypatch):
    """Test loading from environment variables."""
    monkeypatch.setenv("SECRET_KEY", "env_secret_key_" + "x" * 20)
    monkeypatch.setenv("ENCRYPTION_KEY", "env_encryption_key_" + "x" * 16)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    
    settings = BaseSettings()
    
    assert settings.SECRET_KEY.startswith("env_secret_key_")
    assert settings.ENCRYPTION_KEY.startswith("env_encryption_key_")
    assert settings.ENVIRONMENT == "test"
    assert settings.DEBUG is False
    assert settings.LOG_LEVEL == "WARNING"
```

### shared/tests/config/test_database.py
```python
"""Tests for database configuration."""
import pytest
from pydantic import ValidationError
from unittest.mock import patch, MagicMock

from config.database import DatabaseConfig


def test_database_config_valid():
    """Test valid database configuration."""
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        REDIS_URL="redis://localhost:6379/1",
    )
    
    assert config.DATABASE_URL.startswith("postgresql://")
    assert config.DATABASE_POOL_SIZE == 5
    assert config.DATABASE_MAX_OVERFLOW == 10
    assert config.REDIS_URL.startswith("redis://")
    assert config.REDIS_KEY_PREFIX == "zapa:"


def test_database_url_validation():
    """Test database URL validation."""
    # Valid PostgreSQL URL
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/zapa",
    )
    assert config.DATABASE_URL.startswith("postgresql+psycopg2://")
    
    # Invalid database URL
    with pytest.raises(ValidationError) as exc_info:
        DatabaseConfig(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            DATABASE_URL="mysql://user:pass@localhost:3306/db",
        )
    assert "PostgreSQL URL" in str(exc_info.value)


def test_redis_url_validation():
    """Test Redis URL validation."""
    # Valid Redis URL
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        REDIS_URL="redis://localhost:6379/0",
    )
    assert config.REDIS_URL == "redis://localhost:6379/0"
    
    # Invalid Redis URL
    with pytest.raises(ValidationError):
        DatabaseConfig(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
            REDIS_URL="http://localhost:6379",
        )


@patch('config.database.create_engine')
def test_get_database_engine(mock_create_engine):
    """Test database engine creation."""
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        DATABASE_POOL_SIZE=10,
        DATABASE_MAX_OVERFLOW=20,
        DATABASE_ECHO=True,
    )
    
    engine = config.get_database_engine()
    
    assert engine == mock_engine
    mock_create_engine.assert_called_once_with(
        "postgresql://user:pass@localhost:5432/zapa",
        pool_size=10,
        max_overflow=20,
        echo=True,
    )


@patch('config.database.sessionmaker')
@patch('config.database.create_engine')
def test_get_session_maker(mock_create_engine, mock_sessionmaker):
    """Test session maker creation."""
    mock_engine = MagicMock()
    mock_session_maker = MagicMock()
    mock_create_engine.return_value = mock_engine
    mock_sessionmaker.return_value = mock_session_maker
    
    config = DatabaseConfig(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
    )
    
    session_maker = config.get_session_maker()
    
    assert session_maker == mock_session_maker
    mock_sessionmaker.assert_called_once_with(
        autocommit=False,
        autoflush=False,
        bind=mock_engine,
    )
```

### shared/tests/config/test_encryption.py
```python
"""Tests for encryption utilities."""
import pytest
import base64

from config.encryption import EncryptionManager


@pytest.fixture
def encryption_manager():
    """Create encryption manager for testing."""
    return EncryptionManager("test_encryption_key_123456789012345")


def test_encryption_roundtrip(encryption_manager):
    """Test encryption and decryption roundtrip."""
    plaintext = "sk-1234567890abcdef"
    
    # Encrypt
    ciphertext = encryption_manager.encrypt(plaintext)
    assert ciphertext != plaintext
    assert len(ciphertext) > len(plaintext)
    
    # Decrypt
    decrypted = encryption_manager.decrypt(ciphertext)
    assert decrypted == plaintext


def test_encrypt_empty_string(encryption_manager):
    """Test encrypting empty string."""
    ciphertext = encryption_manager.encrypt("")
    assert ciphertext == ""
    
    decrypted = encryption_manager.decrypt("")
    assert decrypted == ""


def test_encrypt_unicode(encryption_manager):
    """Test encrypting unicode text."""
    plaintext = "🔐 Secret émojis & ñoñó"
    
    ciphertext = encryption_manager.encrypt(plaintext)
    decrypted = encryption_manager.decrypt(ciphertext)
    
    assert decrypted == plaintext


def test_decrypt_invalid_data(encryption_manager):
    """Test decrypting invalid data."""
    with pytest.raises(ValueError) as exc_info:
        encryption_manager.decrypt("invalid_base64_data")
    
    assert "Failed to decrypt" in str(exc_info.value)
    
    with pytest.raises(ValueError):
        encryption_manager.decrypt("dmFsaWRfYmFzZTY0X2J1dF9ub3RfZW5jcnlwdGVk")  # valid base64 but not encrypted


def test_different_keys_different_results():
    """Test that different keys produce different results."""
    plaintext = "same_plaintext"
    
    manager1 = EncryptionManager("key1_" + "x" * 27)
    manager2 = EncryptionManager("key2_" + "x" * 27)
    
    ciphertext1 = manager1.encrypt(plaintext)
    ciphertext2 = manager2.encrypt(plaintext)
    
    assert ciphertext1 != ciphertext2
    
    # Each manager can only decrypt its own ciphertext
    assert manager1.decrypt(ciphertext1) == plaintext
    assert manager2.decrypt(ciphertext2) == plaintext
    
    with pytest.raises(ValueError):
        manager1.decrypt(ciphertext2)


def test_generate_key():
    """Test key generation."""
    key1 = EncryptionManager.generate_key()
    key2 = EncryptionManager.generate_key()
    
    # Keys should be different
    assert key1 != key2
    
    # Keys should be valid base64
    assert base64.urlsafe_b64decode(key1.encode())
    assert base64.urlsafe_b64decode(key2.encode())
    
    # Keys should be the right length (32 bytes = 44 base64 chars with padding)
    assert len(key1) >= 40
    assert len(key2) >= 40
    
    # Keys should work for encryption
    manager = EncryptionManager(key1)
    plaintext = "test"
    ciphertext = manager.encrypt(plaintext)
    assert manager.decrypt(ciphertext) == plaintext


def test_fernet_caching(encryption_manager):
    """Test that Fernet instance is cached."""
    # Access fernet property twice
    fernet1 = encryption_manager.fernet
    fernet2 = encryption_manager.fernet
    
    # Should be the same instance (cached)
    assert fernet1 is fernet2
```

### services/private/tests/test_config.py
```python
"""Tests for private service configuration."""
import pytest
from pydantic import ValidationError

from app.core.config import PrivateServiceSettings


def test_private_service_settings_defaults():
    """Test private service settings with required values only."""
    settings = PrivateServiceSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        ADMIN_TOKEN_SECRET="c" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
    )
    
    assert settings.SERVICE_NAME == "zapa-private"
    assert settings.VERSION == "0.1.0"
    assert settings.WHATSAPP_BRIDGE_URL == "http://localhost:3000"
    assert settings.WHATSAPP_BRIDGE_TIMEOUT == 30.0
    assert settings.ADMIN_TOKEN_EXPIRE_MINUTES == 60 * 24
    assert settings.RATE_LIMIT_ENABLED is True


def test_webhook_url_property():
    """Test webhook URL property construction."""
    settings = PrivateServiceSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        ADMIN_TOKEN_SECRET="c" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        WEBHOOK_BASE_URL="https://api.example.com",
    )
    
    expected = "https://api.example.com/api/v1/webhooks/whatsapp"
    assert settings.webhook_url == expected
    
    # Test with trailing slash
    settings.WEBHOOK_BASE_URL = "https://api.example.com/"
    expected = "https://api.example.com/api/v1/webhooks/whatsapp"
    assert settings.webhook_url == expected


def test_integration_test_flags():
    """Test integration test flag defaults."""
    settings = PrivateServiceSettings(
        SECRET_KEY="a" * 32,
        ENCRYPTION_KEY="b" * 32,
        ADMIN_TOKEN_SECRET="c" * 32,
        DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
    )
    
    assert settings.INTEGRATION_TEST_WHATSAPP is False
    assert settings.INTEGRATION_TEST_OPENAI is False
    assert settings.INTEGRATION_TEST_ANTHROPIC is False
    assert settings.INTEGRATION_TEST_GOOGLE is False


def test_validation_errors():
    """Test validation errors for private service settings."""
    # Missing required field
    with pytest.raises(ValidationError):
        PrivateServiceSettings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            # Missing ADMIN_TOKEN_SECRET
            DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
        )
    
    # Invalid timeout range
    with pytest.raises(ValidationError):
        PrivateServiceSettings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            ADMIN_TOKEN_SECRET="c" * 32,
            DATABASE_URL="postgresql://user:pass@localhost:5432/zapa",
            WHATSAPP_BRIDGE_TIMEOUT=400.0,  # Too high
        )
```

### Update shared/pyproject.toml
```toml
[project]
name = "zapa-shared"
version = "0.1.0"
description = "Shared models and schemas for Zapa services"
requires-python = ">=3.10"
dependencies = [
    "sqlalchemy==2.0.25",
    "psycopg2-binary==2.9.9",
    "alembic==1.13.1",
    "pydantic==2.5.3",
    "pydantic-settings==2.1.0",
    "cryptography==41.0.8",
    "redis==5.0.1",
]
```

## Commands to Run

```bash
# Test shared configuration
cd shared
uv run pytest tests/config/ -v --cov=config

# Test service configurations
cd services/private
uv run pytest tests/test_config.py -v

cd services/public
uv run pytest tests/test_config.py -v

# Test encryption utilities
cd shared
uv run pytest tests/config/test_encryption.py -v

# Generate a new encryption key (for production)
cd shared
uv run python -c "from config.encryption import EncryptionManager; print(EncryptionManager.generate_key())"
```

## Verification

1. All configuration classes validate input correctly
2. Environment variables are loaded properly
3. Encryption utilities work for API key storage
4. Different environments have appropriate defaults
5. Tests achieve ≥90% coverage
6. CI/CD passes with new configuration tests

## Next Steps

After configuration is complete, proceed to Task 04: Database Migrations and Fixtures.