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

"""Obfuscator process management"""

import subprocess
import time
import threading
import logging
import re
from datetime import datetime
from typing import Optional, Dict

from ..config.constants import WG_OBFUSCATOR_CONFIG_FILE
from ..exceptions import ServiceError
from .logs import ObfuscatorLogs

logger = logging.getLogger(__name__)


class ObfuscatorManager:
    """Manages wg-obfuscator process"""
    
    def __init__(self, log_storage: Optional[ObfuscatorLogs] = None):
        self.process: Optional[subprocess.Popen] = None
        self.log_storage = log_storage or ObfuscatorLogs()
        self._log_thread: Optional[threading.Thread] = None
        self._cached_version: Optional[str] = None  # Cache version for container lifetime
    
    def stop(self) -> None:
        """Stop wg-obfuscator process if running"""
        # Clean up zombie processes first
        self._cleanup_zombie_processes()
        
        # Check if our tracked process is still running
        if self.process is not None:
            return_code = self.process.poll()
            if return_code is not None:
                # Process already exited
                self.process = None
                return
        
        # Check if there are any running (non-zombie) wg-obfuscator processes
        if not self._is_process_running():
            # No running processes found
            self.process = None
            return
        
        try:
            # Find and kill wg-obfuscator processes (only non-zombie ones)
            subprocess.run(
                ["pkill", "-f", "wg-obfuscator"],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                check=False,
                timeout=5
            )
            
            # Wait for process to terminate, with retries
            max_attempts = 10
            for attempt in range(max_attempts):
                time.sleep(0.2)  # Wait 200ms between checks
                if not self._is_process_running():
                    # Process has terminated (or only zombies remain)
                    break
            else:
                # Process still running after max attempts
                logger.warning("Obfuscator process did not terminate within expected time")
            
            # Clean up zombies again after kill
            self._cleanup_zombie_processes()
            
            # Clean up our process reference
            self.process = None
            logger.info("Stopped obfuscator")
        except Exception as e:
            logger.warning(f"Error stopping obfuscator: {e}")
    
    def start(self) -> None:
        """
        Start wg-obfuscator in background
        
        Raises:
            ServiceError: If obfuscator fails to start
        """
        # Clean up zombie processes first
        self._cleanup_zombie_processes()
        
        # Check if process is already running
        if self._is_process_running():
            # Process is running but may not be tracked - we need to restart it
            # to capture logs properly
            if self.process is None or self.process.poll() is not None:
                logger.warning("Obfuscator is running but not tracked - restarting to capture logs")
                # Stop the untracked process
                try:
                    subprocess.run(
                        ["pkill", "-f", "wg-obfuscator"],
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        check=False,
                        timeout=5
                    )
                    # Wait a bit for process to terminate
                    max_attempts = 10
                    for attempt in range(max_attempts):
                        time.sleep(0.2)
                        if not self._is_process_running():
                            break
                    self._cleanup_zombie_processes()
                except Exception as e:
                    logger.warning(f"Failed to stop untracked process: {e}")
            else:
                # Process is tracked and running - nothing to do
                logger.debug("Obfuscator is already running and tracked")
                return
        
        try:
            # Start process with PIPE to capture output
            process = subprocess.Popen(
                ["wg-obfuscator", "-c", WG_OBFUSCATOR_CONFIG_FILE],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Detach from parent process
                universal_newlines=True,
                bufsize=1  # Line buffered
            )
            
            # Start thread to read logs with timestamps
            log_thread = threading.Thread(
                target=self._log_reader_thread,
                args=(process.stdout, process),
                daemon=True
            )
            log_thread.start()
            
            self.process = process
            self._log_thread = log_thread
            logger.info("Started obfuscator")
        except Exception as e:
            logger.error(f"Failed to start obfuscator: {e}")
            raise ServiceError(f"Failed to start wg-obfuscator: {str(e)}")
    
    def restart(self) -> None:
        """Restart wg-obfuscator"""
        logger.info("Restarting obfuscator")
        self.stop()
        # Additional wait after stop to ensure process fully terminated
        time.sleep(0.3)
        # Clear logs on restart (optional)
        self.log_storage.clear()
        self.start()
    
    def _log_reader_thread(self, pipe, process: subprocess.Popen) -> None:
        """
        Thread function to read from process pipe and add timestamps
        
        Args:
            pipe: Process stdout pipe
            process: Process object
        """
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                self.log_storage.add_log(line, add_timestamp=True)
        except Exception as e:
            logger.error(f"Error reading obfuscator logs: {e}")
        finally:
            pipe.close()
            # Check if process exited with error
            if process.poll() is not None and process.poll() != 0:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                error_msg = f"[{timestamp}] ERROR: wg-obfuscator process exited with code {process.poll()}"
                self.log_storage.add_log(error_msg, add_timestamp=False)
    
    def get_version(self) -> Optional[str]:
        """
        Get wg-obfuscator version by running --help command.
        Version is cached for the lifetime of the container.
        
        Returns:
            Version string (e.g., "v1.5 (linux/amd64)") or None if not available
        """
        # Return cached version if available
        if self._cached_version is not None:
            return self._cached_version
        
        # Try to get version (works even if obfuscator is not running)
        try:
            result = subprocess.run(
                ["wg-obfuscator", "--help"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5
            )
            # Version is in first line: "Starting WireGuard Obfuscator v1.5 (linux/amd64)"
            if result.stderr:
                first_line = result.stderr.split('\n')[0]
                # Extract version from "v1.5 (linux/amd64)" pattern
                match = re.search(r'Starting WireGuard Obfuscator (.*)', first_line)
                if match:
                    version = match.group(1).strip('()').split('@')[0].strip()
                    # Cache the version
                    self._cached_version = version
                    logger.debug(f"Cached obfuscator version: {version}")
                    return version
            # Cache None if version couldn't be extracted
            self._cached_version = None
            return None
        except Exception as e:
            logger.debug(f"Failed to get obfuscator version: {e}")
            # Cache None on error
            self._cached_version = None
            return None
    
    def _is_process_running(self) -> bool:
        """
        Check if wg-obfuscator process is actually running (not zombie)
        
        Returns:
            True if process is running (not zombie), False otherwise
        """
        try:
            # Use ps to check for running processes (exclude zombies)
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                check=False,
                timeout=2
            )
            if result.returncode != 0:
                return False
            
            # Check each line for wg-obfuscator
            for line in result.stdout.split('\n'):
                if 'wg-obfuscator' in line and 'grep' not in line:
                    # Check if it's not a zombie (defunct)
                    if '<defunct>' not in line and 'Z' not in line.split()[7:8]:
                        # Found a running (non-zombie) process
                        return True
            
            return False
        except Exception as e:
            logger.debug(f"Failed to check process status: {e}")
            # Fallback to checking our tracked process
            if self.process is not None:
                return_code = self.process.poll()
                return return_code is None  # None means still running
            return False
    
    def _cleanup_zombie_processes(self) -> None:
        """Clean up zombie processes by waiting for them"""
        try:
            # Find all wg-obfuscator processes (including zombies)
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                check=False,
                timeout=2
            )
            if result.returncode != 0:
                return
            
            # Extract PIDs of zombie processes
            for line in result.stdout.split('\n'):
                if 'wg-obfuscator' in line and 'grep' not in line:
                    if '<defunct>' in line or 'Z' in line.split()[7:8]:
                        # Extract PID (second column)
                        parts = line.split()
                        if len(parts) > 1:
                            try:
                                pid = int(parts[1])
                                # Try to wait for zombie process (reaps it)
                                try:
                                    import os
                                    os.waitpid(pid, 0)
                                except (OSError, ChildProcessError):
                                    pass  # Process may have been cleaned up
                            except (ValueError, IndexError):
                                pass
        except Exception as e:
            logger.debug(f"Failed to cleanup zombie processes: {e}")
    
    def status(self, obfuscation_enabled: bool) -> Dict:
        """
        Check if obfuscator process is running
        
        Args:
            obfuscation_enabled: Whether obfuscation is enabled in config
            
        Returns:
            Dictionary with status information
        """
        # Always get version (cached, so no performance impact)
        version = self.get_version()
        
        if not obfuscation_enabled:
            return {
                "enabled": False,
                "running": False,
                "error": "Obfuscation is disabled",
                "version": version
            }
        
        # Check if process is actually running
        is_running = self._is_process_running()
        
        if is_running:
            # Process is running - try to sync our internal state
            if self.process is None or self.process.poll() is not None:
                # Our tracked process is invalid, but actual process is running
                logger.debug("Obfuscator is running but not tracked in this process")
                return {
                    "enabled": True,
                    "running": True,
                    "error": None,
                    "version": version
                }
            else:
                # Process is tracked and running
                return {
                    "enabled": True,
                    "running": True,
                    "error": None,
                    "version": version
                }
        else:
            # Process is not running - check if it exited with error
            exit_code = None
            if self.process is not None:
                exit_code = self.process.poll()
            
            # Try to extract error message from logs
            error_message = self._extract_error_from_logs()
            
            if error_message:
                error_text = error_message
            else:
                if exit_code is not None:
                    error_text = f"Process exited with code {exit_code}"
                else:
                    error_text = "Process not started"
            
            return {
                "enabled": True,
                "running": False,
                "error": error_text,
                "exit_code": exit_code,
                "version": version
            }
    
    def _extract_error_from_logs(self) -> Optional[str]:
        """
        Extract error message from recent logs
        
        Looks for pattern: [main][E] error message
        
        Returns:
            Error message string or None if not found
        """
        # Check last 50 lines for error messages
        recent_logs = self.log_storage.get_logs(50)
        for log_line in reversed(recent_logs):
            # Look for pattern: [main][E] error message
            if "[main][E]" in log_line:
                # Extract error message after [main][E]
                try:
                    parts = log_line.split("[main][E]")
                    if len(parts) > 1:
                        return parts[1].strip()
                except Exception:
                    pass
        return None

