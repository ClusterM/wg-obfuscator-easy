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

"""Utility functions"""

import ipaddress
import os
import socket
import requests
import secrets
import string
import logging
from typing import List, Optional

from .config.constants import EXTERNAL_IP_FILE, DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
from .exceptions import ConfigError
from .api.system import get_current_timezone, set_system_timezone
from .database import get_config_value

logger = logging.getLogger(__name__)


def get_external_ip() -> str:
    """
    Get external IP address from environment variable, file, or external service
    
    Returns:
        External IP address as string
        
    Raises:
        ConfigError: If IP cannot be obtained
    """
    # Try environment variable first
    ip = os.getenv("EXTERNAL_IP")
    if ip:
        logger.info(f"Got external IP from environment variable: {ip}")
        return ip
    
    # Try reading from file
    if os.path.exists(EXTERNAL_IP_FILE):
        try:
            with open(EXTERNAL_IP_FILE, "r") as f:
                ip = f.read().strip()
            if ip:
                logger.info(f"Got external IP from file: {ip}")
                return ip
        except Exception as e:
            logger.warning(f"Failed to read IP from file: {e}")
    
    # Try getting from external service
    try:
        response = requests.get("http://ifconfig.me", timeout=10)
        ip = response.text.strip()
        if ip:
            # Save IP to file
            try:
                with open(EXTERNAL_IP_FILE, "w") as f:
                    f.write(ip)
            except Exception as e:
                logger.warning(f"Failed to save IP to file: {e}")
            logger.info(f"Got external IP from external service: {ip}")
            return ip
    except Exception as e:
        logger.error(f"Failed to get external IP from external service: {e}")
    
    raise ConfigError("Failed to get external IP address")


def resolve_external_ipv4(host: str) -> List[str]:
    """
    Resolve EXTERNAL_IP (IPv4 or hostname) to one or more IPv4 addresses.

    Used only when excluding the server address from client AllowedIPs.
    """
    if not isinstance(host, str) or not host.strip():
        raise ConfigError("EXTERNAL_IP is empty or invalid")

    host = host.strip()
    try:
        parsed = ipaddress.ip_address(host)
        if isinstance(parsed, ipaddress.IPv4Address):
            return [str(parsed)]
        raise ConfigError(f"EXTERNAL_IP must be an IPv4 address or hostname, got IPv6: {host}")
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ConfigError(f"Failed to resolve EXTERNAL_IP '{host}' to an IPv4 address: {e}")

    addresses: List[str] = []
    seen = set()
    for info in infos:
        addr = info[4][0]
        if addr not in seen:
            seen.add(addr)
            addresses.append(addr)

    if not addresses:
        raise ConfigError(f"Failed to resolve EXTERNAL_IP '{host}' to an IPv4 address")

    logger.debug(f"Resolved EXTERNAL_IP '{host}' to {addresses}")
    return addresses


def parse_listen_port_env() -> Optional[int]:
    """Parse LISTEN_PORT env var. Empty/unset returns None."""
    value = os.getenv("LISTEN_PORT")
    if value is None or not str(value).strip():
        return None
    try:
        port = int(value)
        if port < 1 or port > 65535:
            raise ValueError("Port out of range")
        return port
    except ValueError:
        raise ConfigError(f"Invalid LISTEN_PORT value: {value}")


def get_effective_listen_port(config: dict, external_port: int) -> int:
    """Return stored listen_port, or EXTERNAL_PORT when listen_port is null."""
    listen_port = config.get("listen_port")
    if listen_port is None:
        return external_port
    return int(listen_port)


def get_external_port() -> int:
    """
    Get external port from environment variable
    
    Returns:
        External port number
        
    Raises:
        ConfigError: If port is not set or invalid
    """
    external_port = os.getenv("EXTERNAL_PORT")
    if external_port is None:
        raise ConfigError("EXTERNAL_PORT environment variable is not set")
    
    try:
        port = int(external_port)
        if port < 1 or port > 65535:
            raise ValueError("Port out of range")
        logger.info(f"Got external port: {port}")
        return port
    except ValueError as e:
        raise ConfigError(f"Invalid EXTERNAL_PORT value: {external_port}")


