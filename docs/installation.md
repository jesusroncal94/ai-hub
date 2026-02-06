# Installation

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.13+ | Required |
| [uv](https://docs.astral.sh/uv/) | Latest | Dependency management |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Latest | Must be installed and authenticated |

## Quick Install

```bash
# Clone the repository
git clone https://github.com/jesusroncal94/ai-hub.git
cd ai-hub

# Install dependencies
uv sync

# Run the application
uv run ai-hub
```

## First Run

1. The app creates an admin user: **admin / admin**
2. Open http://127.0.0.1:7860
3. Log in with `admin` / `admin`
4. Go to **Admin** section to create more users

> **Security:** Change the admin password immediately in a production environment.

## Voice Support (Optional)

Voice input requires OpenAI Whisper and ffmpeg:

### 1. Install ffmpeg (system dependency)

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows (WSL)
sudo apt-get install ffmpeg
```

### 2. Install Whisper

```bash
uv sync --extra voice
```

> **Note:** This adds ~7 GB of dependencies (PyTorch + Whisper models).

## Verify Installation

```bash
# Check the app starts correctly
uv run ai-hub

# Or test the import
uv run python -c "from ai_hub.app import build_app; print('OK')"
```

## Troubleshooting

### Claude Code not found

```
Error: claude: command not found
```

**Solution:** Install and authenticate Claude Code:
```bash
npm install -g @anthropic-ai/claude-code
claude auth
```

### Permission denied on port 7860

```
OSError: [Errno 98] Address already in use
```

**Solution:** Either stop the other process or change the port in `config.py`.

### Whisper model download fails

**Solution:** Ensure you have internet access and sufficient disk space (~1-3 GB per model).

---

[← Back to Documentation](README.md)
