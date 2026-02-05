# AI Hub

Lightweight multimodal AI chat interface powered by Claude Code.

## Features

- **Text chat** with conversation memory (session continuity)
- **File uploads**: images (vision), PDFs, Word, Excel, CSV, code files, and plain text
- **Voice input** via microphone (requires optional Whisper dependency)
- **Claude Code backend**: uses your Max/Pro plan subscription (no API key needed)
- **Extensible provider system**: abstract base for adding other AI providers

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Claude Code](https://code.claude.com/) installed and authenticated

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jesusroncal94/ai-hub.git
cd ai-hub

# Install dependencies
uv sync

# Run the application
uv run ai-hub
```

The app will be available at `http://127.0.0.1:7860`.

## Voice Support (Optional)

Voice input requires OpenAI Whisper (pulls in PyTorch) and `ffmpeg` for audio processing:

```bash
# Install ffmpeg (system dependency)
# Ubuntu/Debian: sudo apt-get install ffmpeg
# macOS: brew install ffmpeg
# WSL: brew install ffmpeg

# Install Whisper
uv sync --extra voice
```

## Project Structure

```
src/ai_hub/
├── __init__.py       # Package metadata
├── app.py            # Gradio UI and entry point
├── config.py         # Application settings
├── providers.py      # AI provider abstraction + Claude Code implementation
└── processors.py     # Voice transcription and document text extraction
```

## How It Works

The application uses `claude -p` (Claude Code CLI in non-interactive mode) as its backend. This means all requests go through your Claude Max/Pro subscription — no separate API billing.

```
User Input (text/files/voice)
        |
        v
   Gradio UI (localhost:7860)
        |
        v
   Pre-processing
   ├── Documents (PDF/DOCX/XLSX/CSV) → text extraction (pypdf, python-docx, pandas)
   ├── Images → file reference (for Claude vision)
   └── Voice → transcription (Whisper)
        |
        v
   claude -p --output-format json [--resume session_id]
        |
        v
   Response displayed in chat
```

## Supported File Types

| Type | Formats | Processing |
|------|---------|------------|
| Images | PNG, JPG, GIF, WebP, BMP, SVG | Sent to Claude vision via file reference |
| Documents | PDF | Text extracted with pypdf (page by page) |
| Documents | DOCX | Text extracted with python-docx |
| Spreadsheets | XLSX, XLS | Parsed with pandas + openpyxl (all sheets) |
| Data | CSV | Parsed with pandas |
| Text/Code | TXT, MD, JSON, YAML, PY, JS, TS, etc. | Read as plain text |
