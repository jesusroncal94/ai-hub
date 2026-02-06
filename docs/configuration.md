# Configuration

All settings are **persisted per user**. Click **Save Settings** to store your preferences.

## Model Selection

Select a model from the **Model** dropdown in Settings.

| Label | CLI Alias | Description |
|-------|-----------|-------------|
| Sonnet | `sonnet` | Balanced performance and cost (default) |
| Opus | `opus` | Most capable, highest cost |
| Haiku | `haiku` | Fastest, lowest cost |

You can change models between messages, even in the same conversation.

---

## Allowed Tools

Configure which tools Claude can use. Open **Settings → Tools**.

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

> **Default:** Only **Read** is enabled. Enable additional tools as needed.

---

## Permission Mode

Controls how Claude handles tool permissions.

| Mode | CLI Value | Description |
|------|-----------|-------------|
| Default | `default` | Asks for permission before using tools |
| Accept Edits | `acceptEdits` | Auto-accept file edits, ask for others |
| Bypass All | `bypassPermissions` | Skip all permission prompts ⚠️ |
| Plan Only | `plan` | Claude can only plan, not execute |

> **Warning:** "Bypass All" should only be used in trusted environments.

---

## System Prompt

Append custom instructions to Claude's default system prompt.

**Examples:**

```
Always respond in Spanish.
```

```
You are a senior Python developer. Prioritize readability and type hints.
```

```
Keep responses concise, under 200 words.
```

---

## Additional Directories

Add directories for Claude to access (one per line):

```
/home/user/projects/my-project
/var/www/html
```

---

## Admin Panel

Only visible to admin users.

### User Management

| Action | Description |
|--------|-------------|
| **Create User** | Username, password, admin flag. Auto-whitelists. |
| **Delete User** | Removes user and whitelist entry. |

### Whitelist Management

| Action | Description |
|--------|-------------|
| **Add to Whitelist** | Allow a username to log in |
| **Remove from Whitelist** | Revoke login access (keeps user data) |
| **Refresh tables** | Reload the display |

### Safeguards

- Cannot delete yourself
- Cannot remove the last whitelisted admin

---

## Authentication

### Password Security

- Passwords are hashed with PBKDF2-SHA256
- Stored in SQLite (`users.password_hash`)

### Whitelist System

AI Hub uses a **whitelist** (default-deny) because:

- It uses your Claude Max/Pro subscription
- Only explicitly approved users can consume resources
- Prevents unauthorized access

---

## Data Storage

All data is stored in `.data/` (git-ignored):

```
.data/
├── ai_hub.db     # SQLite database
└── uploads/      # Uploaded files
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `users` | User accounts |
| `whitelist` | Allowed usernames |
| `conversations` | Per-user conversations |
| `messages` | Chat messages |
| `tags` | Per-user tags |
| `conversation_tags` | Tag assignments |
| `user_settings` | Per-user preferences |

---

[← Back to Documentation](README.md)
