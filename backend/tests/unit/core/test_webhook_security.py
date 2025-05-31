"""Unit tests for webhook security."""

import pytest
import hmac
import hashlib

from app.core.webhook_security import WebhookValidator


class TestWebhookValidator:
    """Test webhook signature validation."""
    
    def test_validation_disabled_without_secret(self):
        """Test validation is disabled when no secret is configured."""
        validator = WebhookValidator(webhook_secret=None)
        
        # Should always return True when no secret
        assert validator.validate_signature(b"any payload", None) is True
        assert validator.validate_signature(b"any payload", "any signature") is True
    
    def test_validation_with_valid_signature(self):
        """Test validation passes with correct signature."""
        secret = "test_webhook_secret"
        payload = b'{"event": "test"}'
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        validator = WebhookValidator(webhook_secret=secret)
        assert validator.validate_signature(payload, expected_signature) is True
    
    def test_validation_with_invalid_signature(self):
        """Test validation fails with incorrect signature."""
        secret = "test_webhook_secret"
        payload = b'{"event": "test"}'
        
        validator = WebhookValidator(webhook_secret=secret)
        assert validator.validate_signature(payload, "invalid_signature") is False
    
    def test_validation_with_missing_signature(self):
        """Test validation fails when signature is missing but required."""
        validator = WebhookValidator(webhook_secret="secret")
        
        assert validator.validate_signature(b"payload", None) is False
    
    def test_validation_with_tampered_payload(self):
        """Test validation fails when payload is tampered."""
        secret = "test_webhook_secret"
        original_payload = b'{"event": "test"}'
        tampered_payload = b'{"event": "tampered"}'
        
        # Calculate signature for original payload
        signature = hmac.new(
            secret.encode(),
            original_payload,
            hashlib.sha256
        ).hexdigest()
        
        validator = WebhookValidator(webhook_secret=secret)
        # Try to validate tampered payload with original signature
        assert validator.validate_signature(tampered_payload, signature) is False
    
    def test_constant_time_comparison(self):
        """Test that validation uses constant-time comparison."""
        secret = "test_webhook_secret"
        payload = b'{"event": "test"}'
        
        # This is more of a smoke test - we can't easily test timing
        # but we can verify the function works correctly
        validator = WebhookValidator(webhook_secret=secret)
        
        correct_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        # Create a signature that differs only in the last character
        almost_correct = correct_sig[:-1] + ('0' if correct_sig[-1] != '0' else '1')
        
        assert validator.validate_signature(payload, correct_sig) is True
        assert validator.validate_signature(payload, almost_correct) is False