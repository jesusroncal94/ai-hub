# AI Hub

Lightweight multimodal AI chat interface powered by Claude Code.

## Features

- **Authentication** — per-user login with PBKDF2-hashed passwords stored in SQLite
- **Whitelist access control** — only whitelisted users can log in; admin manages the whitelist
- **Admin panel** — create/delete users, manage whitelist, all from the UI
- **Conversation persistence** — messages saved in SQLite (`.data/ai_hub.db`)
- **Multi-conversation UI** — switch between conversations via dropdown, create new ones
- **Text chat** with conversation memory (session continuity via Claude Code `--resume`)
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

On first run:
1. The app seeds an admin user with default credentials: **admin / admin**
2. A login prompt appears at `http://127.0.0.1:7860`
3. Log in with `admin` / `admin`
4. Open the **Admin Panel** (accordion at the bottom) to create more users

## Authentication & Whitelist

All credentials are stored in SQLite with PBKDF2-SHA256 hashed passwords. Access is controlled by a **whitelist** — only whitelisted usernames can log in.

### Why whitelist (not blacklist)?

AI Hub uses your personal Claude Max/Pro subscription. A whitelist (default-deny) ensures only explicitly approved users consume your resources. A blacklist (default-allow) would let anyone register and use your subscription.

### Admin Panel

Admin users see an **Admin Panel** accordion at the bottom of the UI:

| Action | Description |
|--------|-------------|
| **Create User** | Set username, password, and admin flag. Auto-adds to whitelist. |
| **Delete User** | Remove a user account and their whitelist entry. |
| **Add to Whitelist** | Allow a username to log in. |
| **Remove from Whitelist** | Revoke login access without deleting user data. |
| **Refresh tables** | Reload the users and whitelist tables. |

Safeguards:
- Cannot delete yourself
- Cannot remove the last whitelisted admin

## Conversation Management

- Each user has their own conversations stored in SQLite
- The first message in a conversation auto-sets the title (truncated to 50 chars)
- Use the **dropdown** to switch between conversations
- Click **+ New** to start a fresh conversation
- Conversations persist across app restarts

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
├── app.py            # Gradio UI, event handlers, admin panel, and entry point
├── auth.py           # PBKDF2 password hashing and DB-backed authentication
├── config.py         # Application settings
├── database.py       # SQLite persistence (users, whitelist, conversations, messages)
├── providers.py      # AI provider abstraction + Claude Code implementation
└── processors.py     # Voice transcription and document text extraction
```

## How It Works

The application uses `claude -p` (Claude Code CLI in non-interactive mode) as its backend. This means all requests go through your Claude Max/Pro subscription — no separate API billing.

```
User Input (text/files/voice)
        |
        v
   Login (PBKDF2 auth + whitelist check)
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
   Response saved to SQLite + displayed in chat
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
