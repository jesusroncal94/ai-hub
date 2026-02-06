# User Guide

## Overview

AI Hub is a multimodal chat interface for Claude. It supports text, file uploads, and voice input.

## UI Layouts

AI Hub offers 3 layouts. Select from **Settings → UI Layout**. Your preference is saved automatically.

### Focus (Default)

Collapsible sidebar with chat as the main focus.

```
┌───────────────────────────────────────────────────────────────┐
│  AI Hub                                      [Hide Menu]      │
├───────────────┬───────────────────────────────────────────────┤
│  SIDEBAR      │  CHAT                                         │
│               │  ┌───────────────────────────────────────────┐│
│ Conversations │  │                                           ││
│  [Select ▼]   │  │           Chat messages                   ││
│  [Filter ▼][+]│  │                                           ││
│  ▶ Search     │  └───────────────────────────────────────────┘│
│  ▶ Manage     │  [Chat tab] [Voice tab]                       │
│               │  ┌───────────────────────────────────────────┐│
│ ▶ Tags        │  │ Type a message or attach files...    Send ││
│ ▶ Settings    │  └───────────────────────────────────────────┘│
│ ▶ Admin       │  claude-sonnet | $0.003 | 150 in → 200 out    │
└───────────────┴───────────────────────────────────────────────┘
```

### Minimal

ChatGPT-style with controls in the header bar.

```
┌───────────────────────────────────────────────────────────────┐
│  AI Hub     [Conversation ▼] [Model ▼] [+]     [Hide Menu]    │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│                       Chat messages                           │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ Type a message or attach files...               Send  │   │
│  └───────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

### Productivity

Tags accordion open by default for quick navigation.

```
┌───────────────────────────────────────────────────────────────┐
│  AI Hub                                      [Hide Menu]      │
├───────────────┬───────────────────────────────────────────────┤
│ Conversations │  CHAT                                         │
│  [Select ▼]   │                                               │
│               │                                               │
│ ▼ Tags        │                                               │
│   [work]      │                                               │
│   [research]  │                                               │
│   [personal]  │                                               │
│               │                                               │
│ ▶ Settings    │                                               │
└───────────────┴───────────────────────────────────────────────┘
```

---

## Conversations

### Creating a Conversation

- Click **+ New** to start a fresh conversation
- The first message automatically sets the title (max 50 chars)

### Switching Conversations

- Use the **Conversation** dropdown to switch
- History and Claude session are restored automatically

### Searching

1. Open **Search** accordion
2. Enter a query (searches titles and message content)
3. Results show title, date, and ID

### Renaming

1. Open **Manage** accordion
2. Select a conversation from the dropdown
3. Enter a new title and click **OK**

### Deleting

1. Open **Manage** accordion
2. Select a conversation
3. Click **Delete**

> If you delete the active conversation, the app switches to the most recent one.

---

## Tags

Organize conversations with tags (e.g., "work", "personal", "research").

### Create a Tag

1. Open **Tags** accordion
2. Enter a name and click **+**

### Assign to Conversation

1. In **Tags** accordion, select a conversation
2. Select a tag
3. Click **Assign**

### Filter by Tag

- Use the **Filter** dropdown next to conversations
- Select a tag to show only tagged conversations
- Select "All" to show everything

### Delete a Tag

1. Select the tag in the delete dropdown
2. Click **Delete Tag**

> Deleting a tag removes it from all conversations.

---

## File Handling

### Uploading Files

Attach files using the input area. Supported types:

| Type | Formats | How it's processed |
|------|---------|-------------------|
| Images | PNG, JPG, GIF, WebP, BMP, SVG | Sent to Claude vision |
| Documents | PDF | Text extracted page-by-page |
| Documents | DOCX | Text extracted |
| Spreadsheets | XLSX, XLS | All sheets parsed |
| Data | CSV | Parsed as table |
| Text/Code | TXT, MD, JSON, PY, JS, TS, etc. | Read as plain text |

### Downloading Generated Files

When Claude creates or modifies files, a **Generated Files** section appears with download links.

---

## Voice Input

> Requires [optional voice dependencies](installation.md#voice-support-optional).

1. Go to the **Voice** tab
2. Click the microphone to record
3. Click **Send Voice**
4. Audio is transcribed and sent to Claude

---

## Usage Metrics

After each response, you'll see:

```
claude-sonnet-4-5-20250929 | $0.0031 | 150 in → 200 out
```

- **Model**: Full model ID used
- **Cost**: Estimated cost in USD
- **Tokens**: Input → Output token counts

---

[← Back to Documentation](README.md)
