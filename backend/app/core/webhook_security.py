"""Webhook security and validation utilities."""

import hmac
import hashlib
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class WebhookValidator:
    """Validator for webhook request signatures."""
    
    def __init__(self, webhook_secret: Optional[str] = None):
        """
        Initialize webhook validator.
        
        Args:
            webhook_secret: Secret key for HMAC signature validation.
                           If None, validation is skipped.
        """
        self.webhook_secret = webhook_secret
    
    def validate_signature(
        self, 
        payload: bytes, 
        signature: Optional[str]
    ) -> bool:
        """
        Validate webhook signature if secret is configured.
        
        Args:
            payload: Raw request body bytes
            signature: Signature header value
            
        Returns:
            True if signature is valid or validation is disabled
            False if signature is invalid
        """
        if not self.webhook_secret:
            # No validation if secret not configured
            logger.debug("Webhook signature validation disabled (no secret configured)")
            return True
            
        if not signature:
            logger.warning("Missing webhook signature header")
            return False
            
        # Calculate expected signature
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(expected, signature)
        
        if not is_valid:
            logger.warning("Invalid webhook signature")
        
        return is_valid