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

"""In-memory log storage for obfuscator"""

import threading
from collections import deque
from datetime import datetime
from typing import List

import logging

logger = logging.getLogger(__name__)


class ObfuscatorLogs:
    """Thread-safe in-memory log storage for obfuscator output"""
    
    def __init__(self, max_size: int = 10000):
        self.logs: deque = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.max_size = max_size
    
    def add_log(self, line: str, add_timestamp: bool = True) -> None:
        """
        Add a log line to storage
        
        Args:
            line: Log line to add
            add_timestamp: Whether to add timestamp prefix
        """
        with self.lock:
            if add_timestamp:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_entry = f"[{timestamp}] {line.rstrip()}"
            else:
                log_entry = line.rstrip()
            
            self.logs.append(log_entry)
            logger.debug(f"Added log entry (total: {len(self.logs)})")
    
    def get_logs(self, n_lines: int = 100) -> List[str]:
        """
        Get last N lines from log storage
        
        Args:
            n_lines: Number of lines to retrieve
            
        Returns:
            List of log lines
        """
        with self.lock:
            total_lines = len(self.logs)
            if total_lines == 0:
                return []
            
            if total_lines > n_lines:
                return list(self.logs)[-n_lines:]
            else:
                return list(self.logs)
    
    def clear(self) -> None:
        """Clear all logs"""
        with self.lock:
            self.logs.clear()
            logger.info("Cleared obfuscator logs")
    
    def __len__(self) -> int:
        """Get total number of log lines"""
        with self.lock:
            return len(self.logs)

