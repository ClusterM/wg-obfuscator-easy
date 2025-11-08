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

"""Statistics and logs API endpoints"""

from flask import Blueprint, request, jsonify, current_app, Response
import logging

from ..config.constants import APP_VERSION

logger = logging.getLogger(__name__)

bp = Blueprint('stats', __name__)


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


def require_auth_or_metrics(f):
    """Decorator to require authentication (JWT token or metrics token)"""
    from functools import wraps
    from ..config.constants import AUTH_ENABLED
    from ..database import get_metrics_token
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid authorization header"}), 401
        
        # Extract token more safely - handle cases where token might have spaces or newlines
        try:
            # Remove 'Bearer ' prefix and strip whitespace
            token = auth_header[7:].strip()
            # Remove any newlines or carriage returns that might have been added
            token = token.replace('\n', '').replace('\r', '').replace(' ', '')
            
            # Log token length for debugging (but not the token itself for security)
            logger.debug(f"Received token, length: {len(token)}")
        except (IndexError, AttributeError) as e:
            logger.error(f"Error parsing authorization header: {e}")
            return jsonify({"error": "Invalid authorization header format"}), 401
        
        # Check metrics token first
        metrics_token = get_metrics_token()
        if metrics_token:
            # Normalize both tokens for comparison
            metrics_token_clean = metrics_token.strip().replace('\n', '').replace('\r', '').replace(' ', '')
            token_clean = token.strip().replace('\n', '').replace('\r', '').replace(' ', '')
            if token_clean == metrics_token_clean:
                logger.debug("Metrics token authentication successful")
                return f(*args, **kwargs)
        
        # Check JWT token
        token_manager = current_app.token_manager
        if token_manager and token_manager.is_valid(token):
            logger.debug("JWT token authentication successful")
            return f(*args, **kwargs)
        
        logger.warning(f"Authentication failed for token (length: {len(token)})")
        return jsonify({"error": "Invalid or expired token"}), 401
    return decorated_function