# Written as `key = ...` in the obfuscator config. `#` starts a comment there,
# so the key must stay alphanumeric.
OBFUSCATION_KEY_ALPHABET = string.ascii_letters + string.digits


def is_valid_obfuscation_key(key: str) -> bool:
    """Return True if key is empty or contains only ASCII letters and digits."""
    return all(c in OBFUSCATION_KEY_ALPHABET for c in key)


def generate_obfuscation_key(length: int = 64) -> str:
    """
    Generate random obfuscation key
    
    Args:
        length: Key length in characters
        
    Returns:
        Random alphanumeric string
    """
    return ''.join(secrets.choice(OBFUSCATION_KEY_ALPHABET) for _ in range(length))


def initialize_config(config_manager) -> None:
    """
    Initialize configuration with default values and generate keys if needed
    
    Args:
        config_manager: ConfigManager instance
    """
    # Initialize admin credentials
    admin_username = os.getenv("ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)
    admin_password = os.getenv("ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    
    from .auth.password import hash_password
    
    # Store admin credentials hash if not exists
    if "admin_password_hash" not in config_manager.main:
        config_manager.main["admin_password_hash"] = hash_password(admin_password)
        config_manager.main["admin_username"] = admin_username
        logger.info("Initialized admin credentials")
    
    if "admin_username" not in config_manager.main:
        config_manager.main["admin_username"] = admin_username
        logger.info("Set admin username")
    
    # Create server keys if they don't exist
    if "server_private_key" not in config_manager.main or "server_public_key" not in config_manager.main:
        logger.info("Generating server key pair...")
        from .clients.manager import ClientManager
        # We need a temporary client manager to generate keys
        # For now, we'll generate them directly
        import subprocess
        try:
            response = subprocess.run(["wg", "genkey"], capture_output=True, text=True, check=True)
            private = response.stdout.splitlines()[0]
            response_public = subprocess.run(["wg", "pubkey"], input=private, capture_output=True, text=True, check=True)
            public = response_public.stdout.splitlines()[0]
            config_manager.main["server_private_key"] = private
            config_manager.main["server_public_key"] = public
            logger.info("Generated server key pair")
        except subprocess.CalledProcessError as e:
            raise ConfigError(f"Failed to generate server keys: {e}")
    
    # Generate obfuscation key if not exists
    if "obfuscation_key" not in config_manager.main:
        config_manager.main["obfuscation_key"] = generate_obfuscation_key()
        logger.info("Generated obfuscation key")

    if "listen_port" not in config_manager.main:
        env_listen_port = parse_listen_port_env()
        if env_listen_port is not None:
            config_manager.main["listen_port"] = env_listen_port
            logger.info(f"Initialized listen_port from LISTEN_PORT: {env_listen_port}")
    
    config_manager.save_config()


def check_and_set_system_timezone() -> bool:
    """
    Ensure system timezone matches saved timezone.
    
    Returns:
        True if timezone was changed, False otherwise.
    """
    try:
        saved_timezone = get_config_value("system_timezone")
        if not saved_timezone:
            logger.info("No saved timezone found, skipping timezone check")
            return False

        current_timezone = get_current_timezone()

        if current_timezone == saved_timezone:
            logger.info(f"System timezone matches saved timezone: {current_timezone}")
            return False

        logger.info(f"System timezone mismatch - current: {current_timezone}, saved: {saved_timezone}")
        logger.info(f"Setting system timezone to saved value: {saved_timezone}")

        success, error_msg = set_system_timezone(saved_timezone)
        if success:
            logger.info(f"Successfully set system timezone to: {saved_timezone}")
            return True
        
        logger.error(f"Failed to set system timezone: {error_msg}")
        return False

    except Exception as e:
        logger.error(f"Error checking system timezone: {e}")
        return False

