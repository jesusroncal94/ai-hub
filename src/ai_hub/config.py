"""Application configuration."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _get_data_dir() -> Path:
    return Path(os.getenv("AI_HUB_DATA_DIR", ".data")).resolve()


# Model aliases accepted by the Claude Code CLI
AVAILABLE_MODELS: tuple[tuple[str, str], ...] = (
    ("Sonnet", "sonnet"),
    ("Opus", "opus"),
    ("Haiku", "haiku"),
)

# Permission modes for --permission-mode
PERMISSION_MODES: tuple[tuple[str, str], ...] = (
    ("Default", "default"),
    ("Accept Edits", "acceptEdits"),
    ("Bypass All", "bypassPermissions"),
    ("Plan Only", "plan"),
)

# All built-in tools that can be enabled via --allowedTools
ALL_TOOLS: tuple[str, ...] = (
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "Task",
    "NotebookEdit",
)


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    data_dir: Path = field(default_factory=_get_data_dir)
    whisper_model: str = field(
        default_factory=lambda: os.getenv("AI_HUB_WHISPER_MODEL", "base")
    )
    default_model: str = field(
        default_factory=lambda: os.getenv("AI_HUB_DEFAULT_MODEL", "sonnet")
    )
    default_tools: tuple[str, ...] = ("Read",)
    server_host: str = field(
        default_factory=lambda: os.getenv("AI_HUB_HOST", "127.0.0.1")
    )
    server_port: int = field(
        default_factory=lambda: int(os.getenv("AI_HUB_PORT", "7860"))
    )
    max_upload_mb: int = field(
        default_factory=lambda: int(os.getenv("AI_HUB_MAX_UPLOAD_MB", "50"))
    )

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ai_hub.db"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "audit.log"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        # Secure permissions on data directory (owner only)
        self.data_dir.chmod(0o700)


settings = Settings()
