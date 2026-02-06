"""User authentication with PBKDF2 password hashing."""

from __future__ import annotations

import hashlib
import os
import sys
from typing import TYPE_CHECKING

from ai_hub.security import audit_log, login_limiter

if TYPE_CHECKING:
    from ai_hub.database import Database


def hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        salt_hex, key_hex = password_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
        return key.hex() == key_hex
    except (ValueError, AttributeError):
        return False


def authenticate(username: str, password: str, db: Database) -> bool:
    """Validate credentials against the database and whitelist.

    Includes rate limiting to prevent brute force attacks.
    """
    # Check rate limit first
    if login_limiter.is_blocked(username):
        remaining = login_limiter.get_lockout_remaining(username)
        audit_log("LOGIN_BLOCKED", username, f"Rate limited, {remaining}s remaining")
        return False

    user = db.get_user_by_username(username)
    if user is None:
        login_limiter.record_attempt(username, success=False)
        audit_log("LOGIN_FAILED", username, "User not found")
        return False

    if not verify_password(password, user.password_hash):
        login_limiter.record_attempt(username, success=False)
        remaining = login_limiter.get_remaining_attempts(username)
        audit_log("LOGIN_FAILED", username, f"Invalid password, {remaining} attempts remaining")
        return False

    if not db.is_whitelisted(username):
        audit_log("LOGIN_FAILED", username, "Not whitelisted")
        return False

    # Success - clear rate limit and log
    login_limiter.record_attempt(username, success=True)
    audit_log("LOGIN_SUCCESS", username)
    return True


def seed_admin(db: Database) -> None:
    """Create the initial admin user if no users exist yet.

    Uses AI_HUB_ADMIN_PASSWORD env var, or generates a secure random password.
    """
    if db.get_all_users():
        return

    admin_password = os.getenv("AI_HUB_ADMIN_PASSWORD", "").strip()

    if not admin_password:
        # Generate secure random password
        admin_password = os.urandom(16).hex()
        print("\n" + "=" * 60, file=sys.stderr)
        print("⚠️  SECURITY WARNING: Generated random admin password", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(f"   Username: admin", file=sys.stderr)
        print(f"   Password: {admin_password}", file=sys.stderr)
        print("", file=sys.stderr)
        print("   Save this password! It won't be shown again.", file=sys.stderr)
        print("   For production, set AI_HUB_ADMIN_PASSWORD env var.", file=sys.stderr)
        print("=" * 60 + "\n", file=sys.stderr)

    pw_hash = hash_password(admin_password)
    db.create_user("admin", pw_hash, is_admin=True)
    db.add_to_whitelist("admin")
    audit_log("ADMIN_CREATED", "admin", "Initial admin user created")
