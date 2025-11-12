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

"""Database management for SQLite storage"""

import sqlite3
import json
import os
import logging
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager

from .exceptions import ConfigError

logger = logging.getLogger(__name__)

# SQLite database file path
DB_FILE = "/config/wg-easy.db"

# Thread-local storage for database connections (one per thread)
_local = threading.local()


def get_db_connection() -> sqlite3.Connection:
    """Get thread-local database connection"""
    if not hasattr(_local, 'connection') or _local.connection is None:
        _local.connection = sqlite3.connect(
            DB_FILE,
            check_same_thread=False,
            timeout=30.0  # 30 second timeout for locks
        )
        _local.connection.row_factory = sqlite3.Row  # Return rows as dict-like objects
        # Enable WAL mode for better concurrency
        _local.connection.execute("PRAGMA journal_mode=WAL")
        _local.connection.execute("PRAGMA foreign_keys=ON")
    return _local.connection


@contextmanager
def get_db():
    """Context manager for database operations with automatic commit/rollback"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise


def init_database() -> None:
    """Initialize database schema"""
    logger.info("Initializing database schema...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Main configuration table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Clients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                username TEXT PRIMARY KEY,
                ip INTEGER NOT NULL,
                private_key TEXT NOT NULL,
                public_key TEXT NOT NULL,
                allowed_ips TEXT NOT NULL,  -- JSON array
                obfuscator_port INTEGER,
                masking_type_override TEXT,
                verbosity_level TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                latest_handshake INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_in INTEGER NOT NULL
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tokens_created_at 
            ON tokens(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_clients_enabled 
            ON clients(enabled)
        """)
        
        conn.commit()
        logger.info("Database schema initialized successfully")


def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        
        if row is None:
            return default
        
        value_str = row['value']
        # Try to parse as JSON, fallback to string
        try:
            return json.loads(value_str)
        except (json.JSONDecodeError, TypeError):
            return value_str


def set_config_value(key: str, value: Any) -> None:
    """Set configuration value in database"""
    # Convert value to JSON string if it's not a string
    if not isinstance(value, str):
        value_str = json.dumps(value)
    else:
        value_str = value
    
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value_str, now))


def get_metrics_token() -> Optional[str]:
    """Get metrics token from database"""
    token = get_config_value("metrics_token")

    if token:
        token = str(token).strip().replace('\n', '').replace('\r', '').replace(' ', '')
        if token:
            return token
    return None


def set_metrics_token(token: str) -> None:
    """Set metrics token in database"""
    token = token.strip().replace('\n', '').replace('\r', '').replace(' ', '')
    set_config_value("metrics_token", token)


def delete_metrics_token() -> None:
    """Delete metrics token from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config WHERE key = ?", ("metrics_token",))
        cursor.execute("DELETE FROM config WHERE key = ?", ("grafana_token",))


def get_all_config() -> Dict[str, Any]:
    """Get all configuration as dictionary"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM config")
        rows = cursor.fetchall()
        
        config = {}
        for row in rows:
            key = row['key']
            value_str = row['value']
            # Try to parse as JSON, fallback to string
            try:
                config[key] = json.loads(value_str)
            except (json.JSONDecodeError, TypeError):
                config[key] = value_str
        
        return config


