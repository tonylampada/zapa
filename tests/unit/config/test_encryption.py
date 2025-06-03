"""Tests for encryption utilities."""

import base64

import pytest

from app.config.encryption import EncryptionManager


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
        encryption_manager.decrypt(
            "dmFsaWRfYmFzZTY0X2J1dF9ub3RfZW5jcnlwdGVk"
        )  # valid base64 but not encrypted


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
