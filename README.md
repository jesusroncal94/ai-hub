# AI Hub

Lightweight multimodal AI chat interface powered by Claude Code.

## Features

- **Authentication** — per-user login with PBKDF2-hashed passwords stored in SQLite
- **Whitelist access control** — only whitelisted users can log in; admin manages the whitelist
- **Admin panel** — create/delete users, manage whitelist, all from the UI
- **Model selection** — switch between Sonnet, Opus, and Haiku on the fly
- **Configurable tools** — enable/disable Claude Code tools (Read, Bash, Edit, WebSearch, etc.)
- **Custom system prompt** — append instructions to Claude's default system prompt
- **Usage metrics** — model used, cost (USD), and token count displayed after each response
- **Conversation persistence** — messages saved in SQLite (`.data/ai_hub.db`)
- **Multi-conversation UI** — switch between conversations via dropdown, create new ones
- **Text chat** with conversation memory (session continuity via Claude Code `--resume`)
- **File uploads** — images (vision), PDFs, Word, Excel, CSV, code files, and plain text
- **Voice input** via microphone (requires optional Whisper dependency)
- **Claude Code backend** — uses your Max/Pro plan subscription (no API key needed)
- **Extensible provider system** — abstract base for adding other AI providers

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated

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

## UI Layout

```
┌──────────────────────────────────────────────┐
│ # AI Hub                                     │
│ [Conversation ▼]  [Model ▼]  [+ New]         │
│ ┌──────────────────────────────────────────┐ │
│ │ Chatbot (height=500)                     │ │
│ └──────────────────────────────────────────┘ │
│ Last response: claude-sonnet... | $0.003 | …  │
│ [Text & Files tab] [Voice tab]               │
│ ┌──────────────────────────────────────────┐ │
│ │ MultimodalTextbox / Audio                │ │
│ └──────────────────────────────────────────┘ │
│ ▶ Settings (tools, system prompt)            │
│ ▶ Admin Panel (admin users only)             │
└──────────────────────────────────────────────┘
```

## Claude CLI Settings

These settings are exposed from the Claude Code CLI and can be changed at any time during a session.

### Model Selection

Use the **Model** dropdown in the top bar to switch between:

| Label | CLI alias | Description |
|-------|-----------|-------------|
| Sonnet | `sonnet` | Balanced performance and cost (default) |
| Opus | `opus` | Most capable, highest cost |
| Haiku | `haiku` | Fastest, lowest cost |

The selected model is passed to the CLI as `--model <alias>`. You can change it between messages, even within the same conversation.

### Allowed Tools

Open the **Settings** accordion to configure which tools Claude can use. Tools are passed to the CLI as `--allowedTools`.

| Tool | Description |
|------|-------------|
| **Read** | Read files from disk (default: enabled) |
| **Write** | Create new files |
| **Edit** | Make string replacements in existing files |
| **Bash** | Execute shell commands |
| **Glob** | Find files by name/pattern |
| **Grep** | Search file contents with regex |
| **WebSearch** | Search the web |
| **WebFetch** | Fetch and analyze web page content |
| **Task** | Launch specialized sub-agents |
| **NotebookEdit** | Edit Jupyter notebook cells |

By default only **Read** is enabled. Enable additional tools as needed.

### System Prompt

The **System prompt** textbox in the Settings accordion lets you append custom instructions to Claude's default system prompt. This is passed as `--append-system-prompt`.

Examples:
- `Always respond in Spanish.`
- `You are a senior Python developer. Prioritize readability.`
- `Keep responses concise, under 200 words.`

### Usage Metrics

After each response, the **Last response** field shows:

```
claude-sonnet-4-5-20250929 | $0.0031 | 150 in → 200 out
```

- **Model**: full model ID used for the response
- **Cost**: estimated cost in USD
- **Tokens**: input and output token counts

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
- Claude Code session IDs are saved per conversation, enabling `--resume` continuity

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

## Supported File Types

| Type | Formats | Processing |
|------|---------|------------|
| Images | PNG, JPG, GIF, WebP, BMP, SVG | Sent to Claude vision via file reference |
| Documents | PDF | Text extracted with pypdf (page by page) |
| Documents | DOCX | Text extracted with python-docx |
| Spreadsheets | XLSX, XLS | Parsed with pandas + openpyxl (all sheets) |
| Data | CSV | Parsed with pandas |
| Text/Code | TXT, MD, JSON, YAML, PY, JS, TS, etc. | Read as plain text |

## Project Structure

```
src/ai_hub/
├── __init__.py       # Package metadata
├── app.py            # Gradio UI, event handlers, admin panel, and entry point
├── auth.py           # PBKDF2 password hashing and DB-backed authentication
├── config.py         # Application settings, available models and tools
├── database.py       # SQLite persistence (users, whitelist, conversations, messages)
├── providers.py      # AI provider abstraction + Claude Code CLI implementation
└── processors.py     # Voice transcription and document text extraction
```

## How It Works

```
User Input (text/files/voice)
        │
        ▼
   Login (PBKDF2 auth + whitelist check)
        │
        ▼
   Gradio UI (localhost:7860)
        │
        ▼
   Pre-processing
   ├── Documents (PDF/DOCX/XLSX/CSV) → text extraction
   ├── Images → file reference (for Claude vision)
   └── Voice → transcription (Whisper)
        │
        ▼
   claude -p --output-format json \
     [--model sonnet|opus|haiku] \
     [--resume session_id] \
     [--allowedTools Read,Bash,...] \
     [--append-system-prompt "..."]
        │
        ▼
   Parse JSON response → extract result, session_id, usage
        │
        ▼
   Response saved to SQLite + displayed in chat
   Usage metrics shown (model, cost, tokens)
```

## Data Storage

All persistent data is stored under `.data/` (git-ignored):

```
.data/
├── ai_hub.db     # SQLite database (users, whitelist, conversations, messages)
└── uploads/      # Uploaded files (images, documents)
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `users` | User accounts (username, password_hash, is_admin) |
| `whitelist` | Usernames allowed to log in |
| `conversations` | Per-user conversations (title, claude_session_id) |
| `messages` | Chat messages (role, content, timestamps) |
