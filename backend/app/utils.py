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

import os
import requests
import secrets
import string
import logging
from typing import Optional

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


def generate_obfuscation_key(length: int = 64) -> str:
    """
    Generate random obfuscation key
    
    Args:
        length: Key length in characters
        
    Returns:
        Random ASCII string
    """
    return ''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*()_+-=[]{}|;:,.<>?') for _ in range(length))


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
    
    config_manager.save_config()


def check_and_set_system_timezone() -> bool:
    """
    Check if system timezone matches saved timezone and correct if needed.
    Returns True if restart is needed.
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
            return True  # Need restart
        else:
            logger.error(f"Failed to set system timezone: {error_msg}")
            return False

    except Exception as e:
        logger.error(f"Error checking system timezone: {e}")
        return False

