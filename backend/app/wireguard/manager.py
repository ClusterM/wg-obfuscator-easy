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

"""WireGuard service management"""

import subprocess
import logging
from typing import Dict, Optional

from ..config.constants import INTERNAL_WG_PORT
from ..exceptions import ServiceError

logger = logging.getLogger(__name__)


class WireGuardManager:
    """Manages WireGuard service operations"""
    
    def __init__(self, wg_interface: str = "wg0"):
        self.wg_interface = wg_interface
    
    def stop(self) -> None:
        """Stop WireGuard interface"""
        # Check if already stopped
        status = self.status()
        if not status["running"]:
            return
        
        try:
            subprocess.run(
                ["wg-quick", "down", self.wg_interface],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                check=False
            )
            logger.info(f"Stopped WireGuard interface {self.wg_interface}")
        except Exception as e:
            logger.warning(f"Error stopping WireGuard: {e}")
    
    def start(self) -> None:
        """Start WireGuard interface"""
        try:
            output = subprocess.run(
                ["wg-quick", "up", self.wg_interface],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Started WireGuard interface {self.wg_interface}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else "Unknown error"
            logger.error(f"Failed to start WireGuard: {error_msg}")
            raise ServiceError(f"Failed to start WireGuard: {error_msg}")
    
    def restart(self) -> None:
        """Restart WireGuard interface"""
        logger.info(f"Restarting WireGuard interface {self.wg_interface}")
        self.stop()
        self.start()
    
    def status(self) -> Dict[str, any]:
        """
        Check if WireGuard interface is running
        
        Returns:
            Dictionary with 'running' (bool) and 'error' (str or None)
        """
        try:
            result = subprocess.run(
                ["wg", "show", self.wg_interface],
                capture_output=True,
                text=True,
                check=False
            )
            is_running = result.returncode == 0
            error = None if is_running else "Interface not found or not running"
            return {
                "running": is_running,
                "error": error
            }
        except Exception as e:
            logger.error(f"Error checking WireGuard status: {e}")
            return {
                "running": False,
                "error": str(e)
            }

