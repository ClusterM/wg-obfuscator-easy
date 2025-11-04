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

Custom exceptions for the application
"""


class WireGuardError(Exception):
    """Base exception for WireGuard related errors"""
    pass


class ClientNotFoundError(WireGuardError):
    """Raised when a client is not found"""
    pass


class ClientAlreadyExistsError(WireGuardError):
    """Raised when trying to create a client that already exists"""
    pass


class ConfigValidationError(WireGuardError):
    """Raised when configuration validation fails"""
    pass


class ConfigError(WireGuardError):
    """Raised when configuration operations fail"""
    pass


class AuthenticationError(WireGuardError):
    """Raised when authentication fails"""
    pass


class ServiceError(WireGuardError):
    """Raised when service operations fail"""
    pass

