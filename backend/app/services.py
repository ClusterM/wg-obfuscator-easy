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

"""Service orchestration for applying configuration changes"""

import logging
from typing import Optional

from .wireguard.config import WireGuardConfigGenerator
from .wireguard.manager import WireGuardManager
from .obfuscator.config import ObfuscatorConfigGenerator
from .obfuscator.manager import ObfuscatorManager
from .config.constants import INTERNAL_WG_PORT

logger = logging.getLogger(__name__)


class ServiceManager:
    """Orchestrates service management and configuration generation"""
    
    def __init__(
        self,
        config_manager,
        client_manager,
        wg_manager: WireGuardManager,
        obfuscator_manager: ObfuscatorManager,
        external_ip: str,
        external_port: int
    ):
        self.config_manager = config_manager
        self.client_manager = client_manager
        self.wg_manager = wg_manager
        self.obfuscator_manager = obfuscator_manager
        self.external_ip = external_ip
        self.external_port = external_port
    
    def generate_configs(self) -> None:
        """Generate both WireGuard and obfuscator configuration files"""
        config = self.config_manager.main
        clients = self.config_manager.clients
        
        # Generate WireGuard config
        wg_config_content = WireGuardConfigGenerator.generate_server_config(
            config=config,
            clients=clients,
            external_port=self.external_port,
            obfuscation=config.get('obfuscation', False)
        )
        WireGuardConfigGenerator.save_config_file(
            wg_config_content,
            config['wg_interface']
        )
        
        # Generate obfuscator config
        if config.get('obfuscation', False):
            obf_config_content = ObfuscatorConfigGenerator.generate_server_config(
                external_port=self.external_port,
                obfuscation_key=config['obfuscation_key'],
                masking_type=config.get('masking_type', 'NONE'),
                masking_forced=config.get('masking_forced', False),
                verbosity_level=config.get('verbosity_level', 'INFO')
            )
            ObfuscatorConfigGenerator.save_config_file(obf_config_content)
        
        logger.debug("Generated WireGuard and obfuscator configuration files")
    
    def restart_services(self) -> None:
        """Restart WireGuard and obfuscator services"""
        config = self.config_manager.main
        
        # Stop obfuscator first
        self.obfuscator_manager.stop()
        
        # Stop WireGuard
        self.wg_manager.stop()
        
        # Only start services if WireGuard is enabled
        if config.get('enabled', True):
            # Start obfuscator if enabled
            if config.get('obfuscation', False):
                self.obfuscator_manager.start()
            
            # Start WireGuard
            self.wg_manager.start()
            logger.info("Started WireGuard and obfuscator services")
        else:
            logger.info("WireGuard is disabled, services not started")
    
    def apply_config_changes(self) -> None:
        """Apply configuration changes: generate configs and restart services"""
        logger.info("Applying configuration changes...")
        self.generate_configs()
        self.restart_services()
        logger.info("Configuration changes applied successfully")

