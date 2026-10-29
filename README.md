# AI Hub

Lightweight multimodal AI chat interface powered by Claude Code.

> **Demo:** this is a sample project and is not maintained.

![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue)
![Gradio 6](https://img.shields.io/badge/gradio-6.x-orange)
![License](https://img.shields.io/badge/license-MIT-green)

## Quick Start

```bash
git clone https://github.com/jesusroncal94/ai-hub.git
cd ai-hub
uv sync
uv run ai-hub
```

Open http://127.0.0.1:7860 — Default login: `admin` / `admin`

## Features

| Feature | Description |
|---------|-------------|
| **Multi-conversation** | Create, search, rename, delete conversations |
| **Tags** | Organize and filter conversations by tags |
| **3 UI Layouts** | Focus, Minimal, Productivity — saved per user |
| **File Uploads** | Images, PDF, DOCX, XLSX, CSV, code files |
| **File Downloads** | Auto-detect and download Claude-generated files |
| **Voice Input** | Whisper transcription (optional) |
| **Model Selection** | Switch between Sonnet, Opus, Haiku |
| **Configurable Tools** | Enable/disable Read, Write, Bash, etc. |
| **User Settings** | Per-user preferences persisted to database |
| **Admin Panel** | User management and whitelist control |

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — dependency management
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — installed and authenticated

## Documentation

| Guide | Description |
|-------|-------------|
| [Installation](docs/installation.md) | Setup, dependencies, troubleshooting |
| [User Guide](docs/user-guide.md) | Layouts, conversations, tags, files |
| [Configuration](docs/configuration.md) | Models, tools, permissions, admin |
| [Deployment](docs/deployment.md) | Resources, production, scaling |

## Architecture

```
User Input → Gradio UI → Claude Code CLI → Response
     ↓           ↓              ↓            ↓
  (files)    (SQLite)      (subprocess)   (parsed)
```

```
src/ai_hub/
├── app.py          # Gradio UI and event handlers
├── auth.py         # PBKDF2 authentication
├── config.py       # Settings and constants
├── database.py     # SQLite persistence
├── providers.py    # Claude Code CLI wrapper
└── processors.py   # File and voice processing
```

## License

MIT
