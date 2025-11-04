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


"""Configuration management module"""

from .constants import *
from .manager import ConfigManager

__all__ = ['ConfigManager', 'INTERNAL_WG_PORT', 'DEFAULT_CLIENT_OBFUSCATOR_PORT',
           'EXTERNAL_IP_FILE', 'WG_OBFUSCATOR_CONFIG_FILE', 'HANDSHAKE_TIMEOUT',
           'DEFAULT_ADMIN_USERNAME', 'DEFAULT_ADMIN_PASSWORD', 'AUTH_ENABLED',
           'VERBOSITY_LEVELS', 'DEFAULT_VERBOSITY_LEVEL', 'MASKING_TYPES',
           'DEFAULT_MASKING_TYPE', 'MASKING_TYPES_NAMES', 'DEFAULT_WG_CONFIG',
           'TOKEN_EXPIRES_IN']

