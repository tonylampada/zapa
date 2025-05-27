"""Encryption utilities for sensitive data."""
import base64
import secrets

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    """Handles encryption/decryption of sensitive data."""

    def __init__(self, encryption_key: str):
        """
        Initialize encryption manager.

        Args:
            encryption_key: Base encryption key (will be derived)
        """
        self.encryption_key = encryption_key
        self._fernet: Fernet | None = None

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

    def encrypt(self, plaintext: str) -> str:
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

    def decrypt(self, ciphertext: str) -> str:
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
            raise ValueError(f"Failed to decrypt data: {e}") from e

    @classmethod
    def generate_key(cls) -> str:
        """Generate a secure random key."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


# Global encryption manager instance
_encryption_manager = None


def get_encryption_manager() -> EncryptionManager:
    """Get the global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        # In production, this should come from environment config
        import os
        encryption_key = os.getenv("ENCRYPTION_KEY", "test-encryption-key-32-chars-long")
        _encryption_manager = EncryptionManager(encryption_key)
    return _encryption_manager


def encrypt_api_key(api_key: str) -> bytes:
    """Encrypt an API key and return bytes for database storage."""
    manager = get_encryption_manager()
    encrypted = manager.encrypt(api_key)
    return encrypted.encode()


def decrypt_api_key(encrypted: bytes) -> str:
    """Decrypt an API key from database bytes."""
    manager = get_encryption_manager()
    return manager.decrypt(encrypted.decode())
