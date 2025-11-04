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

"""Configuration manager for loading and saving configuration using SQLite"""

import logging
from typing import Dict, Any, Optional

from .constants import DEFAULT_WG_CONFIG
from ..exceptions import ConfigError
from ..database import (
    init_database,
    get_all_config, get_config_value, set_config_value,
    get_all_clients, get_client, save_client, delete_client, client_exists
)

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages WireGuard server and clients configuration using SQLite"""
    
    def __init__(self):
        # Initialize database
        init_database()
        
        self.main: Dict[str, Any] = {}
        self.clients: Dict[str, Any] = {}
        self._load_config()
        self._load_clients()
    
    def _load_config(self) -> None:
        """Load main configuration from database or use defaults"""
        try:
            self.main = get_all_config()
            
            # If no config exists, initialize with defaults
            if not self.main:
                self.main = DEFAULT_WG_CONFIG.copy()
                # Save defaults to database
                for key, value in self.main.items():
                    set_config_value(key, value)
                logger.info("Initialized with default configuration")
            else:
                logger.info(f"Loaded configuration from database ({len(self.main)} keys)")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigError(f"Failed to load configuration: {e}")
    
    def _load_clients(self) -> None:
        """Load clients configuration from database"""
        try:
            self.clients = get_all_clients()
            logger.info(f"Loaded {len(self.clients)} clients from database")
        except Exception as e:
            logger.error(f"Failed to load clients: {e}")
            raise ConfigError(f"Failed to load clients: {e}")
    
    def save_config(self) -> None:
        """Save main configuration to database"""
        try:
            for key, value in self.main.items():
                set_config_value(key, value)
            logger.debug(f"Saved configuration to database ({len(self.main)} keys)")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise ConfigError(f"Failed to save configuration: {e}")
    
    def save_clients(self) -> None:
        """Save clients configuration to database"""
        try:
            for username, client_data in self.clients.items():
                save_client(username, client_data)
            logger.debug(f"Saved {len(self.clients)} clients to database")
        except Exception as e:
            logger.error(f"Failed to save clients: {e}")
            raise ConfigError(f"Failed to save clients: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from main config with optional default"""
        return self.main.get(key, default)
    
    def set(self, key: str, value: Any, save: bool = True) -> None:
        """Set value in main config and optionally save"""
        self.main[key] = value
        if save:
            self.save_config()
    
    def get_client(self, username: str) -> Optional[Dict[str, Any]]:
        """Get client configuration by username"""
        # Always get fresh data from database
        client = get_client(username)
        if client:
            # Update in-memory cache
            self.clients[username] = client
        elif username in self.clients:
            # Remove from cache if deleted
            del self.clients[username]
        return client
    
    def set_client(self, username: str, client_data: Dict[str, Any], save: bool = True) -> None:
        """Set client configuration and optionally save"""
        self.clients[username] = client_data
        if save:
            save_client(username, client_data)
            # Reload only this client to ensure consistency (don't reload all to avoid race conditions)
            updated_client = get_client(username)
            if updated_client:
                self.clients[username] = updated_client
    
    def delete_client(self, username: str, save: bool = True) -> None:
        """Delete client configuration and optionally save"""
        if save:
            delete_client(username)
        if username in self.clients:
            del self.clients[username]
    
    def has_client(self, username: str) -> bool:
        """Check if client exists"""
        return client_exists(username)

