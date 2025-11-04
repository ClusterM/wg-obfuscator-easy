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

"""Authentication API endpoints"""

from flask import Blueprint, request, jsonify, current_app
import logging

from ..auth.tokens import TokenManager
from ..auth.password import verify_password
from ..config.constants import AUTH_ENABLED, DEFAULT_ADMIN_USERNAME

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__)


def get_token_manager():
    """Get token manager from app context"""
    from flask import g
    return g.token_manager if hasattr(g, 'token_manager') else None


def require_auth(f):
    """Decorator to require authentication for Flask endpoints"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        
        token = auth_header.split(' ')[1]
        token_manager = current_app.token_manager
        if not token_manager or not token_manager.is_valid(token):
            return jsonify({"error": "Invalid or expired token"}), 401
        
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/login', methods=['POST'])
def login():
    """Login and get authentication token"""
    if not AUTH_ENABLED:
        return jsonify({"error": "Authentication is disabled"}), 400
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
        
        config_manager = current_app.config_manager
        token_manager = current_app.token_manager
        
        # Verify credentials
        config = config_manager.main
        if username != config.get("admin_username", DEFAULT_ADMIN_USERNAME):
            return jsonify({"error": "Invalid credentials"}), 401
        
        stored_hash = config.get("admin_password_hash")
        if not stored_hash or not verify_password(password, stored_hash):
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Generate token with OAuth 2.0 format
        access_token, created_at = token_manager.create_token()
        expires_in = token_manager.expires_in
        
        return jsonify({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": expires_in
        })
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/credentials', methods=['GET'])
@require_auth
def get_credentials():
    """Get admin username (without password)"""
    try:
        config_manager = current_app.config_manager
        config = config_manager.main
        username = config.get("admin_username", DEFAULT_ADMIN_USERNAME)
        return jsonify({"username": username})
    except Exception as e:
        logger.error(f"Get credentials error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/change-password', methods=['POST'])
@require_auth
def change_password():
    """Change admin password"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        old_password = data.get("old_password")
        new_password = data.get("new_password")
        
        if not old_password or not new_password:
            return jsonify({"error": "old_password and new_password are required"}), 400
        
        config_manager = current_app.config_manager
        token_manager = current_app.token_manager
        from ..auth.password import hash_password
        
        config = config_manager.main
        # Verify old password
        stored_hash = config.get("admin_password_hash")
        if not stored_hash or not verify_password(old_password, stored_hash):
            return jsonify({"error": "Invalid old password"}), 401
        
        # Update password
        config_manager.set("admin_password_hash", hash_password(new_password), save=True)
        
        # Invalidate all existing tokens
        token_manager.revoke_all_tokens()
        
        return jsonify({"message": "Password changed successfully"})
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/change-credentials', methods=['POST'])
@require_auth
def change_credentials():
    """Change admin username and/or password"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        config_manager = current_app.config_manager
        token_manager = current_app.token_manager
        from ..auth.password import hash_password
        
        config = config_manager.main
        
        # If changing password, verify old password
        if "new_password" in data:
            old_password = data.get("old_password")
            new_password = data.get("new_password")
            
            if not old_password or not new_password:
                return jsonify({"error": "old_password and new_password are required"}), 400
            
            stored_hash = config.get("admin_password_hash")
            if not stored_hash or not verify_password(old_password, stored_hash):
                return jsonify({"error": "Invalid old password"}), 401
            
            # Update password
            config_manager.set("admin_password_hash", hash_password(new_password), save=False)
        
        # If changing username
        if "new_username" in data:
            new_username = data.get("new_username")
            if not new_username or not new_username.strip():
                return jsonify({"error": "new_username is required and cannot be empty"}), 400
            config_manager.set("admin_username", new_username.strip(), save=False)
        
        # Save all changes at once
        config_manager.save_config()
        
        # Invalidate all existing tokens (force re-login)
        token_manager.revoke_all_tokens()
        
        return jsonify({"message": "Credentials changed successfully"})
    except Exception as e:
        logger.error(f"Change credentials error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    return jsonify({
        "enabled": AUTH_ENABLED
    })