def get_client(username: str) -> Optional[Dict[str, Any]]:
    """Get client by username"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM clients WHERE username = ?
        """, (username,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        client = dict(row)
        # Parse JSON fields
        client['ip_full'] = f"{get_config_value("subnet")}.{client['ip']}"
        client['allowed_ips'] = json.loads(client['allowed_ips'])
        client['enabled'] = bool(client['enabled'])
        # latest_handshake is already an integer from DB
        if 'latest_handshake' not in client:
            client['latest_handshake'] = 0
        return client


def get_all_clients() -> Dict[str, Dict[str, Any]]:
    """Get all clients as dictionary"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients")
        rows = cursor.fetchall()
        
        clients = {}
        subnet = get_config_value("subnet")
        for row in rows:
            username = row['username']
            client = dict(row)
            # Parse JSON fields
            client['ip_full'] = f"{subnet}.{client['ip']}"
            client['allowed_ips'] = json.loads(client['allowed_ips'])
            client['enabled'] = bool(client['enabled'])
            # latest_handshake is already an integer from DB
            if 'latest_handshake' not in client:
                client['latest_handshake'] = 0
            clients[username] = client
        
        return clients


def save_client(username: str, client_data: Dict[str, Any]) -> None:
    """Save or update client"""
    allowed_ips_json = json.dumps(client_data.get("allowed_ips", ["0.0.0.0/0"]))
    now = datetime.now().isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check if client exists
        cursor.execute("SELECT username FROM clients WHERE username = ?", (username,))
        exists = cursor.fetchone() is not None
        
        if exists:
            # Update existing client
            # Only update latest_handshake if it's provided and is newer than current
            latest_handshake = client_data.get("latest_handshake")
            if latest_handshake is not None:
                # Get current latest_handshake to compare
                cursor.execute("SELECT latest_handshake FROM clients WHERE username = ?", (username,))
                current_row = cursor.fetchone()
                current_handshake = current_row['latest_handshake'] if current_row else 0
                # Only update if new value is greater (newer)
                if latest_handshake > current_handshake:
                    cursor.execute("""
                        UPDATE clients SET
                            ip = ?, private_key = ?, public_key = ?,
                            allowed_ips = ?, obfuscator_port = ?,
                            masking_type_override = ?, verbosity_level = ?,
                            enabled = ?, latest_handshake = ?, updated_at = ?
                        WHERE username = ?
                    """, (
                        client_data.get("ip"),
                        client_data.get("private_key"),
                        client_data.get("public_key"),
                        allowed_ips_json,
                        client_data.get("obfuscator_port"),
                        client_data.get("masking_type_override"),
                        client_data.get("verbosity_level"),
                        1 if client_data.get("enabled", True) else 0,
                        latest_handshake,
                        now,
                        username
                    ))
                else:
                    # Don't update latest_handshake, use existing SQL
                    cursor.execute("""
                        UPDATE clients SET
                            ip = ?, private_key = ?, public_key = ?,
                            allowed_ips = ?, obfuscator_port = ?,
                            masking_type_override = ?, verbosity_level = ?,
                            enabled = ?, updated_at = ?
                        WHERE username = ?
                    """, (
                        client_data.get("ip"),
                        client_data.get("private_key"),
                        client_data.get("public_key"),
                        allowed_ips_json,
                        client_data.get("obfuscator_port"),
                        client_data.get("masking_type_override"),
                        client_data.get("verbosity_level"),
                        1 if client_data.get("enabled", True) else 0,
                        now,
                        username
                    ))
            else:
                # No latest_handshake provided in client_data, preserve existing value in DB
                # Get current latest_handshake from DB to preserve it
                cursor.execute("SELECT latest_handshake FROM clients WHERE username = ?", (username,))
                current_row = cursor.fetchone()
                existing_handshake = current_row['latest_handshake'] if current_row else 0
                
                cursor.execute("""
                    UPDATE clients SET
                        ip = ?, private_key = ?, public_key = ?,
                        allowed_ips = ?, obfuscator_port = ?,
                        masking_type_override = ?, verbosity_level = ?,
                        enabled = ?, latest_handshake = ?, updated_at = ?
                    WHERE username = ?
                """, (
                    client_data.get("ip"),
                    client_data.get("private_key"),
                    client_data.get("public_key"),
                    allowed_ips_json,
                    client_data.get("obfuscator_port"),
                    client_data.get("masking_type_override"),
                    client_data.get("verbosity_level"),
                    1 if client_data.get("enabled", True) else 0,
                    existing_handshake,  # Preserve existing latest_handshake
                    now,
                    username
                ))
        else:
            # Insert new client
            latest_handshake = client_data.get("latest_handshake", 0)
            cursor.execute("""
                INSERT INTO clients (
                    username, ip, private_key, public_key, allowed_ips,
                    obfuscator_port, masking_type_override, verbosity_level,
                    enabled, latest_handshake, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                username,
                client_data.get("ip"),
                client_data.get("private_key"),
                client_data.get("public_key"),
                allowed_ips_json,
                client_data.get("obfuscator_port"),
                client_data.get("masking_type_override"),
                client_data.get("verbosity_level"),
                1 if client_data.get("enabled", True) else 0,
                latest_handshake,
                now,
                now
            ))


def delete_client(username: str) -> None:
    """Delete client"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE username = ?", (username,))


def client_exists(username: str) -> bool:
    """Check if client exists"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM clients WHERE username = ?", (username,))
        return cursor.fetchone() is not None


def create_token(token: str, created_at: datetime, expires_in: int) -> None:
    """Create token in database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tokens (token, created_at, expires_in)
            VALUES (?, ?, ?)
        """, (token, created_at.isoformat(), expires_in))


def get_token(token: str) -> Optional[Dict[str, Any]]:
    """Get token from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tokens WHERE token = ?
        """, (token,))
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        token_data = dict(row)
        token_data['created_at'] = datetime.fromisoformat(token_data['created_at'])
        return token_data


def delete_token(token: str) -> None:
    """Delete token from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tokens WHERE token = ?", (token,))


def delete_all_tokens() -> None:
    """Delete all tokens from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tokens")


def get_all_tokens() -> Dict[str, Dict[str, Any]]:
    """Get all tokens from database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tokens")
        rows = cursor.fetchall()
        
        tokens = {}
        for row in rows:
            token = row['token']
            token_data = dict(row)
            token_data['created_at'] = datetime.fromisoformat(token_data['created_at'])
            tokens[token] = token_data
        
        return tokens


def cleanup_expired_tokens() -> int:
    """
    Delete expired tokens from database
    
    Returns:
        Number of deleted tokens
    """
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now()
        
        cursor.execute("SELECT token, created_at, expires_in FROM tokens")
        rows = cursor.fetchall()
        
        deleted_count = 0
        for row in rows:
            created_at = datetime.fromisoformat(row['created_at'])
            expires_in = row['expires_in']
            elapsed = (now - created_at).total_seconds()
            
            if elapsed > expires_in:
                cursor.execute("DELETE FROM tokens WHERE token = ?", (row['token'],))
                deleted_count += 1
        
        return deleted_count

