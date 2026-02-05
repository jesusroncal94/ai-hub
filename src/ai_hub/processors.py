"""Input processors for multimodal support."""

import shutil
from pathlib import Path

import pandas as pd
from docx import Document
from pypdf import PdfReader

_TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".json", ".yaml", ".yml", ".toml",
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".go", ".rs", ".rb", ".php",
    ".html", ".css", ".scss", ".xml",
    ".sh", ".bash", ".zsh",
    ".sql", ".log", ".ini", ".cfg", ".conf",
})

_IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico",
})


def extract_text(file_path: Path) -> str | None:
    """Extract text content from a file.

    Returns the extracted text for documents, or None for image files
    (which should be sent as file references for vision processing).
    """
    suffix = file_path.suffix.lower()

    if suffix in _IMAGE_EXTENSIONS:
        return None

    if suffix == ".pdf":
        return _extract_pdf(file_path)

    if suffix == ".docx":
        return _extract_docx(file_path)

    if suffix in (".xlsx", ".xls"):
        return _extract_excel(file_path)

    if suffix == ".csv":
        return _extract_csv(file_path)

    if suffix in _TEXT_EXTENSIONS:
        return file_path.read_text(encoding="utf-8", errors="replace")

    # Unknown format: try reading as text
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _extract_pdf(file_path: Path) -> str:
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {i}]\n{text}")
    return "\n\n".join(pages) if pages else "(Empty PDF)"


def _extract_docx(file_path: Path) -> str:
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs) if paragraphs else "(Empty document)"


def _extract_excel(file_path: Path) -> str:
    sheets = pd.read_excel(file_path, sheet_name=None)
    parts = []
    for name, df in sheets.items():
        parts.append(f"[Sheet: {name}]\n{df.to_string(index=False)}")
    return "\n\n".join(parts) if parts else "(Empty spreadsheet)"


def _extract_csv(file_path: Path) -> str:
    df = pd.read_csv(file_path)
    return df.to_string(index=False) if not df.empty else "(Empty CSV)"


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
