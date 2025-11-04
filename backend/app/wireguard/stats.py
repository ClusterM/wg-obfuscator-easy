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

"""WireGuard statistics collection"""

import subprocess
import time
import logging
from typing import Dict, List, Optional

from ..config.constants import HANDSHAKE_TIMEOUT
from ..exceptions import ServiceError

logger = logging.getLogger(__name__)


class WireGuardStats:
    """Collects and parses WireGuard statistics"""
    
    def __init__(self, wg_interface: str = "wg0"):
        self.wg_interface = wg_interface
    
    def get_stats(self, clients: Optional[Dict] = None) -> Optional[Dict]:
        """
        Get WireGuard statistics from wg show command
        
        Args:
            clients: Optional clients dictionary to map public keys to usernames
            
        Returns:
            Dictionary with interface name and peers statistics, or None if interface not found
        """
        try:
            # Get stats in dump format
            result = subprocess.run(
                ["wg", "show", self.wg_interface, "dump"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                logger.warning(f"WireGuard interface {self.wg_interface} not found or not running")
                return None
            
            stats = {
                "interface": self.wg_interface,
                "peers": []
            }
            
            # Parse wg dump output format: public_key, preshared_key, endpoint, allowed_ips, 
            # latest_handshake, transfer_rx, transfer_tx, persistent_keepalive
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 6:
                    public_key = parts[0]
                    endpoint = parts[2] if len(parts) > 2 and parts[2] != '(none)' else None
                    allowed_ips = parts[3] if len(parts) > 3 else ""
                    latest_handshake = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
                    transfer_rx = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0
                    transfer_tx = int(parts[6]) if len(parts) > 6 and parts[6].isdigit() else 0
                    
                    # Swap rx/tx from server perspective to client perspective
                    # transfer_rx (server received = client sent) -> client tx (outgoing)
                    # transfer_tx (server sent = client received) -> client rx (incoming)
                    client_rx_bytes = transfer_tx  # Client receives what server sends
                    client_tx_bytes = transfer_rx  # Client sends what server receives
                    
                    # Find client name by public key
                    client_name = None
                    if clients:
                        for name, client in clients.items():
                            if client.get('public_key') == public_key:
                                client_name = name
                                break
                    
                    # Check if connected (handshake within timeout)
                    is_connected = latest_handshake > 0 and (
                        time.time() - latest_handshake < HANDSHAKE_TIMEOUT
                    )
                    
                    peer_info = {
                        "public_key": public_key,
                        "client_name": client_name,
                        "endpoint": endpoint,
                        "allowed_ips": allowed_ips,
                        "latest_handshake": latest_handshake,
                        "transfer_rx_bytes": client_rx_bytes,  # Client incoming (server outgoing)
                        "transfer_tx_bytes": client_tx_bytes,  # Client outgoing (server incoming)
                        "is_connected": is_connected
                    }
                    stats["peers"].append(peer_info)
            
            logger.debug(f"Collected stats for {len(stats['peers'])} peers")
            return stats
        except Exception as e:
            logger.error(f"Failed to get WireGuard statistics: {e}")
            raise ServiceError(f"Failed to get WireGuard statistics: {str(e)}")

