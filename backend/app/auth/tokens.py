"""
Copyright (C) 2025 Alexey Cluster <cluster@cluster.wtf>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

"""Token management for authentication using SQLite"""

import secrets
import logging
from datetime import datetime
from functools import wraps

from flask import request, jsonify

from ..config.constants import TOKEN_EXPIRES_IN, AUTH_ENABLED
from ..database import (
    create_token, get_token, delete_token, delete_all_tokens,
    cleanup_expired_tokens
)

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages authentication tokens with SQLite persistence"""
    
    def __init__(self, expires_in: int = TOKEN_EXPIRES_IN):
        self.expires_in = expires_in
        # Cleanup expired tokens on initialization
        deleted = cleanup_expired_tokens()
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired tokens")
    
    def generate_token(self) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)
    
    def create_token(self) -> tuple[str, datetime]:
        """
        Create a new token
        
        Returns:
            Tuple of (token, created_at datetime)
        """
        token = self.generate_token()
        created_at = datetime.now()
        create_token(token, created_at, self.expires_in)
        logger.info(f"Created new token (expires in {self.expires_in}s)")
        return token, created_at
    
    def is_valid(self, token: str) -> bool:
        """
        Check if token is valid and not expired
        
        Args:
            token: Token to validate
            
        Returns:
            True if token is valid, False otherwise
        """
        token_data = get_token(token)
        
        if token_data is None:
            return False
        
        created_at = token_data["created_at"]
        expires_in = token_data["expires_in"]
        
        # Check if token has expired
        elapsed = (datetime.now() - created_at).total_seconds()
        if elapsed > expires_in:
            delete_token(token)
            logger.debug(f"Token expired (elapsed: {elapsed}s, expires_in: {expires_in}s)")
            return False
        
        return True
    
    def revoke_token(self, token: str) -> None:
        """Revoke a specific token"""
        delete_token(token)
        logger.info("Token revoked")
    
    def revoke_all_tokens(self) -> None:
        """Revoke all tokens"""
        delete_all_tokens()
        logger.info("All tokens revoked")


def require_auth(f):
    """
    Decorator to require authentication for Flask endpoints
    
    Checks for Bearer token in Authorization header and validates it.
    If AUTH_ENABLED is False, authentication is bypassed.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        
        token = auth_header.split(' ')[1]
        # Create temporary token manager to check token
        # In practice, you'd pass the token manager instance
        token_manager = TokenManager()
        if not token_manager.is_valid(token):
            return jsonify({"error": "Invalid or expired token"}), 401
        
        return f(*args, **kwargs)
    return decorated_function

