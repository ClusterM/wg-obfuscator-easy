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


"""Constants and default values for the application"""

import os

# Port configuration
INTERNAL_WG_PORT = 65535  # Any
DEFAULT_CLIENT_OBFUSCATOR_PORT = 13255  # Any
API_PORT = 5000  # Flask API server port

# File paths
EXTERNAL_IP_FILE = "/etc/external_ip.txt"
WG_OBFUSCATOR_CONFIG_FILE = "/etc/wg-obfuscator.conf"

# Timeouts
HANDSHAKE_TIMEOUT = 180  # seconds

# Default credentials
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"

# Enable/disable authentication for debugging
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"

# Verbosity levels
VERBOSITY_LEVELS = ["ERROR", "WARNING", "INFO", "DEBUG", "TRACE"]
DEFAULT_VERBOSITY_LEVEL = "INFO"

# Masking types
MASKING_TYPES = ["NONE", "STUN"]  # and AUTO
DEFAULT_MASKING_TYPE = "NONE"
MASKING_TYPES_NAMES = {
    "NONE": "None",
    "STUN": "STUN",
    "AUTO": "Auto",
}

# Token expiration
TOKEN_EXPIRES_IN = 86400  # 24 hours in seconds

# Application version
APP_VERSION = "v1.0"

# Default WireGuard configuration
DEFAULT_WG_CONFIG = {
    "subnet": "10.6.13",
    "wan_interface": "eth0",
    "wg_interface": "wg0",
    "own_ip": 1,
    "enabled": True,
    "obfuscation": True,
    "verbosity_level": DEFAULT_VERBOSITY_LEVEL,
    "masking_type": DEFAULT_MASKING_TYPE,
    "masking_forced": False,
}

