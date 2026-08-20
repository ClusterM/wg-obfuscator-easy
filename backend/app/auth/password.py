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

"""Password hashing and verification utilities"""

import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600000
SALT_BYTES = 16
LEGACY_SHA256_LENGTH = 64


def hash_password(password: str) -> str:
    """
    Hash password using PBKDF2-HMAC-SHA256 with a random salt
    
    Args:
        password: Plain text password
        
    Returns:
        Encoded hash in the form algorithm$iterations$salt$hash
    """
    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify password against a stored hash
    
    Supports both the current PBKDF2 format and the legacy unsalted SHA-256
    hashes written by older versions.
    
    Args:
        password: Plain text password to verify
        password_hash: Stored password hash
        
    Returns:
        True if password matches hash, False otherwise
    """
    if not password_hash:
        return False
    
    if is_legacy_hash(password_hash):
        legacy = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(legacy, password_hash)
    
    try:
        algorithm, iterations, salt_hex, digest_hex = password_hash.split("$")
        if algorithm != PBKDF2_ALGORITHM:
            logger.warning(f"Unsupported password hash algorithm: {algorithm}")
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, TypeError) as e:
        logger.warning(f"Malformed stored password hash: {e}")
        return False
    
    return hmac.compare_digest(expected.hex(), digest_hex)


def is_legacy_hash(password_hash: str) -> bool:
    """
    Check whether a stored hash uses the legacy unsalted SHA-256 format
    
    Args:
        password_hash: Stored password hash
        
    Returns:
        True if the hash should be upgraded after a successful verification
    """
    return (
        len(password_hash) == LEGACY_SHA256_LENGTH
        and "$" not in password_hash
        and all(c in "0123456789abcdefABCDEF" for c in password_hash)
    )

