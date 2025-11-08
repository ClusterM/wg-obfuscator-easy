import sqlite3
import sys
import hashlib
from datetime import datetime

try:
    password = sys.argv[1]
    if not password:
        print("Error: Password is empty", file=sys.stderr)
        sys.exit(1)

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    now = datetime.now().isoformat()

    db_path = "/config/wg-easy.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Update admin username
        cursor.execute("""
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?
        """, ("admin_username", "admin", now, "admin", now))

        # Update admin password hash
        cursor.execute("""
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?
        """, ("admin_password_hash", password_hash, now, password_hash, now))

        # Delete all tokens
        cursor.execute("DELETE FROM tokens")

        conn.commit()
        conn.close()
        print("Successfully reset admin credentials", file=sys.stdout)

    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
