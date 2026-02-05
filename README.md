# AI Hub

Lightweight multimodal AI chat interface powered by Claude Code.

## Features

- **Text chat** with conversation memory (session continuity)
- **File uploads**: images, PDFs, documents, code files
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

Voice input requires OpenAI Whisper, which pulls in PyTorch:

```bash
uv sync --extra voice
```

## Project Structure

```
src/ai_hub/
├── __init__.py       # Package metadata
├── app.py            # Gradio UI and entry point
├── config.py         # Application settings
├── providers.py      # AI provider abstraction + Claude Code implementation
└── processors.py     # Voice transcription and file handling
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
   claude -p --output-format json [--resume session_id]
        |
        v
   Response displayed in chat
```
