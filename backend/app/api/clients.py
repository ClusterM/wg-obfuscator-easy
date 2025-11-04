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

"""Client management API endpoints"""

from flask import Blueprint, request, jsonify, current_app
import logging

from ..config.constants import MASKING_TYPES, VERBOSITY_LEVELS
from ..exceptions import ClientNotFoundError, ClientAlreadyExistsError, ConfigValidationError

logger = logging.getLogger(__name__)

bp = Blueprint('clients', __name__)


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
    """Apply configuration changes"""
    from ..services import ServiceManager
    service_manager = ServiceManager(
        app.config_manager,
        app.client_manager,
        app.wg_manager,
        app.obfuscator_manager,
        app.external_ip,
        app.external_port
    )
    service_manager.apply_config_changes()


@bp.route('', methods=['GET'])
@require_auth
def get_clients():
    """Get list of all clients with connection stats"""
    try:
        from ..wireguard.stats import WireGuardStats
        from ..database import get_all_clients
        
        config_manager = current_app.config_manager
        wg_manager = current_app.wg_manager
        # Reload clients from database to get fresh all_time_rx_bytes and all_time_tx_bytes
        clients = get_all_clients()
        
        # Add connection stats for each client
        try:
            stats_collector = WireGuardStats(wg_manager.wg_interface)
            stats = stats_collector.get_stats(clients)
            
            if stats and stats.get("peers"):
                # Create a map of public_key -> peer stats
                peer_stats_map = {}
                for peer in stats["peers"]:
                    peer_stats_map[peer.get("public_key")] = peer
                
                # Add stats to each client and save latest_handshake to DB
                config_manager = current_app.config_manager
                for username, client_data in clients.items():
                    public_key = client_data.get('public_key')
                    peer_stats = peer_stats_map.get(public_key)
                    
                    if peer_stats:
                        client_data['is_connected'] = peer_stats.get('is_connected', False)
                        new_handshake = peer_stats.get('latest_handshake', 0)
                        # Get stored value before updating
                        stored_handshake = client_data.get('latest_handshake', 0)
                        
                        # Only update latest_handshake if new value is greater (newer) than stored
                        # If new_handshake is 0, it means no handshake yet, so keep stored value
                        if new_handshake > stored_handshake:
                            client_data['latest_handshake'] = new_handshake
                            # Save latest_handshake to database if it's newer
                            config_manager.set_client(username, client_data, save=True)
                        else:
                            # Keep stored value, don't overwrite with 0 or older value
                            pass
                    else:
                        client_data['is_connected'] = False
                        # Use stored latest_handshake from DB (already loaded in client_data)
                        # Don't overwrite it - it's already there from database
            else:
                # No stats available (WireGuard not running)
                # Use stored latest_handshake from DB (already loaded in client_data)
                for client_data in clients.values():
                    client_data['is_connected'] = False
                    # latest_handshake already loaded from DB, just ensure it exists (default to 0 only if None)
                    if client_data.get('latest_handshake') is None:
                        client_data['latest_handshake'] = 0
        except Exception as e:
            logger.warning(f"Failed to get connection stats: {e}")
            # If stats collection fails, use stored latest_handshake from DB
            for client_data in clients.values():
                client_data['is_connected'] = False
                # latest_handshake already loaded from DB, just ensure it exists (default to 0 only if None)
                if client_data.get('latest_handshake') is None:
                    client_data['latest_handshake'] = 0
        
        return jsonify(clients)
    except Exception as e:
        logger.error(f"Error getting clients: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/<username>/config/wireguard', methods=['GET'])
@require_auth
def get_client_config_wireguard_endpoint(username):
    """Get WireGuard configuration for specific client"""
    try:
        client_manager = current_app.client_manager
        external_ip = current_app.external_ip
        external_port = current_app.external_port
        
        client_config = client_manager.get_client_wg_config(username, external_ip, external_port)
        response = current_app.response_class(
            response=client_config,
            status=200,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename="{username}-wireguard.conf"',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
        return response
    except ClientNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error getting client WireGuard config: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/<username>/config/obfuscator', methods=['GET'])
@require_auth
def get_client_config_obfuscator_endpoint(username):
    """Get Obfuscator configuration for specific client"""
    try:
        config = current_app.config_manager.main
        if not config.get('obfuscation', False):
            return jsonify({"error": "Obfuscation is disabled"}), 400
        
        client_manager = current_app.client_manager
        external_ip = current_app.external_ip
        external_port = current_app.external_port
        
        client_config = client_manager.get_client_obfuscator_config(username, external_ip, external_port)
        response = current_app.response_class(
            response=client_config,
            status=200,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename="{username}-obfuscator.conf"',
                'Access-Control-Expose-Headers': 'Content-Disposition'
            }
        )
        return response
    except ClientNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error getting client obfuscator config: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/<username>', methods=['GET'])
@require_auth
def get_client(username):
    """Get information about specific client with connection stats"""
    try:
        from ..wireguard.stats import WireGuardStats
        
        config_manager = current_app.config_manager
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        client = config_manager.get_client(username).copy()
        
        # Add connection stats
        try:
            wg_manager = current_app.wg_manager
            clients = config_manager.clients
            stats_collector = WireGuardStats(wg_manager.wg_interface)
            stats = stats_collector.get_stats(clients)
            
            if stats and stats.get("peers"):
                public_key = client.get('public_key')
                stored_handshake = client.get('latest_handshake', 0)
                
                for peer in stats["peers"]:
                    if peer.get("public_key") == public_key:
                        client['is_connected'] = peer.get('is_connected', False)
                        new_handshake = peer.get('latest_handshake', 0)
                        
                        # Only update latest_handshake if new value is greater (newer) than stored
                        # If new_handshake is 0, it means no handshake yet, so keep stored value
                        if new_handshake > stored_handshake:
                            client['latest_handshake'] = new_handshake
                            # Save to DB if newer
                            config_manager.set_client(username, client, save=True)
                        # else: keep stored value, don't overwrite with 0 or older value
                        break
                else:
                    client['is_connected'] = False
                    # Use stored latest_handshake (already loaded from DB via get_client)
            else:
                client['is_connected'] = False
                # Use stored latest_handshake (already loaded from DB via get_client)
        except Exception as e:
            logger.warning(f"Failed to get connection stats for client: {e}")
            client['is_connected'] = False
            # Use stored latest_handshake (already loaded from DB via get_client)
        
        return jsonify(client)
    except Exception as e:
        logger.error(f"Error getting client: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('', methods=['POST'])
@require_auth
def create_client():
    """Create new client"""
    try:
        data = request.get_json()
        if not data or "username" not in data:
            return jsonify({"error": "username is required"}), 400
        
        username = data["username"]
        client_manager = current_app.client_manager
        
        new_client = client_manager.add_client(username, data.get("obfuscation", True))
        
        # Set enabled status if provided
        if "enabled" in data:
            enabled = data["enabled"]
            if isinstance(enabled, bool):
                new_client["enabled"] = enabled
                config_manager = current_app.config_manager
                config_manager.set_client(username, new_client, save=True)
        
        apply_config_changes(current_app)
        
        return jsonify(new_client), 201
    except ClientAlreadyExistsError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating client: {e}")
        return jsonify({"error": str(e)}), 400


@bp.route('/<username>', methods=['PATCH'])
@require_auth
def update_client(username):
    """Update client configuration"""
    try:
        config_manager = current_app.config_manager
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        client = config_manager.get_client(username)
        updated = False
        
        # Preserve latest_handshake from DB - don't lose it when updating other fields
        stored_latest_handshake = client.get('latest_handshake', 0)
        
        # Update allowed_ips
        if "allowed_ips" in data:
            allowed_ips = data["allowed_ips"]
            if not isinstance(allowed_ips, list):
                return jsonify({"error": "allowed_ips must be a list"}), 400
            # Validate that all items are strings and valid CIDR format
            for ip in allowed_ips:
                if not isinstance(ip, str):
                    return jsonify({"error": "allowed_ips must be a list of strings"}), 400
                ip = ip.strip()
                if not ip:
                    return jsonify({"error": "allowed_ips cannot contain empty strings"}), 400
                # Validate CIDR format using strict mode (ensures network address matches, no host bits set)
                # This also ensures that /0 can only be used with 0.0.0.0
                try:
                    import ipaddress
                    ipaddress.ip_network(ip, strict=True)
                except ValueError as e:
                    return jsonify({"error": f"Invalid CIDR format in allowed_ips: {ip}. Expected format: X.Y.Z.W/MASK (e.g., 0.0.0.0/0). Network address must match the prefix length."}), 400
            client["allowed_ips"] = allowed_ips
            updated = True
        
        # Update obfuscator_port
        if "obfuscator_port" in data:
            obfuscator_port = data["obfuscator_port"]
            if obfuscator_port is None:
                # Delete port (use default)
                if "obfuscator_port" in client:
                    del client["obfuscator_port"]
                    updated = True
            else:
                if not isinstance(obfuscator_port, int) or obfuscator_port < 1 or obfuscator_port > 65535:
                    return jsonify({"error": "obfuscator_port must be an integer between 1 and 65535 or null"}), 400
                client["obfuscator_port"] = obfuscator_port
                updated = True
        
        # Update or delete masking_type_override
        if "masking_type_override" in data:
            config = config_manager.main
            if config.get("masking_forced", False):
                return jsonify({"error": "masking_type_override cannot be set when masking_forced is true"}), 400
            
            masking_type_override = data["masking_type_override"]
            if masking_type_override is None:
                # Delete override
                if "masking_type_override" in client:
                    del client["masking_type_override"]
                    updated = True
            else:
                # Set override
                if masking_type_override not in MASKING_TYPES:
                    return jsonify({"error": f"masking_type_override must be one of: {', '.join(MASKING_TYPES)} or null"}), 400
                client["masking_type_override"] = masking_type_override
                updated = True
        
        # Update verbosity_level
        if "verbosity_level" in data:
            verbosity_level = data["verbosity_level"]
            if verbosity_level not in VERBOSITY_LEVELS:
                return jsonify({"error": f"verbosity_level must be one of: {', '.join(VERBOSITY_LEVELS)}"}), 400
            client["verbosity_level"] = verbosity_level
            updated = True
        
        # Update enabled status
        if "enabled" in data:
            enabled = data["enabled"]
            if not isinstance(enabled, bool):
                return jsonify({"error": "enabled must be a boolean"}), 400
            client["enabled"] = enabled
            updated = True
        
        if updated:
            # Ensure latest_handshake is preserved
            if 'latest_handshake' not in client:
                client['latest_handshake'] = stored_latest_handshake
            config_manager.set_client(username, client, save=True)
            apply_config_changes(current_app)
        
        return jsonify(client), 200
    except Exception as e:
        logger.error(f"Error updating client: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/<username>/regenerate-keys', methods=['POST'])
@require_auth
def regenerate_client_keys(username):
    """Regenerate client key pair"""
    try:
        client_manager = current_app.client_manager
        
        private, public = client_manager.regenerate_client_keys(username)
        apply_config_changes(current_app)
        
        return jsonify({
            "private_key": private,
            "public_key": public
        })
    except ClientNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error regenerating client keys: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/<username>', methods=['DELETE'])
@require_auth
def remove_client(username):
    """Delete client"""
    try:
        client_manager = current_app.client_manager
        client_manager.delete_client(username)
        apply_config_changes(current_app)
        return jsonify({"message": f"Client {username} deleted successfully"}), 200
    except ClientNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error deleting client: {e}")
        return jsonify({"error": str(e)}), 500