@bp.route('/status', methods=['GET'])
@require_auth
def get_status():
    """Get server status including WireGuard and obfuscator status"""
    try:
        from ..wireguard.stats import WireGuardStats
        
        config_manager = current_app.config_manager
        wg_manager = current_app.wg_manager
        obfuscator_manager = current_app.obfuscator_manager
        external_ip = current_app.external_ip
        external_port = current_app.external_port
        
        config = config_manager.main
        wg_status = wg_manager.status()
        obfuscator_status = obfuscator_manager.status(config.get('obfuscation', False))
        
        # Count connected clients
        connected_clients_count = 0
        if wg_status["running"]:
            try:
                stats_collector = WireGuardStats(wg_manager.wg_interface)
                stats = stats_collector.get_stats(config_manager.clients)
                if stats and stats.get("peers"):
                    connected_clients_count = sum(
                        1 for peer in stats["peers"] 
                        if peer.get("is_connected", False)
                    )
            except Exception as e:
                logger.warning(f"Failed to get connected clients count: {e}")
        
        return jsonify({
            "external_ip": external_ip,
            "external_port": external_port,
            "subnet": f"{config.get('subnet')}.0/24",
            "server_ip": f"{config.get('subnet')}.{config.get('own_ip')}",
            "server_public_key": config.get("server_public_key"),
            "clients_count": len(config_manager.clients),
            "connected_clients_count": connected_clients_count,
            "version": APP_VERSION,
            "wireguard": {
                "running": wg_status["running"],
                "error": wg_status.get("error")
            },
            "obfuscator": {
                "enabled": obfuscator_status.get("enabled", False),
                "running": obfuscator_status.get("running", False),
                "error": obfuscator_status.get("error"),
                "exit_code": obfuscator_status.get("exit_code"),
                "version": obfuscator_status.get("version")
            }
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/stats', methods=['GET'])
@require_auth
def get_stats():
    """Get WireGuard statistics for all peers"""
    try:
        from ..wireguard.stats import WireGuardStats
        
        config_manager = current_app.config_manager
        wg_manager = current_app.wg_manager
        
        stats_collector = WireGuardStats(wg_manager.wg_interface)
        stats = stats_collector.get_stats(config_manager.clients)
        
        if stats is None:
            return jsonify({"error": "WireGuard interface not found or not running"}), 503
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/stats/<username>', methods=['GET'])
@require_auth
def get_client_stats(username):
    """Get WireGuard statistics for specific client"""
    try:
        from ..wireguard.stats import WireGuardStats
        
        config_manager = current_app.config_manager
        wg_manager = current_app.wg_manager
        
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        client = config_manager.get_client(username)
        public_key = client.get('public_key')
        
        stats_collector = WireGuardStats(wg_manager.wg_interface)
        stats = stats_collector.get_stats(config_manager.clients)
        
        if stats is None:
            return jsonify({"error": "WireGuard interface not found or not running"}), 503
        
        # Find peer by public key
        for peer in stats.get("peers", []):
            if peer.get("public_key") == public_key:
                return jsonify(peer)
        
        # Peer not found in active connections
        return jsonify({
            "public_key": public_key,
            "client_name": username,
            "is_connected": False,
            "message": "Client not currently connected"
        })
    except Exception as e:
        logger.error(f"Error getting client stats: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/logs/obfuscator', methods=['GET'])
@require_auth
def get_obfuscator_logs():
    """Get last N lines from in-memory obfuscator logs"""
    try:
        # Get number of lines from query parameter, default 100
        n_lines = request.args.get('lines', default=100, type=int)
        if n_lines < 1 or n_lines > 10000:
            return jsonify({"error": "lines parameter must be between 1 and 10000"}), 400
        
        obfuscator_manager = current_app.obfuscator_manager
        log_storage = obfuscator_manager.log_storage
        
        total_lines = len(log_storage)
        if total_lines == 0:
            return jsonify({
                "lines": [],
                "total_lines": 0,
                "requested_lines": n_lines,
                "returned_lines": 0,
                "message": "No logs available yet"
            })
        
        last_lines = log_storage.get_logs(n_lines)
        
        return jsonify({
            "lines": last_lines,
            "total_lines": total_lines,
            "requested_lines": n_lines,
            "returned_lines": len(last_lines)
        })
    except Exception as e:
        logger.error(f"Error getting obfuscator logs: {e}")
        return jsonify({"error": str(e)}), 500


def _collect_wireguard_peer_map(config_manager, wg_manager):
    """Build a map of username -> peer stats from WireGuard"""
    peer_map = {}
    try:
        from ..wireguard.stats import WireGuardStats

        stats_collector = WireGuardStats(wg_manager.wg_interface)
        stats = stats_collector.get_stats(config_manager.clients)
        if stats and stats.get("peers"):
            for peer in stats["peers"]:
                username = peer.get("client_name")
                if username:
                    peer_map[username] = peer
    except Exception as e:
        logger.warning(f"Failed to collect WireGuard peer stats: {e}")
    return peer_map


def _sanitize_metric_label(value: str) -> str:
    """Sanitize metric label to contain only safe characters"""
    import re

    if not value:
        return ""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', value)


def _format_plain_metrics(lines):
    """Helper to return text/plain metrics"""
    body = "\n".join(lines)
    if not body.endswith("\n"):
        body += "\n"
    return Response(body, mimetype='text/plain')


def _get_system_metrics_lines(config_manager, wg_manager, obfuscator_manager, peer_map):
    """Generate system-level Prometheus metrics lines"""
    wg_status = wg_manager.status()
    obfuscator_status = obfuscator_manager.status(
        config_manager.main.get('obfuscation', False)
    )
    
    connected_clients = sum(
        1 for peer in peer_map.values() if peer.get('is_connected', False)
    )
    
    return [
        f"service_running{{service=\"wireguard\"}} {1 if wg_status.get('running') else 0}",
        f"service_running{{service=\"obfuscator\"}} {1 if obfuscator_status.get('running') else 0}",
        f"wg_clients_connected {len(config_manager.clients)}",
        f"wg_clients_configured {connected_clients}",
    ]


def _get_client_metrics_lines(username, peer_map):
    """Generate Prometheus metrics lines for a single client"""
    label = _sanitize_metric_label(username)
    peer_stats = peer_map.get(username, {})
    connected = 1 if peer_stats.get('is_connected') else 0
    rx_bytes = int(peer_stats.get('transfer_rx_bytes', 0) or 0)
    tx_bytes = int(peer_stats.get('transfer_tx_bytes', 0) or 0)
    
    return [
        f"wg_client_connected{{client_id=\"{label}\"}} {connected}",
        f"wg_client_tx_bytes_total{{client_id=\"{label}\"}} {tx_bytes}",
        f"wg_client_rx_bytes_total{{client_id=\"{label}\"}} {rx_bytes}",
    ]


def _get_all_clients_metrics_lines(config_manager, peer_map):
    """Generate Prometheus metrics lines for all clients"""
    lines = []
    for username in sorted(config_manager.clients.keys()):
        client_data = config_manager.get_client(username)
        if not client_data:
            continue
        lines.extend(_get_client_metrics_lines(username, peer_map))
    return lines


@bp.route('/metrics/system', methods=['GET'])
@require_auth_or_metrics
def get_metrics_system():
    """Return system level Prometheus metrics"""
    try:
        config_manager = current_app.config_manager
        wg_manager = current_app.wg_manager
        obfuscator_manager = current_app.obfuscator_manager
        
        peer_map = _collect_wireguard_peer_map(config_manager, wg_manager)
        lines = _get_system_metrics_lines(config_manager, wg_manager, obfuscator_manager, peer_map)
        
        return _format_plain_metrics(lines)
    except Exception as e:
        logger.error(f"Error generating system metrics: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/metrics/clients/<username>', methods=['GET'])
@require_auth_or_metrics
def get_metrics_client(username):
    """Return Prometheus metrics for a single client"""
    try:
        config_manager = current_app.config_manager
        client_data = config_manager.get_client(username)
        if not client_data:
            return jsonify({"error": "Client not found"}), 404

        wg_manager = current_app.wg_manager
        peer_map = _collect_wireguard_peer_map(config_manager, wg_manager)
        lines = _get_client_metrics_lines(username, peer_map)

        return _format_plain_metrics(lines)
    except Exception as e:
        logger.error(f"Error generating metrics for client {username}: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/metrics/clients', methods=['GET'])
@require_auth_or_metrics
def get_metrics_clients():
    """Return Prometheus metrics for all clients"""
    try:
        config_manager = current_app.config_manager
        wg_manager = current_app.wg_manager
        peer_map = _collect_wireguard_peer_map(config_manager, wg_manager)
        lines = _get_all_clients_metrics_lines(config_manager, peer_map)

        return _format_plain_metrics(lines)
    except Exception as e:
        logger.error("Error generating metrics for all clients: %s", e)
        return jsonify({"error": str(e)}), 500


@bp.route('/metrics/all', methods=['GET'])
@require_auth_or_metrics
def get_metrics_all():
    """Return all Prometheus metrics (system + all clients combined)"""
    try:
        config_manager = current_app.config_manager
        wg_manager = current_app.wg_manager
        obfuscator_manager = current_app.obfuscator_manager

        peer_map = _collect_wireguard_peer_map(config_manager, wg_manager)
        lines = _get_system_metrics_lines(config_manager, wg_manager, obfuscator_manager, peer_map)
        lines.extend(_get_all_clients_metrics_lines(config_manager, peer_map))

        return _format_plain_metrics(lines)
    except Exception as e:
        logger.error(f"Error generating all metrics: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/metrics/token', methods=['GET'])
@require_auth
def get_metrics_token_endpoint():
    """Get current metrics token"""
    try:
        from ..database import get_metrics_token

        token = get_metrics_token()
        return jsonify({"token": token})
    except Exception as e:
        logger.error(f"Error getting metrics token: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/metrics/token', methods=['POST'])
@require_auth
def generate_metrics_token_endpoint():
    """Generate a new metrics token (replaces existing token)"""
    try:
        import secrets
        from ..database import set_metrics_token

        token = secrets.token_hex(32)
        set_metrics_token(token)
        logger.info("Generated new metrics token (replaced previous value)")
        return jsonify({"token": token})
    except Exception as e:
        logger.error(f"Error generating metrics token: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/metrics/token', methods=['DELETE'])
@require_auth
def delete_metrics_token_endpoint():
    """Delete the metrics token"""
    try:
        from ..database import delete_metrics_token

        delete_metrics_token()
        logger.info("Deleted metrics token")
        return jsonify({"message": "Metrics token deleted successfully"})
    except Exception as e:
        logger.error(f"Error deleting metrics token: {e}")
        return jsonify({"error": str(e)}), 500
