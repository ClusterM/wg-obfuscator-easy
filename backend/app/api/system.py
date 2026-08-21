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
import logging
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
import pytz

from ..auth.tokens import require_auth
from .errors import error_response

logger = logging.getLogger(__name__)

bp = Blueprint('system', __name__)


def _is_valid_timezone(timezone_name):
    """Return True if timezone_name is a known IANA timezone"""
    if not timezone_name:
        return False
    try:
        pytz.timezone(timezone_name)
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        return False


def _timezone_from_localtime():
    """Resolve timezone name from /etc/localtime if it points into zoneinfo"""
    localtime_path = "/etc/localtime"
    zoneinfo_dir = "/usr/share/zoneinfo"
    if not os.path.exists(localtime_path):
        return None
    try:
        target = os.path.realpath(localtime_path)
        prefix = os.path.realpath(zoneinfo_dir) + os.sep
        if target.startswith(prefix):
            timezone_name = target[len(prefix):]
            if _is_valid_timezone(timezone_name):
                return timezone_name
    except OSError as e:
        logger.debug(f"Failed to resolve {localtime_path}: {e}")
    return None


def _timezone_from_timezone_file():
    """Read Debian-style /etc/timezone when it is a regular file"""
    timezone_file = "/etc/timezone"
    if not os.path.isfile(timezone_file):
        if os.path.exists(timezone_file):
            logger.debug(f"{timezone_file} exists but is not a file, skipping")
        return None
    try:
        with open(timezone_file, "r", encoding="utf-8") as f:
            timezone_name = f.read().strip()
        if _is_valid_timezone(timezone_name):
            return timezone_name
    except OSError as e:
        logger.debug(f"Failed to read {timezone_file}: {e}")
    return None


def get_current_timezone():
    """
    Detect the effective timezone without assuming /etc/timezone is a file.

    Order: TZ environment variable, /etc/localtime, /etc/timezone, UTC.
    """
    tz_env = os.environ.get("TZ", "").strip()
    if _is_valid_timezone(tz_env):
        return tz_env

    from_localtime = _timezone_from_localtime()
    if from_localtime:
        return from_localtime

    from_file = _timezone_from_timezone_file()
    if from_file:
        return from_file

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

        # Process timezone is what actually affects log timestamps
        os.environ['TZ'] = timezone_name
        try:
            time.tzset()
        except AttributeError:
            # tzset not available on all platforms
            pass

        # Save timezone to database
        from ..database import set_config_value
        set_config_value("system_timezone", timezone_name)

        try:
            subprocess.run(['ln', '-sf', zoneinfo_path, '/etc/localtime'],
                          check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.warning(
                "Failed to update /etc/localtime symlink: %s",
                e.stderr.decode().strip() if e.stderr else str(e)
            )

        timezone_file = "/etc/timezone"
        if os.path.isdir(timezone_file):
            logger.warning(
                "%s is a directory (likely a host bind mount); skip writing",
                timezone_file
            )
        else:
            try:
                with open(timezone_file, "w", encoding="utf-8") as f:
                    f.write(f"{timezone_name}\n")
            except OSError as e:
                logger.warning("Failed to write %s: %s", timezone_file, e)

        return True, None

    except Exception as e:
        error_msg = f"Failed to set timezone: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


@bp.route('/timezone', methods=['GET'])
@require_auth
def get_system_timezone():
    """Get current system timezone information"""
    try:
        from ..database import get_config_value
        saved_tz = get_config_value("system_timezone")
        current_tz = saved_tz if _is_valid_timezone(saved_tz) else get_current_timezone()
        offset = get_timezone_offset(current_tz)
        available_timezones = get_available_timezones()

        return jsonify({
            "timezone": current_tz,
            "offset": offset,
            "available_timezones": available_timezones
        })

    except Exception as e:
        logger.error(f"Error getting system timezone: {e}")
        return error_response(e)


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
        return error_response(e)
