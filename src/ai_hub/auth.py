"""User authentication with PBKDF2 password hashing."""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_hub.database import Database


def hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its stored hash."""
    salt_hex, key_hex = password_hash.split(":")
    salt = bytes.fromhex(salt_hex)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return key.hex() == key_hex


def authenticate(username: str, password: str, db: Database) -> bool:
    """Validate credentials against the database and whitelist."""
    user = db.get_user_by_username(username)
    if user is None:
        return False
    if not verify_password(password, user.password_hash):
        return False
    if not db.is_whitelisted(username):
        return False
    return True


def seed_admin(db: Database) -> None:
    """Create the initial admin user if no users exist yet.

    Default credentials: admin / admin
    """
    if db.get_all_users():
        return
    pw_hash = hash_password("admin")
    db.create_user("admin", pw_hash, is_admin=True)
    db.add_to_whitelist("admin")
