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

"""Configuration API endpoints"""

from flask import Blueprint, request, jsonify, current_app
import logging

from ..config.constants import (
    DEFAULT_VERBOSITY_LEVEL, DEFAULT_MASKING_TYPE,
    VERBOSITY_LEVELS, MASKING_TYPES
)
from ..exceptions import ConfigValidationError, ServiceError

logger = logging.getLogger(__name__)

bp = Blueprint('config', __name__)


def require_auth(f):
    """Decorator to require authentication"""
    from functools import wraps
    from ..config.constants import AUTH_ENABLED
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        
        token = auth_header.split(' ')[1]
        token_manager = current_app.token_manager
        if not token_manager or not token_manager.is_valid(token):
            return jsonify({"error": "Invalid or expired token"}), 401
        
        return f(*args, **kwargs)
    return decorated_function


def apply_config_changes(app):
    """Apply configuration changes: generate config and restart WireGuard"""
    from ..services import ServiceManager
    from ..exceptions import ServiceError
    try:
        service_manager = ServiceManager(
            app.config_manager,
            app.client_manager,
            app.wg_manager,
            app.obfuscator_manager,
            app.external_ip,
            app.external_port
        )
        service_manager.apply_config_changes()
    except Exception as e:
        logger.error(f"Failed to apply config changes: {e}")
        raise ServiceError(f"Failed to apply configuration changes: {str(e)}")


@bp.route('', methods=['GET'])
@require_auth
def get_config():
    """Get current server settings (read-only)"""
    try:
        config_manager = current_app.config_manager
        external_ip = current_app.external_ip
        external_port = current_app.external_port
        
        config = config_manager.main
        subnet = config.get("subnet")
        
        return jsonify({
            "external_ip": external_ip,
            "external_port": external_port,
            "server_public_key": config.get("server_public_key"),
            "subnet": f"{subnet}.0/24" if subnet else None,
            "server_ip": f"{config['subnet']}.{config['own_ip']}",
            "obfuscation": config.get("obfuscation", False),
            "obfuscator_verbosity": config.get("verbosity_level", DEFAULT_VERBOSITY_LEVEL),
            "masking_type": config.get("masking_type", DEFAULT_MASKING_TYPE),
            "masking_forced": config.get("masking_forced", False)
        })
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('', methods=['PATCH'])
@require_auth
def update_config():
    """Update server configuration parameters"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        config_manager = current_app.config_manager
        updated = False
        
        # Validate and update subnet
        if "subnet" in data:
            subnet_value = data["subnet"]
            if not isinstance(subnet_value, str):
                return jsonify({"error": "subnet must be a string"}), 400
            
            # Extract base subnet (first 3 octets)
            if subnet_value.endswith(".0/24"):
                base_subnet = subnet_value[:-5]  # Remove ".0/24"
                # Validate it's 3 octets
                parts = base_subnet.split(".")
                if len(parts) != 3:
                    return jsonify({"error": "subnet must be in format X.Y.Z.0/24"}), 400
                try:
                    for part in parts:
                        num = int(part)
                        if num < 0 or num > 255:
                            raise ValueError
                except ValueError:
                    return jsonify({"error": "subnet octets must be between 0 and 255"}), 400
                
                config_manager.set("subnet", base_subnet, save=False)
                updated = True
            else:
                return jsonify({"error": "subnet must be in format X.Y.Z.0/24"}), 400
        
        # Validate and update obfuscation
        if "obfuscation" in data:
            obfuscation_value = data["obfuscation"]
            if not isinstance(obfuscation_value, bool):
                return jsonify({"error": "obfuscation must be a boolean"}), 400
            config_manager.set("obfuscation", obfuscation_value, save=False)
            updated = True
        
        # Validate and update verbosity level
        if "verbosity_level" in data or "obfuscator_verbosity" in data:
            verbosity = data.get("verbosity_level") or data.get("obfuscator_verbosity")
            if verbosity not in VERBOSITY_LEVELS:
                return jsonify({"error": f"verbosity_level must be one of: {', '.join(VERBOSITY_LEVELS)}"}), 400
            config_manager.set("verbosity_level", verbosity, save=False)
            updated = True
        
        # Validate and update masking_type
        if "masking_type" in data:
            masking_type = data["masking_type"]
            if masking_type not in MASKING_TYPES:
                return jsonify({"error": f"masking_type must be one of: {', '.join(MASKING_TYPES)}"}), 400
            config_manager.set("masking_type", masking_type, save=False)
            updated = True
        
        # Validate and update masking_forced
        if "masking_forced" in data:
            masking_forced = data["masking_forced"]
            if not isinstance(masking_forced, bool):
                return jsonify({"error": "masking_forced must be a boolean"}), 400
            config_manager.set("masking_forced", masking_forced, save=False)
            updated = True
        
        if updated:
            config_manager.save_config()
            apply_config_changes(current_app)
        
        # Return updated config (same format as GET)
        config = config_manager.main
        subnet = config.get("subnet")
        external_ip = current_app.external_ip
        external_port = current_app.external_port
        
        return jsonify({
            "external_ip": external_ip,
            "external_port": external_port,
            "server_public_key": config.get("server_public_key"),
            "subnet": f"{subnet}.0/24" if subnet else None,
            "server_ip": f"{config['subnet']}.{config['own_ip']}",
            "obfuscation": config.get("obfuscation", False),
            "obfuscator_verbosity": config.get("verbosity_level", DEFAULT_VERBOSITY_LEVEL),
            "masking_type": config.get("masking_type", DEFAULT_MASKING_TYPE),
            "masking_forced": config.get("masking_forced", False)
        })
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/regenerate-keys', methods=['POST'])
@require_auth
def regenerate_server_keys():
    """Generate new server key pair"""
    try:
        config_manager = current_app.config_manager
        client_manager = current_app.client_manager
        
        server_private_key, server_public_key = client_manager.generate_key_pair()
        config_manager.set("server_private_key", server_private_key, save=False)
        config_manager.set("server_public_key", server_public_key, save=True)
        
        apply_config_changes(current_app)
        
        return jsonify({
            "server_public_key": server_public_key
        })
    except Exception as e:
        logger.error(f"Error regenerating server keys: {e}")
        return jsonify({"error": str(e)}), 500

