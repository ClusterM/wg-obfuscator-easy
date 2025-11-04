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

from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
import logging
import time
import json

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


@bp.route('/clients/<username>/traffic-stats', methods=['GET'])
@require_auth
def get_client_traffic_stats(username):
    """Get historical traffic statistics for a client"""
    try:
        collector = current_app.traffic_stats_collector
        if not collector:
            return jsonify({"error": "Traffic statistics collector not available"}), 503
        
        config_manager = current_app.config_manager
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        # Get time range from query parameters
        start_time = request.args.get('start_time', type=int)
        end_time = request.args.get('end_time', type=int)
        aggregation_interval = request.args.get('aggregation_interval', type=int)  # in seconds
        
        # Default to last hour if not specified
        if end_time is None:
            end_time = int(time.time())
        if start_time is None:
            start_time = end_time - 3600  # Last hour
        
        # Validate time range
        if start_time >= end_time:
            return jsonify({"error": "start_time must be less than end_time"}), 400
        
        # Maximum range: 7 days
        if end_time - start_time > 7 * 24 * 3600:
            return jsonify({"error": "Time range cannot exceed 7 days"}), 400
        
        # Validate aggregation interval
        if aggregation_interval is not None:
            if aggregation_interval <= 0:
                return jsonify({"error": "aggregation_interval must be positive"}), 400
            # Cap aggregation at 1 hour
            if aggregation_interval > 3600:
                return jsonify({"error": "aggregation_interval cannot exceed 3600 seconds (1 hour)"}), 400
        
        stats = collector.get_traffic_stats(username, start_time, end_time, aggregation_interval)
        aggregated = collector.get_aggregated_stats(username, start_time, end_time)
        
        return jsonify({
            "username": username,
            "start_time": start_time,
            "end_time": end_time,
            "data_points": stats,
            "aggregated": aggregated
        })
    except Exception as e:
        logger.error(f"Error getting client traffic stats: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/clients/<username>/traffic-stats/stream', methods=['GET'])
def stream_client_traffic_stats(username):
    """Stream real-time traffic statistics for a client using Server-Sent Events (SSE)"""
    try:
        # Check auth - token can come from Authorization header or query param (for EventSource)
        from ..config.constants import AUTH_ENABLED
        if AUTH_ENABLED:
            token = None
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
            else:
                token = request.args.get('token')
            
            if not token:
                return jsonify({"error": "Missing authorization token"}), 401
            
            token_manager = current_app.token_manager
            if not token_manager or not token_manager.is_valid(token):
                return jsonify({"error": "Invalid or expired token"}), 401
        
        collector = current_app.traffic_stats_collector
        if not collector:
            return jsonify({"error": "Traffic statistics collector not available"}), 503
        
        config_manager = current_app.config_manager
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        def generate():
            """Generate SSE stream"""
            try:
                # Send initial data
                current_time = int(time.time())
                start_time = current_time - 3600  # Last hour
                
                stats = collector.get_traffic_stats(username, start_time, current_time)
                aggregated = collector.get_aggregated_stats(username, start_time, current_time)
                
                yield f"data: {json.dumps({'type': 'initial', 'data': stats, 'aggregated': aggregated})}\n\n"
                
                # Stream updates every 5 seconds
                last_timestamp = current_time
                while True:
                    time.sleep(5)
                    current_time = int(time.time())
                    
                    # Get new data points since last update
                    new_stats = collector.get_traffic_stats(username, last_timestamp, current_time)
                    if new_stats:
                        # Calculate aggregated for the update period
                        period_aggregated = collector.get_aggregated_stats(username, last_timestamp, current_time)
                        yield f"data: {json.dumps({'type': 'update', 'data': new_stats, 'aggregated': period_aggregated})}\n\n"
                        last_timestamp = current_time
                    else:
                        # Send heartbeat to keep connection alive
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            except GeneratorExit:
                logger.debug(f"SSE stream closed for client {username}")
            except Exception as e:
                logger.error(f"Error in SSE stream for client {username}: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',  # Disable buffering in nginx
                'Connection': 'keep-alive'
            }
        )
    except Exception as e:
        logger.error(f"Error starting SSE stream for client {username}: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/clients/<username>/traffic-stats/all-time', methods=['GET'])
@require_auth
def get_client_all_time_traffic_stats(username):
    """Get all-time aggregated traffic statistics for a client"""
    try:
        collector = current_app.traffic_stats_collector
        if not collector:
            return jsonify({"error": "Traffic statistics collector not available"}), 503
        
        config_manager = current_app.config_manager
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        stats = collector.get_all_time_stats(username)
        
        return jsonify({
            "username": username,
            **stats
        })
    except Exception as e:
        logger.error(f"Error getting all-time traffic stats: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/clients/<username>/traffic-stats/clear-all-time', methods=['POST'])
@require_auth
def clear_client_all_time_stats(username):
    """Clear all-time traffic statistics for a client (resets counters, but keeps history)"""
    try:
        collector = current_app.traffic_stats_collector
        if not collector:
            return jsonify({"error": "Traffic statistics collector not available"}), 503
        
        config_manager = current_app.config_manager
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        collector.clear_client_all_time_stats(username)
        
        return jsonify({
            "message": "All-time traffic statistics cleared successfully",
            "username": username
        })
    except Exception as e:
        logger.error(f"Error clearing all-time traffic stats: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/grafana/clients/<username>/traffic', methods=['GET'])
@require_auth
def get_grafana_traffic_data(username):
    """
    Get traffic statistics for Grafana JSON API data source.
    Returns data in Grafana-compatible format.
    
    Query parameters:
    - from: start time (Unix timestamp in seconds)
    - to: end time (Unix timestamp in seconds)
    - interval: aggregation interval in seconds (optional)
    """
    try:
        collector = current_app.traffic_stats_collector
        if not collector:
            return jsonify({"error": "Traffic statistics collector not available"}), 503
        
        config_manager = current_app.config_manager
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        # Get time range from query parameters (Grafana uses 'from' and 'to')
        from_time = request.args.get('from', type=int)
        to_time = request.args.get('to', type=int)
        interval = request.args.get('interval', type=int)  # optional aggregation interval
        
        # Default to last hour if not specified
        if to_time is None:
            to_time = int(time.time())
        if from_time is None:
            from_time = to_time - 3600
        
        # Convert to seconds if provided in milliseconds (Grafana sometimes sends ms)
        if from_time > 10000000000:  # Likely milliseconds
            from_time = from_time // 1000
        if to_time > 10000000000:
            to_time = to_time // 1000
        
        # Validate time range
        if from_time >= to_time:
            return jsonify({"error": "from must be less than to"}), 400
        
        # Maximum range: 30 days
        if to_time - from_time > 30 * 24 * 3600:
            return jsonify({"error": "Time range cannot exceed 30 days"}), 400
        
        # Get traffic stats
        stats = collector.get_traffic_stats(username, from_time, to_time, interval)
        
        # Convert to Grafana format: array of series with datapoints
        # Each datapoint is [value, timestamp_in_milliseconds]
        received_points = []
        sent_points = []
        
        for point in stats:
            # Calculate speeds (bytes per second)
            time_interval = interval if interval else 5  # default 5 seconds
            received_speed = point.get('rx_bytes_delta', 0) / time_interval
            sent_speed = point.get('tx_bytes_delta', 0) / time_interval
            
            # Convert timestamp to milliseconds for Grafana
            timestamp_ms = point.get('timestamp', 0) * 1000
            
            received_points.append([received_speed, timestamp_ms])
            sent_points.append([sent_speed, timestamp_ms])
        
        # Return in Grafana format
        return jsonify([
            {
                "target": f"{username} - Received",
                "datapoints": received_points
            },
            {
                "target": f"{username} - Sent",
                "datapoints": sent_points
            }
        ])
    except Exception as e:
        logger.error(f"Error getting Grafana traffic data for {username}: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/grafana/clients/<username>/traffic-bytes', methods=['GET'])
@require_auth
def get_grafana_traffic_bytes(username):
    """
    Get total traffic (bytes) for Grafana JSON API data source.
    Returns cumulative byte counts instead of speeds.
    """
    try:
        collector = current_app.traffic_stats_collector
        if not collector:
            return jsonify({"error": "Traffic statistics collector not available"}), 503
        
        config_manager = current_app.config_manager
        if not config_manager.has_client(username):
            return jsonify({"error": "Client not found"}), 404
        
        from_time = request.args.get('from', type=int)
        to_time = request.args.get('to', type=int)
        interval = request.args.get('interval', type=int)
        
        if to_time is None:
            to_time = int(time.time())
        if from_time is None:
            from_time = to_time - 3600
        
        if from_time > 10000000000:
            from_time = from_time // 1000
        if to_time > 10000000000:
            to_time = to_time // 1000
        
        if from_time >= to_time:
            return jsonify({"error": "from must be less than to"}), 400
        
        stats = collector.get_traffic_stats(username, from_time, to_time, interval)
        
        received_points = []
        sent_points = []
        
        for point in stats:
            timestamp_ms = point.get('timestamp', 0) * 1000
            received_bytes = point.get('rx_bytes_delta', 0)
            sent_bytes = point.get('tx_bytes_delta', 0)
            
            received_points.append([received_bytes, timestamp_ms])
            sent_points.append([sent_bytes, timestamp_ms])
        
        return jsonify([
            {
                "target": f"{username} - Received Bytes",
                "datapoints": received_points
            },
            {
                "target": f"{username} - Sent Bytes",
                "datapoints": sent_points
            }
        ])
    except Exception as e:
        logger.error(f"Error getting Grafana traffic bytes for {username}: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/grafana/clients', methods=['GET'])
@require_auth
def get_grafana_clients_list():
    """
    Get list of all clients for Grafana query builder.
    Returns list of available clients.
    """
    try:
        config_manager = current_app.config_manager
        clients = config_manager.clients
        
        # Return list of client usernames
        return jsonify([
            {"text": username, "value": username}
            for username in clients.keys()
        ])
    except Exception as e:
        logger.error(f"Error getting Grafana clients list: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/grafana/status', methods=['GET'])
@require_auth
def get_grafana_status():
    """
    Get server status metrics for Grafana.
    Returns various server metrics as time series.
    """
    try:
        config_manager = current_app.config_manager
        wg_manager = current_app.wg_manager
        obfuscator_manager = current_app.obfuscator_manager
        
        from ..wireguard.stats import WireGuardStats
        
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
            except Exception:
                pass
        
        current_time_ms = int(time.time() * 1000)
        
        # Return metrics as time series
        return jsonify([
            {
                "target": "Total Clients",
                "datapoints": [[len(config_manager.clients), current_time_ms]]
            },
            {
                "target": "Connected Clients",
                "datapoints": [[connected_clients_count, current_time_ms]]
            },
            {
                "target": "WireGuard Running",
                "datapoints": [[1 if wg_status["running"] else 0, current_time_ms]]
            },
            {
                "target": "Obfuscator Enabled",
                "datapoints": [[1 if obfuscator_status.get("enabled", False) else 0, current_time_ms]]
            },
            {
                "target": "Obfuscator Running",
                "datapoints": [[1 if obfuscator_status.get("running", False) else 0, current_time_ms]]
            }
        ])
    except Exception as e:
        logger.error(f"Error getting Grafana status: {e}")
        return jsonify({"error": str(e)}), 500

