import aiosqlite
import bcrypt
import hashlib
from pathlib import Path
from app.config import get_settings
from app.crypto import encrypt_private_key, decrypt_private_key

settings = get_settings()


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token using bcrypt.

    Args:
        token: The plaintext refresh token.

    Returns:
        The bcrypt hash as a string.
    """
    # Use SHA256 to reduce token to fixed size before bcrypt (bcrypt has 72 byte limit)
    token_hash = hashlib.sha256(token.encode()).digest()
    return bcrypt.hashpw(token_hash, bcrypt.gensalt()).decode()


def verify_refresh_token(token: str, hashed: str) -> bool:
    """Verify a refresh token against its stored hash.

    Args:
        token: The plaintext refresh token to verify.
        hashed: The stored bcrypt hash.

    Returns:
        True if the token matches the hash, False otherwise.
    """
    try:
        # Use SHA256 to reduce token to fixed size before bcrypt (bcrypt has 72 byte limit)
        token_hash = hashlib.sha256(token.encode()).digest()
        return bcrypt.checkpw(token_hash, hashed.encode())
    except Exception:
        return False

# Extract path from SQLite URL
DB_PATH = settings.database_url.replace("sqlite+aiosqlite:///", "")
if settings.database_url.startswith("sqlite+aiosqlite:////"):
    # Handle absolute path (4 slashes) -> /path/to/db
    DB_PATH = "/" + settings.database_url.split("sqlite+aiosqlite:////")[1]



async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


async def init_db():
    """Initialize database tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Peer metadata table (stores friendly names and other metadata)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS peer_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interface_name TEXT NOT NULL,
                public_key TEXT NOT NULL,
                name TEXT NOT NULL,
                private_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(interface_name, public_key)
            )
        """)

        # Audit log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Refresh tokens table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Settings table (for runtime-editable settings)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


async def get_user_by_username(username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_user(username: str, hashed_password: str, is_admin: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (username, hashed_password, is_admin) VALUES (?, ?, ?)",
            (username, hashed_password, is_admin),
        )
        await db.commit()


async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def save_peer_metadata(interface_name: str, public_key: str, name: str, private_key: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        # Encrypt private key before storing
        encrypted_key = encrypt_private_key(private_key) if private_key else None

        await db.execute(
            """INSERT OR REPLACE INTO peer_metadata
               (interface_name, public_key, name, private_key)
               VALUES (?, ?, ?, ?)""",
            (interface_name, public_key, name, encrypted_key),
        )
        await db.commit()


async def get_peer_metadata(interface_name: str, public_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM peer_metadata WHERE interface_name = ? AND public_key = ?",
            (interface_name, public_key),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            metadata = dict(row)
            # Decrypt private key if present
            if metadata.get("private_key"):
                metadata["private_key"] = decrypt_private_key(metadata["private_key"])
            return metadata


async def get_all_peer_metadata(interface_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM peer_metadata WHERE interface_name = ?",
            (interface_name,),
        ) as cursor:
            rows = await cursor.fetchall()
            metadata_list = []
            for row in rows:
                metadata = dict(row)
                # Decrypt private key if present
                if metadata.get("private_key"):
                    metadata["private_key"] = decrypt_private_key(metadata["private_key"])
                metadata_list.append(metadata)
            return metadata_list


async def delete_peer_metadata(interface_name: str, public_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM peer_metadata WHERE interface_name = ? AND public_key = ?",
            (interface_name, public_key),
        )
        await db.commit()


async def add_audit_log(user_id: int, action: str, details: str = None, ip_address: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO audit_logs (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
            (user_id, action, details, ip_address),
        )
        await db.commit()


async def update_user_password(user_id: int, hashed_password: str):
    """Update user's password."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET hashed_password = ? WHERE id = ?",
            (hashed_password, user_id),
        )
        await db.commit()


async def save_refresh_token(user_id: int, token: str, expires_at: str):
    """Save a refresh token to the database (stores bcrypt hash, not plaintext)."""
    token_hash = hash_refresh_token(token)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO refresh_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token_hash, expires_at),
        )
        await db.commit()


async def get_refresh_token(token: str):
    """Get refresh token data by verifying the provided token against stored hashes.

    Args:
        token: The plaintext refresh token to verify.

    Returns:
        Token data dict if valid, None otherwise.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Get all tokens for this user (should be few)
        # We need to check all because we can't query by hash
        async with db.execute("SELECT * FROM refresh_tokens") as cursor:
            async for row in cursor:
                row_dict = dict(row)
                # Verify the token against this hash
                if verify_refresh_token(token, row_dict["token"]):
                    return row_dict
            return None


async def delete_refresh_token(token: str):
    """Delete a refresh token from the database.

    Args:
        token: The plaintext refresh token to delete.
    """
    # First find the token by verifying hashes
    token_data = await get_refresh_token(token)
    if token_data:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM refresh_tokens WHERE id = ?", (token_data["id"],)
            )
            await db.commit()


async def delete_expired_tokens():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM refresh_tokens WHERE expires_at < datetime('now')"
        )
        await db.commit()


async def delete_all_refresh_tokens_for_user(user_id: int):
    """Delete all refresh tokens for a specific user.

    This should be called when:
    - User changes their password
    - User explicitly logs out from all sessions
    - Account security events require session revocation

    Args:
        user_id: The user ID whose tokens should be deleted.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_setting(key: str):
    """Get a setting value by key."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else None


async def get_all_settings():
    """Get all settings as a dictionary."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT key, value FROM settings") as cursor:
            rows = await cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}


async def set_setting(key: str, value: str):
    """Set or update a setting value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))""",
            (key, value),
        )
        await db.commit()
