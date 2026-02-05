"""Application configuration."""

from dataclasses import dataclass
from pathlib import Path

_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / ".uploads"


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    upload_dir: Path = _UPLOAD_DIR
    whisper_model: str = "base"
    allowed_tools: tuple[str, ...] = ("Read",)
    server_host: str = "127.0.0.1"
    server_port: int = 7860

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
