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

"""Traffic statistics collection and storage"""

import time
import threading
import logging
from typing import Dict, Optional, List
from datetime import datetime

from .database import get_db
from .wireguard.stats import WireGuardStats
from .exceptions import ServiceError

logger = logging.getLogger(__name__)


class TrafficStatsCollector:
    """Collects and stores traffic statistics for clients"""
    
    # Retention policy: how long to keep data at different resolutions
    # Format: (retention_seconds, aggregation_interval_seconds, table_name)
    RETENTION_POLICY = [
        (48 * 3600, None, 'client_traffic_stats'),  # 48 hours: raw 5-second data
        (30 * 24 * 3600, 60, 'client_traffic_stats_1m'),  # 30 days: 1-minute aggregated
        (365 * 24 * 3600, 3600, 'client_traffic_stats_1h'),  # 1 year: 1-hour aggregated
    ]
    
    def __init__(self, config_manager, wg_manager, collection_interval: int = 5):
        """
        Initialize traffic statistics collector
        
        Args:
            config_manager: ConfigManager instance
            wg_manager: WireGuardManager instance
            collection_interval: Interval in seconds between collections (default: 5)
        """
        self.config_manager = config_manager
        self.wg_manager = wg_manager
        self.collection_interval = collection_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.aggregation_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        # Store last known values to calculate deltas
        self._last_values: Dict[str, Dict[str, int]] = {}  # {username: {rx: int, tx: int}}
        # Track last aggregation time
        self._last_aggregation_time = int(time.time())
        
    def start(self):
        """Start background collection thread and aggregation thread"""
        if self.running:
            logger.warning("Traffic stats collector is already running")
            return
        
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.thread.start()
        # Start aggregation thread (runs every hour)
        self.aggregation_thread = threading.Thread(target=self._aggregation_loop, daemon=True)
        self.aggregation_thread.start()
        logger.info(f"Traffic stats collector started (interval: {self.collection_interval}s)")
    
    def stop(self):
        """Stop background collection thread and aggregation thread"""
        if not self.running:
            return
        
        self.running = False
        self._stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        if self.aggregation_thread:
            self.aggregation_thread.join(timeout=10)
        logger.info("Traffic stats collector stopped")
    
    def _collection_loop(self):
        """Main collection loop running in background thread"""
        while self.running and not self._stop_event.is_set():
            try:
                self._collect_and_store_stats()
            except Exception as e:
                logger.error(f"Error collecting traffic stats: {e}", exc_info=True)
            
            # Wait for interval or stop event
            if self._stop_event.wait(timeout=self.collection_interval):
                break
    
    def _collect_and_store_stats(self):
        """Collect current stats and store deltas in database"""
        try:
            config = self.config_manager.main
            if not config.get('enabled', True):
                # Skip collection if WireGuard is disabled
                return
            
            wg_status = self.wg_manager.status()
            if not wg_status.get('running', False):
                # Skip if WireGuard is not running
                return
            
            # Get current stats from WireGuard
            stats_collector = WireGuardStats(self.wg_manager.wg_interface)
            clients = self.config_manager.clients
            stats = stats_collector.get_stats(clients)
            
            if not stats or not stats.get('peers'):
                return
            
            # Create map of public_key -> stats
            current_stats: Dict[str, Dict] = {}
            for peer in stats['peers']:
                public_key = peer.get('public_key')
                if public_key and peer.get('client_name'):
                    current_stats[public_key] = {
                        'username': peer['client_name'],
                        'rx': peer.get('transfer_rx_bytes', 0),
                        'tx': peer.get('transfer_tx_bytes', 0)
                    }
            
            # Calculate deltas and store in database
            timestamp = int(time.time())
            records_to_insert = []
            
            for public_key, stats_data in current_stats.items():
                username = stats_data['username']
                current_rx = stats_data['rx']
                current_tx = stats_data['tx']
                
                # Get last known values
                last_values = self._last_values.get(username, {})
                last_rx = last_values.get('rx', 0)
                last_tx = last_values.get('tx', 0)
                
                # Calculate delta (handle counter reset/overflow)
                # If current value is less than last, assume counter reset
                rx_delta = max(0, current_rx - last_rx) if current_rx >= last_rx else current_rx
                tx_delta = max(0, current_tx - last_tx) if current_tx >= last_tx else current_tx
                
                # Only store if there's actual traffic
                if rx_delta > 0 or tx_delta > 0:
                    records_to_insert.append((username, timestamp, rx_delta, tx_delta))
                    
                    # Update all-time counters in clients table
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE clients 
                            SET all_time_rx_bytes = COALESCE(all_time_rx_bytes, 0) + ?,
                                all_time_tx_bytes = COALESCE(all_time_tx_bytes, 0) + ?
                            WHERE username = ?
                            """,
                            (rx_delta, tx_delta, username)
                        )
                        conn.commit()
                
                # Update last known values
                self._last_values[username] = {'rx': current_rx, 'tx': current_tx}
            
            # Batch insert into database
            if records_to_insert:
                with get_db() as conn:
                    cursor = conn.cursor()
                    # Insert delta records (but all-time counters already updated above)
                    cursor.executemany(
                        "INSERT INTO client_traffic_stats (username, timestamp, rx_bytes_delta, tx_bytes_delta) VALUES (?, ?, ?, ?)",
                        records_to_insert
                    )
                    conn.commit()
                    logger.debug(f"Stored traffic stats for {len(records_to_insert)} clients")
        
        except Exception as e:
            logger.error(f"Error in _collect_and_store_stats: {e}", exc_info=True)
    
    def get_traffic_stats(self, username: str, start_time: Optional[int] = None, end_time: Optional[int] = None, aggregation_interval: Optional[int] = None) -> List[Dict]:
        """
        Get traffic statistics for a client from appropriate tables based on time range
        
        Args:
            username: Client username
            start_time: Start timestamp (Unix epoch), if None, gets last hour
            end_time: End timestamp (Unix epoch), if None, uses current time
            aggregation_interval: Aggregation interval in seconds (e.g., 60 for 1 minute, 3600 for 1 hour).
                                  If None, uses best available resolution.
            
        Returns:
            List of dicts with keys: timestamp, rx_bytes_delta, tx_bytes_delta
        """
        if end_time is None:
            end_time = int(time.time())
        if start_time is None:
            start_time = end_time - 3600  # Default to last hour
        
        time_range = end_time - start_time
        current_time = int(time.time())
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Determine which tables to query based on time range and requested aggregation
            # Raw data (5 sec): last 48 hours
            # 1-minute aggregated: 48 hours to 30 days
            # 1-hour aggregated: older than 30 days
            
            results = []
            
            # Query raw data if within 48 hours
            raw_cutoff = current_time - (48 * 3600)
            raw_start = max(start_time, raw_cutoff)
            if raw_start < end_time:
                if aggregation_interval is None:
                    # Return raw data points
                    cursor.execute(
                        """
                        SELECT timestamp, rx_bytes_delta, tx_bytes_delta
                        FROM client_traffic_stats
                        WHERE username = ? AND timestamp >= ? AND timestamp <= ?
                        ORDER BY timestamp ASC
                        """,
                        (username, raw_start, end_time)
                    )
                    results.extend([
                        {
                            'timestamp': row['timestamp'],
                            'rx_bytes_delta': row['rx_bytes_delta'],
                            'tx_bytes_delta': row['tx_bytes_delta']
                        }
                        for row in cursor.fetchall()
                    ])
                elif aggregation_interval >= 60:
                    # Aggregate raw data
                    cursor.execute(
                        """
                        SELECT 
                            ((timestamp / ?) * ?) as bucket_start,
                            SUM(rx_bytes_delta) as rx_bytes_delta,
                            SUM(tx_bytes_delta) as tx_bytes_delta
                        FROM client_traffic_stats
                        WHERE username = ? AND timestamp >= ? AND timestamp <= ?
                        GROUP BY bucket_start
                        ORDER BY bucket_start ASC
                        """,
                        (aggregation_interval, aggregation_interval, username, raw_start, end_time)
                    )
                    results.extend([
                        {
                            'timestamp': int(row['bucket_start']),
                            'rx_bytes_delta': row['rx_bytes_delta'],
                            'tx_bytes_delta': row['tx_bytes_delta']
                        }
                        for row in cursor.fetchall()
                    ])
            
            # Query 1-minute aggregated data if needed (48 hours to 30 days)
            minute_cutoff = current_time - (30 * 24 * 3600)
            if start_time < raw_cutoff:
                minute_start = max(start_time, minute_cutoff)
                minute_end = min(end_time, raw_cutoff)
                
                if minute_start < minute_end:
                    if aggregation_interval is None or aggregation_interval == 60:
                        # Use 1-minute aggregated data as-is
                        cursor.execute(
                            """
                            SELECT timestamp, rx_bytes_delta, tx_bytes_delta
                            FROM client_traffic_stats_1m
                            WHERE username = ? AND timestamp >= ? AND timestamp <= ?
                            ORDER BY timestamp ASC
                            """,
                            (username, minute_start, minute_end)
                        )
                        results.extend([
                            {
                                'timestamp': row['timestamp'],
                                'rx_bytes_delta': row['rx_bytes_delta'],
                                'tx_bytes_delta': row['tx_bytes_delta']
                            }
                            for row in cursor.fetchall()
                        ])
                    elif aggregation_interval > 60:
                        # Aggregate 1-minute data further
                        cursor.execute(
                            """
                            SELECT 
                                ((timestamp / ?) * ?) as bucket_start,
                                SUM(rx_bytes_delta) as rx_bytes_delta,
                                SUM(tx_bytes_delta) as tx_bytes_delta
                            FROM client_traffic_stats_1m
                            WHERE username = ? AND timestamp >= ? AND timestamp <= ?
                            GROUP BY bucket_start
                            ORDER BY bucket_start ASC
                            """,
                            (aggregation_interval, aggregation_interval, username, minute_start, minute_end)
                        )
                        results.extend([
                            {
                                'timestamp': int(row['bucket_start']),
                                'rx_bytes_delta': row['rx_bytes_delta'],
                                'tx_bytes_delta': row['tx_bytes_delta']
                            }
                            for row in cursor.fetchall()
                        ])
            
            # Query 1-hour aggregated data if needed (older than 30 days)
            if start_time < minute_cutoff:
                hour_start = start_time
                hour_end = min(end_time, minute_cutoff)
                
                if hour_start < hour_end:
                    if aggregation_interval is None or aggregation_interval >= 3600:
                        # Use 1-hour aggregated data as-is or aggregate further
                        if aggregation_interval is None or aggregation_interval == 3600:
                            cursor.execute(
                                """
                                SELECT timestamp, rx_bytes_delta, tx_bytes_delta
                                FROM client_traffic_stats_1h
                                WHERE username = ? AND timestamp >= ? AND timestamp <= ?
                                ORDER BY timestamp ASC
                                """,
                                (username, hour_start, hour_end)
                            )
                            results.extend([
                                {
                                    'timestamp': row['timestamp'],
                                    'rx_bytes_delta': row['rx_bytes_delta'],
                                    'tx_bytes_delta': row['tx_bytes_delta']
                                }
                                for row in cursor.fetchall()
                            ])
                        else:
                            # Aggregate further (shouldn't happen often)
                            cursor.execute(
                                """
                                SELECT 
                                    ((timestamp / ?) * ?) as bucket_start,
                                    SUM(rx_bytes_delta) as rx_bytes_delta,
                                    SUM(tx_bytes_delta) as tx_bytes_delta
                                FROM client_traffic_stats_1h
                                WHERE username = ? AND timestamp >= ? AND timestamp <= ?
                                GROUP BY bucket_start
                                ORDER BY bucket_start ASC
                                """,
                                (aggregation_interval, aggregation_interval, username, hour_start, hour_end)
                            )
                            results.extend([
                                {
                                    'timestamp': int(row['bucket_start']),
                                    'rx_bytes_delta': row['rx_bytes_delta'],
                                    'tx_bytes_delta': row['tx_bytes_delta']
                                }
                                for row in cursor.fetchall()
                            ])
            
            # Sort all results by timestamp
            results.sort(key=lambda x: x['timestamp'])
            return results
    
    def get_aggregated_stats(self, username: str, start_time: Optional[int] = None, end_time: Optional[int] = None) -> Dict:
        """
        Get aggregated traffic statistics for a client
        
        Args:
            username: Client username
            start_time: Start timestamp (Unix epoch), if None, gets last hour
            end_time: End timestamp (Unix epoch), if None, uses current time
            
        Returns:
            Dict with keys: total_rx_bytes, total_tx_bytes, total_bytes
        """
        stats = self.get_traffic_stats(username, start_time, end_time)
        
        total_rx = sum(s['rx_bytes_delta'] for s in stats)
        total_tx = sum(s['tx_bytes_delta'] for s in stats)
        
        return {
            'total_rx_bytes': total_rx,
            'total_tx_bytes': total_tx,
            'total_bytes': total_rx + total_tx,
            'start_time': start_time,
            'end_time': end_time,
            'data_points': len(stats)
        }
    
    def get_all_time_stats(self, username: str) -> Dict:
        """
        Get aggregated traffic statistics for a client for all time
        
        Args:
            username: Client username
            
        Returns:
            Dict with keys: total_rx_bytes, total_tx_bytes, total_bytes
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(all_time_rx_bytes, 0) as total_rx, 
                       COALESCE(all_time_tx_bytes, 0) as total_tx
                FROM clients
                WHERE username = ?
                """,
                (username,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {
                    'total_rx_bytes': 0,
                    'total_tx_bytes': 0,
                    'total_bytes': 0
                }
            
            total_rx = row['total_rx'] if row['total_rx'] is not None else 0
            total_tx = row['total_tx'] if row['total_tx'] is not None else 0
            
            return {
                'total_rx_bytes': total_rx,
                'total_tx_bytes': total_tx,
                'total_bytes': total_rx + total_tx
            }
    
    def clear_client_all_time_stats(self, username: str) -> None:
        """
        Clear all-time traffic statistics for a client (reset counters, but keep history)
        
        Args:
            username: Client username
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE clients 
                SET all_time_rx_bytes = 0, all_time_tx_bytes = 0
                WHERE username = ?
                """,
                (username,)
            )
            conn.commit()
    
    def _aggregation_loop(self):
        """Background thread for data aggregation and cleanup"""
        # Wait 1 hour before first aggregation
        if self._stop_event.wait(timeout=3600):
            return
        
        while self.running and not self._stop_event.is_set():
            try:
                self._aggregate_and_cleanup()
                self._last_aggregation_time = int(time.time())
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}", exc_info=True)
            
            # Run aggregation every hour
            if self._stop_event.wait(timeout=3600):
                break
    
    def _aggregate_and_cleanup(self):
        """Aggregate old data and cleanup based on retention policy"""
        current_time = int(time.time())
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Initialize aggregated tables if they don't exist
                self._init_aggregated_tables(cursor)
                
                # Process each retention policy level
                for retention_seconds, aggregation_interval, table_name in self.RETENTION_POLICY:
                    cutoff_time = current_time - retention_seconds
                    
                    if aggregation_interval is None:
                        # This is the raw data table - just delete old data
                        cursor.execute(
                            "DELETE FROM client_traffic_stats WHERE timestamp < ?",
                            (cutoff_time,)
                        )
                        deleted = cursor.rowcount
                        if deleted > 0:
                            logger.info(f"Deleted {deleted} old raw data records (older than {retention_seconds // 3600} hours)")
                    else:
                        # Aggregate data and move to aggregated table
                        self._aggregate_to_table(cursor, cutoff_time, aggregation_interval, table_name)
                
                conn.commit()
                logger.debug("Data aggregation and cleanup completed")
                
        except Exception as e:
            logger.error(f"Error in _aggregate_and_cleanup: {e}", exc_info=True)
    
    def _init_aggregated_tables(self, cursor):
        """Initialize aggregated tables if they don't exist"""
        # 1-minute aggregation table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_traffic_stats_1m (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                rx_bytes_delta INTEGER NOT NULL,
                tx_bytes_delta INTEGER NOT NULL,
                FOREIGN KEY(username) REFERENCES clients(username) ON DELETE CASCADE,
                UNIQUE(username, timestamp)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_traffic_stats_1m_username_timestamp 
            ON client_traffic_stats_1m(username, timestamp)
        """)
        
        # 1-hour aggregation table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS client_traffic_stats_1h (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                rx_bytes_delta INTEGER NOT NULL,
                tx_bytes_delta INTEGER NOT NULL,
                FOREIGN KEY(username) REFERENCES clients(username) ON DELETE CASCADE,
                UNIQUE(username, timestamp)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_traffic_stats_1h_username_timestamp 
            ON client_traffic_stats_1h(username, timestamp)
        """)
    
    def _aggregate_to_table(self, cursor, cutoff_time: int, aggregation_interval: int, target_table: str):
        """Aggregate data from raw table to aggregated table and delete old raw data"""
        # Find all clients with data older than cutoff
        cursor.execute("SELECT DISTINCT username FROM client_traffic_stats WHERE timestamp < ?", (cutoff_time,))
        usernames = [row['username'] for row in cursor.fetchall()]
        
        aggregated_count = 0
        deleted_count = 0
        
        for username in usernames:
            # Aggregate data for this client
            cursor.execute("""
                SELECT 
                    ((timestamp / ?) * ?) as bucket_start,
                    SUM(rx_bytes_delta) as rx_bytes_delta,
                    SUM(tx_bytes_delta) as tx_bytes_delta
                FROM client_traffic_stats
                WHERE username = ? AND timestamp < ?
                GROUP BY bucket_start
            """, (aggregation_interval, aggregation_interval, username, cutoff_time))
            
            aggregated_rows = cursor.fetchall()
            
            # Insert aggregated data (use INSERT OR REPLACE to handle duplicates)
            for row in aggregated_rows:
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {target_table} 
                    (username, timestamp, rx_bytes_delta, tx_bytes_delta)
                    VALUES (?, ?, ?, ?)
                """, (username, int(row['bucket_start']), row['rx_bytes_delta'], row['tx_bytes_delta']))
                aggregated_count += 1
            
            # Delete raw data that was aggregated
            cursor.execute(
                "DELETE FROM client_traffic_stats WHERE username = ? AND timestamp < ?",
                (username, cutoff_time)
            )
            deleted_count += cursor.rowcount
        
        if aggregated_count > 0 or deleted_count > 0:
            logger.info(f"Aggregated {aggregated_count} records to {target_table}, deleted {deleted_count} raw records")

