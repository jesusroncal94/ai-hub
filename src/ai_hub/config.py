"""Application configuration."""

from dataclasses import dataclass
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / ".data"

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


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    data_dir: Path = _DATA_DIR
    whisper_model: str = "base"
    default_model: str = "sonnet"
    default_tools: tuple[str, ...] = ("Read",)
    server_host: str = "127.0.0.1"
    server_port: int = 7860

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ai_hub.db"

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
