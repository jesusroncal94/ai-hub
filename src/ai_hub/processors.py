"""Input processors for multimodal support."""

import shutil
from pathlib import Path


def transcribe_audio(audio_path: str, model_name: str = "base") -> str:
    """Transcribe an audio file to text using OpenAI Whisper.

    Requires the 'voice' extra: uv sync --extra voice
    """
    try:
        import whisper
    except ImportError as exc:
        raise ImportError(
            "Voice support requires whisper. "
            "Install with: uv sync --extra voice"
        ) from exc

    model = whisper.load_model(model_name)
    result = model.transcribe(audio_path)
    return result["text"].strip()


def save_upload(file_path: str, upload_dir: Path) -> Path:
    """Copy an uploaded file to the persistent upload directory."""
    source = Path(file_path)
    destination = upload_dir / source.name
    shutil.copy2(source, destination)
    return destination
