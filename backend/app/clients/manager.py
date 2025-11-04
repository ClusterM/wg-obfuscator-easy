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

"""Client management operations"""

import subprocess
import ipaddress
import logging
from typing import Dict, Tuple, List

from ..config.constants import DEFAULT_CLIENT_OBFUSCATOR_PORT
from ..exceptions import ClientAlreadyExistsError, ClientNotFoundError, ServiceError
from ..wireguard.manager import WireGuardManager
from ..wireguard.config import WireGuardConfigGenerator
from ..obfuscator.config import ObfuscatorConfigGenerator
from ..obfuscator.manager import ObfuscatorManager

logger = logging.getLogger(__name__)


class ClientManager:
    """Manages WireGuard clients"""
    
    def __init__(
        self,
        config_manager,
        wg_manager: WireGuardManager,
        obfuscator_manager: ObfuscatorManager
    ):
        self.config_manager = config_manager
        self.wg_manager = wg_manager
        self.obfuscator_manager = obfuscator_manager
    
    def generate_key_pair(self) -> Tuple[str, str]:
        """
        Generate WireGuard key pair
        
        Returns:
            Tuple of (private_key, public_key)
            
        Raises:
            ServiceError: If key generation fails
        """
        try:
            # Generate private key
            response = subprocess.run(
                ["wg", "genkey"],
                capture_output=True,
                text=True,
                check=True
            )
            private = response.stdout.splitlines()[0]
            
            # Generate public key from private
            response_public = subprocess.run(
                ["wg", "pubkey"],
                input=private,
                capture_output=True,
                text=True,
                check=True
            )
            public = response_public.stdout.splitlines()[0]
            
            logger.debug("Generated new key pair")
            return private, public
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate key pair: {e}")
            raise ServiceError("Failed to generate server keys")
    
    def find_free_ip(self) -> int:
        """
        Find free IP address in subnet
        
        Returns:
            Free IP address (last octet)
            
        Raises:
            ServiceError: If no free IP found
        """
        config = self.config_manager.main
        ip_in_use = [client["ip"] for client in self.config_manager.clients.values()]
        
        for i in range(1, 254):
            if i not in ip_in_use and i != config["own_ip"]:
                logger.debug(f"Found free IP: {i}")
                return i
        
        raise ServiceError("No free IP found in subnet")
    
    def add_client(self, username: str, obfuscation: bool = True) -> Dict:
        """
        Add a new client
        
        Args:
            username: Client username
            obfuscation: Whether to enable obfuscation for this client
            
        Returns:
            Client configuration dictionary
            
        Raises:
            ClientAlreadyExistsError: If client already exists
            ServiceError: If no free IP found or key generation fails
        """
        if self.config_manager.has_client(username):
            raise ClientAlreadyExistsError(f"Client {username} already exists")
        
        ip = self.find_free_ip()
        private, public = self.generate_key_pair()
        
        new_client = {
            "ip": ip,
            "private_key": str(private),
            "public_key": str(public),
            "allowed_ips": ["0.0.0.0/0"],
            "obfuscator_port": DEFAULT_CLIENT_OBFUSCATOR_PORT,
            "masking_type_override": None,
            "verbosity_level": "INFO",
            "enabled": True,  # By default, new clients are enabled
        }
        
        self.config_manager.set_client(username, new_client, save=True)
        logger.info(f"Added client {username} with IP {ip}")
        return new_client
    
    def delete_client(self, username: str) -> None:
        """
        Delete a client
        
        Args:
            username: Client username
            
        Raises:
            ClientNotFoundError: If client does not exist
        """
        if not self.config_manager.has_client(username):
            raise ClientNotFoundError(f"Client {username} does not exist")
        
        self.config_manager.delete_client(username, save=True)
        logger.info(f"Deleted client {username}")
    
    def regenerate_client_keys(self, username: str) -> Tuple[str, str]:
        """
        Regenerate keys for a client
        
        Args:
            username: Client username
            
        Returns:
            Tuple of (private_key, public_key)
            
        Raises:
            ClientNotFoundError: If client does not exist
        """
        if not self.config_manager.has_client(username):
            raise ClientNotFoundError(f"Client {username} does not exist")
        
        client = self.config_manager.get_client(username)
        private, public = self.generate_key_pair()
        
        client["private_key"] = str(private)
        client["public_key"] = str(public)
        
        self.config_manager.set_client(username, client, save=True)
        logger.info(f"Regenerated keys for client {username}")
        return private, public
    
    def calculate_allowed_ips(
        self,
        allowed_subnets: List[str],
        exclude_subnets: List[str]
    ) -> List[str]:
        """
        Calculate allowed IPs excluding specified subnets
        
        Args:
            allowed_subnets: List of allowed subnet strings
            exclude_subnets: List of subnets to exclude
            
        Returns:
            List of allowed subnet strings after exclusion
        """
        # Convert input subnets to ip_network objects
        if isinstance(allowed_subnets, list) and len(allowed_subnets) > 0:
            allowed = [ipaddress.ip_network(subnet, strict=False) for subnet in allowed_subnets]
        elif isinstance(allowed_subnets, str):
            allowed = [ipaddress.ip_network(allowed_subnets, strict=False)]
        else:
            allowed = allowed_subnets
        
        if isinstance(exclude_subnets, list) and len(exclude_subnets) > 0:
            exclude = [ipaddress.ip_network(subnet, strict=False) for subnet in exclude_subnets]
        elif isinstance(exclude_subnets, str):
            exclude = [ipaddress.ip_network(exclude_subnets, strict=False)]
        else:
            exclude = exclude_subnets
        
        final_ranges = []
        # Exclude each subnet
        for exclude_subnet in exclude:
            for net in allowed:
                if exclude_subnet.overlaps(net):
                    subnets = list(net.address_exclude(exclude_subnet))
                    final_ranges.extend(subnets)
                else:
                    final_ranges.append(net)
        
        return [str(subnet) for subnet in final_ranges]
    
    def get_client_wg_config(
        self,
        username: str,
        external_ip: str,
        external_port: int
    ) -> str:
        """
        Get WireGuard configuration for a client
        
        Args:
            username: Client username
            external_ip: External IP address
            external_port: External port number
            
        Returns:
            WireGuard configuration file content
            
        Raises:
            ClientNotFoundError: If client does not exist
        """
        if not self.config_manager.has_client(username):
            raise ClientNotFoundError(f"Client {username} does not exist")
        
        config = self.config_manager.main
        client = self.config_manager.get_client(username)
        
        obfuscation = config.get('obfuscation', False)
        
        if obfuscation:
            allowed_ips_subnets = self.calculate_allowed_ips(
                client["allowed_ips"],
                [external_ip + "/32"]
            )
            allowed_ips = allowed_ips_subnets
        else:
            allowed_ips = client["allowed_ips"]
        
        return WireGuardConfigGenerator.generate_client_config(
            config=config,
            client=client,
            external_ip=external_ip,
            external_port=external_port,
            obfuscation=obfuscation,
            allowed_ips=allowed_ips,
            default_obfuscator_port=DEFAULT_CLIENT_OBFUSCATOR_PORT
        )
    
    def get_client_obfuscator_config(
        self,
        username: str,
        external_ip: str,
        external_port: int
    ) -> str:
        """
        Get obfuscator configuration for a client
        
        Args:
            username: Client username
            external_ip: External IP address
            external_port: External port number
            
        Returns:
            Obfuscator configuration file content
            
        Raises:
            ClientNotFoundError: If client does not exist
        """
        if not self.config_manager.has_client(username):
            raise ClientNotFoundError(f"Client {username} does not exist")
        
        config = self.config_manager.main
        client = self.config_manager.get_client(username)
        
        return ObfuscatorConfigGenerator.generate_client_config(
            client=client,
            external_ip=external_ip,
            external_port=external_port,
            obfuscation_key=config['obfuscation_key'],
            masking_type=config.get('masking_type', 'NONE'),
            masking_forced=config.get('masking_forced', False),
            verbosity_level=config.get('verbosity_level', 'INFO')
        )

