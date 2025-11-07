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

"""System configuration API endpoints"""

import os
import subprocess
import signal
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
import pytz

logger = logging.getLogger(__name__)

bp = Blueprint('system', __name__)


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


def get_current_timezone():
    """Get current system timezone"""
    try:
        with open('/etc/timezone', 'r') as f:
            timezone_name = f.read().strip()
        return timezone_name
    except (FileNotFoundError, IOError) as e:
        logger.error(f"Failed to read /etc/timezone: {e}")
        return "UTC"


def get_timezone_offset(timezone_name):
    """Get UTC offset for timezone"""
    try:
        tz = pytz.timezone(timezone_name)
        now = datetime.now(tz)
        offset = now.strftime('%z')
        # Format as +HH:MM or -HH:MM
        return f"{offset[:3]}:{offset[3:]}"
    except Exception as e:
        logger.error(f"Failed to get offset for timezone {timezone_name}: {e}")
        return "+00:00"


def get_available_timezones():
    """Get list of available timezones"""
    try:
        # Get timezones from zoneinfo directory
        zoneinfo_dir = '/usr/share/zoneinfo'
        if not os.path.exists(zoneinfo_dir):
            logger.warning(f"Zoneinfo directory not found: {zoneinfo_dir}")
            return ["UTC"]

        timezones = []

        # Walk through zoneinfo directory and collect timezone names
        for root, dirs, files in os.walk(zoneinfo_dir):
            for file in files:
                # Skip files that start with + or contain dots (like +VERSION, .tab files)
                if file.startswith('+') or '.' in file:
                    continue

                # Get relative path from zoneinfo directory
                rel_path = os.path.relpath(os.path.join(root, file), zoneinfo_dir)

                # Skip posix/ and right/ subdirectories (they are duplicates)
                if rel_path.startswith(('posix/', 'right/')):
                    continue

                # Validate timezone by trying to create pytz object
                try:
                    pytz.timezone(rel_path)
                    timezones.append(rel_path)
                except pytz.exceptions.UnknownTimeZoneError:
                    continue

        # Sort timezones alphabetically
        timezones.sort()

        # Ensure UTC is included
        if "UTC" not in timezones:
            timezones.insert(0, "UTC")

        return timezones

    except Exception as e:
        logger.error(f"Failed to get available timezones: {e}")
        return ["UTC"]


def set_system_timezone(timezone_name):
    """Set system timezone"""
    try:
        # Validate timezone
        try:
            pytz.timezone(timezone_name)
        except pytz.exceptions.UnknownTimeZoneError:
            return False, f"Invalid timezone: {timezone_name}"

        # Check if timezone file exists
        zoneinfo_path = f"/usr/share/zoneinfo/{timezone_name}"
        if not os.path.exists(zoneinfo_path):
            return False, f"Timezone file not found: {zoneinfo_path}"

        # Update /etc/timezone file
        with open('/etc/timezone', 'w') as f:
            f.write(f"{timezone_name}\n")

        # Update /etc/localtime symlink
        subprocess.run(['ln', '-sf', zoneinfo_path, '/etc/localtime'],
                      check=True, capture_output=True)

        # Save timezone to database
        from ..database import set_config_value
        set_config_value("system_timezone", timezone_name)

        return True, None

    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to update timezone symlink: {e.stderr.decode().strip()}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Failed to set timezone: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


@bp.route('/timezone', methods=['GET'])
@require_auth
def get_system_timezone():
    """Get current system timezone information"""
    try:
        current_tz = get_current_timezone()
        offset = get_timezone_offset(current_tz)
        available_timezones = get_available_timezones()

        return jsonify({
            "timezone": current_tz,
            "offset": offset,
            "available_timezones": available_timezones
        })

    except Exception as e:
        logger.error(f"Error getting system timezone: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/timezone', methods=['PATCH'])
@require_auth
def set_system_timezone_endpoint():
    """Set system timezone"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        if "timezone" not in data:
            return jsonify({"error": "timezone field is required"}), 400

        new_timezone = data["timezone"]
        if not isinstance(new_timezone, str):
            return jsonify({"error": "timezone must be a string"}), 400

        # Validate and set timezone
        success, error_msg = set_system_timezone(new_timezone)
        if not success:
            return jsonify({"error": error_msg}), 400

        # Get updated timezone info
        current_tz = get_current_timezone()
        offset = get_timezone_offset(current_tz)

        logger.info(f"System timezone changed to: {current_tz}")

        return jsonify({
            "message": "Timezone updated successfully",
            "timezone": current_tz,
            "offset": offset
        })

    except Exception as e:
        logger.error(f"Error setting system timezone: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/restart', methods=['POST'])
@require_auth
def restart_system():
    """Restart the application gracefully"""
    try:
        logger.info("Initiating graceful restart via API call")
        # Send SIGHUP to current process for graceful restart
        os.kill(os.getpid(), signal.SIGHUP)
        return jsonify({
            "message": "System restart initiated. The application will restart automatically."
        })
    except Exception as e:
        logger.error(f"Error initiating system restart: {e}")
        return jsonify({"error": str(e)}), 500
