"""Security utilities: rate limiting and audit logging."""

import logging
import os
from collections import defaultdict
from pathlib import Path
from time import time

from ai_hub.config import settings


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Simple in-memory rate limiter for login attempts."""

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        lockout_seconds: int = 900,
    ):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self.lockout = lockout_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)
        self.lockouts: dict[str, float] = {}

    def _cleanup(self, key: str) -> None:
        """Remove expired attempts."""
        now = time()
        self.attempts[key] = [t for t in self.attempts[key] if now - t < self.window]

    def is_blocked(self, key: str) -> bool:
        """Check if the key is currently blocked."""
        now = time()

        # Check lockout
        if key in self.lockouts:
            if now < self.lockouts[key]:
                return True
            del self.lockouts[key]

        self._cleanup(key)
        return len(self.attempts[key]) >= self.max_attempts

    def record_attempt(self, key: str, success: bool = False) -> None:
        """Record a login attempt."""
        if success:
            # Clear attempts on successful login
            self.attempts.pop(key, None)
            self.lockouts.pop(key, None)
            return

        self._cleanup(key)
        self.attempts[key].append(time())

        # Trigger lockout if max attempts reached
        if len(self.attempts[key]) >= self.max_attempts:
            self.lockouts[key] = time() + self.lockout
            audit_log("LOCKOUT", key, f"Too many failed attempts, locked for {self.lockout}s")

    def get_remaining_attempts(self, key: str) -> int:
        """Get remaining attempts before lockout."""
        self._cleanup(key)
        return max(0, self.max_attempts - len(self.attempts[key]))

    def get_lockout_remaining(self, key: str) -> int:
        """Get seconds remaining in lockout, or 0 if not locked."""
        if key not in self.lockouts:
            return 0
        remaining = self.lockouts[key] - time()
        return max(0, int(remaining))


# Global rate limiter instance
login_limiter = RateLimiter(
    max_attempts=int(os.getenv("AI_HUB_MAX_LOGIN_ATTEMPTS", "5")),
    window_seconds=int(os.getenv("AI_HUB_LOGIN_WINDOW_SECONDS", "300")),
    lockout_seconds=int(os.getenv("AI_HUB_LOCKOUT_SECONDS", "900")),
)


# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------


_audit_logger: logging.Logger | None = None


def _get_audit_logger() -> logging.Logger:
    """Get or create the audit logger."""
    global _audit_logger

    if _audit_logger is not None:
        return _audit_logger

    settings.ensure_dirs()

    _audit_logger = logging.getLogger("ai_hub.audit")
    _audit_logger.setLevel(logging.INFO)

    # Prevent duplicate handlers
    if not _audit_logger.handlers:
        handler = logging.FileHandler(settings.log_path)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        _audit_logger.addHandler(handler)

    return _audit_logger


def audit_log(event: str, user: str, details: str = "") -> None:
    """Log a security-relevant event."""
    logger = _get_audit_logger()
    message = f"[{event}] user={user}"
    if details:
        message += f" | {details}"
    logger.info(message)


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------


def validate_username(username: str) -> tuple[bool, str]:
    """Validate username format."""
    if not username:
        return False, "Username is required"
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(username) > 50:
        return False, "Username must be at most 50 characters"
    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Username can only contain letters, numbers, underscores, and hyphens"
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength."""
    if not password:
        return False, "Password is required"
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if len(password) > 128:
        return False, "Password must be at most 128 characters"
    return True, ""
