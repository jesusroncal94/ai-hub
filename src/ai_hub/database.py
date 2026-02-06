"""SQLite conversation persistence."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    is_admin: bool
    created_at: str


@dataclass
class WhitelistEntry:
    id: int
    username: str
    created_at: str


@dataclass
class Message:
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: str


@dataclass
class Conversation:
    id: int
    user_id: int
    title: str
    claude_session_id: str | None
    created_at: str
    updated_at: str


@dataclass
class Tag:
    id: int
    user_id: int
    name: str
    created_at: str


@dataclass
class UserSettings:
    user_id: int
    model: str
    tools: str  # comma-separated
    permission_mode: str
    system_prompt: str
    add_dirs: str
    ui_layout: str  # 'minimal', 'productivity', 'focus'
    updated_at: str


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS whitelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL DEFAULT 'New conversation',
    claude_session_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);
CREATE TABLE IF NOT EXISTS conversation_tags (
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (conversation_id, tag_id)
);
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    model TEXT NOT NULL DEFAULT 'sonnet',
    tools TEXT NOT NULL DEFAULT 'Read',
    permission_mode TEXT NOT NULL DEFAULT 'default',
    system_prompt TEXT NOT NULL DEFAULT '',
    add_dirs TEXT NOT NULL DEFAULT '',
    ui_layout TEXT NOT NULL DEFAULT 'focus',
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


class Database:
    """Thin wrapper around SQLite for conversation storage."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add columns/tables that may be missing from older schema versions."""
        migrations = [
            "ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE user_settings ADD COLUMN ui_layout TEXT NOT NULL DEFAULT 'focus'",
        ]
        for sql in migrations:
            try:
                self._conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists

    # -- users ---------------------------------------------------------------

    def create_user(
        self,
        username: str,
        password_hash: str,
        *,
        is_admin: bool = False,
    ) -> User:
        self._conn.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
            (username, password_hash, int(is_admin)),
        )
        self._conn.commit()
        return self.get_user_by_username(username)  # type: ignore[return-value]

    def get_user_by_username(self, username: str) -> User | None:
        cur = self._conn.execute(
            "SELECT id, username, password_hash, is_admin, created_at "
            "FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return User(
            id=row[0],
            username=row[1],
            password_hash=row[2],
            is_admin=bool(row[3]),
            created_at=row[4],
        )

    def get_all_users(self) -> list[User]:
        cur = self._conn.execute(
            "SELECT id, username, password_hash, is_admin, created_at "
            "FROM users ORDER BY id"
        )
        return [
            User(
                id=r[0],
                username=r[1],
                password_hash=r[2],
                is_admin=bool(r[3]),
                created_at=r[4],
            )
            for r in cur.fetchall()
        ]

    def delete_user(self, user_id: int) -> None:
        self._conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self._conn.commit()

    # -- whitelist -----------------------------------------------------------

    def add_to_whitelist(self, username: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO whitelist (username) VALUES (?)",
            (username,),
        )
        self._conn.commit()

    def remove_from_whitelist(self, username: str) -> None:
        self._conn.execute(
            "DELETE FROM whitelist WHERE username = ?", (username,)
        )
        self._conn.commit()

    def is_whitelisted(self, username: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM whitelist WHERE username = ?", (username,)
        )
        return cur.fetchone() is not None

    def get_whitelist(self) -> list[WhitelistEntry]:
        cur = self._conn.execute(
            "SELECT id, username, created_at FROM whitelist ORDER BY id"
        )
        return [WhitelistEntry(*row) for row in cur.fetchall()]

    # -- conversations -------------------------------------------------------

    def create_conversation(
        self, user_id: int, title: str = "New conversation"
    ) -> Conversation:
        cur = self._conn.execute(
            "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        self._conn.commit()
        return self.get_conversation(cur.lastrowid)  # type: ignore[arg-type, return-value]

    def get_conversations(self, user_id: int) -> list[Conversation]:
        cur = self._conn.execute(
            "SELECT id, user_id, title, claude_session_id, created_at, updated_at "
            "FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        return [Conversation(*row) for row in cur.fetchall()]

    def get_conversation(self, conversation_id: int) -> Conversation | None:
        cur = self._conn.execute(
            "SELECT id, user_id, title, claude_session_id, created_at, updated_at "
            "FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        row = cur.fetchone()
        return Conversation(*row) if row else None

    def update_conversation(
        self,
        conversation_id: int,
        *,
        title: str | None = None,
        claude_session_id: str | None = None,
    ) -> None:
        if title is not None:
            self._conn.execute(
                "UPDATE conversations SET title = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (title, conversation_id),
            )
        if claude_session_id is not None:
            self._conn.execute(
                "UPDATE conversations SET claude_session_id = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (claude_session_id, conversation_id),
            )
        self._conn.commit()

    def delete_conversation(self, conversation_id: int) -> None:
        self._conn.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
        self._conn.commit()

    # -- messages ------------------------------------------------------------

    def add_message(
        self, conversation_id: int, role: str, content: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )
        self._conn.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        self._conn.commit()

    def get_messages(self, conversation_id: int) -> list[Message]:
        cur = self._conn.execute(
            "SELECT id, conversation_id, role, content, created_at "
            "FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        )
        return [Message(*row) for row in cur.fetchall()]

    # -- tags ----------------------------------------------------------------

    def create_tag(self, user_id: int, name: str) -> Tag:
        self._conn.execute(
            "INSERT INTO tags (user_id, name) VALUES (?, ?)",
            (user_id, name),
        )
        self._conn.commit()
        cur = self._conn.execute(
            "SELECT id, user_id, name, created_at FROM tags "
            "WHERE user_id = ? AND name = ?",
            (user_id, name),
        )
        return Tag(*cur.fetchone())

    def get_tag(self, tag_id: int) -> Tag | None:
        cur = self._conn.execute(
            "SELECT id, user_id, name, created_at FROM tags WHERE id = ?",
            (tag_id,),
        )
        row = cur.fetchone()
        return Tag(*row) if row else None

    def get_tags(self, user_id: int) -> list[Tag]:
        cur = self._conn.execute(
            "SELECT id, user_id, name, created_at FROM tags "
            "WHERE user_id = ? ORDER BY name",
            (user_id,),
        )
        return [Tag(*row) for row in cur.fetchall()]

    def rename_tag(self, tag_id: int, new_name: str) -> None:
        self._conn.execute(
            "UPDATE tags SET name = ? WHERE id = ?", (new_name, tag_id)
        )
        self._conn.commit()

    def delete_tag(self, tag_id: int) -> None:
        self._conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self._conn.commit()

    def add_tag_to_conversation(self, conv_id: int, tag_id: int) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO conversation_tags (conversation_id, tag_id) "
            "VALUES (?, ?)",
            (conv_id, tag_id),
        )
        self._conn.commit()

    def remove_tag_from_conversation(self, conv_id: int, tag_id: int) -> None:
        self._conn.execute(
            "DELETE FROM conversation_tags "
            "WHERE conversation_id = ? AND tag_id = ?",
            (conv_id, tag_id),
        )
        self._conn.commit()

    def get_conversation_tags(self, conv_id: int) -> list[Tag]:
        cur = self._conn.execute(
            "SELECT t.id, t.user_id, t.name, t.created_at "
            "FROM tags t JOIN conversation_tags ct ON t.id = ct.tag_id "
            "WHERE ct.conversation_id = ? ORDER BY t.name",
            (conv_id,),
        )
        return [Tag(*row) for row in cur.fetchall()]

    def get_conversations_by_tag(
        self, user_id: int, tag_id: int
    ) -> list[Conversation]:
        cur = self._conn.execute(
            "SELECT c.id, c.user_id, c.title, c.claude_session_id, "
            "c.created_at, c.updated_at "
            "FROM conversations c "
            "JOIN conversation_tags ct ON c.id = ct.conversation_id "
            "WHERE c.user_id = ? AND ct.tag_id = ? "
            "ORDER BY c.updated_at DESC",
            (user_id, tag_id),
        )
        return [Conversation(*row) for row in cur.fetchall()]

    def search_conversations(
        self, user_id: int, query: str
    ) -> list[Conversation]:
        pattern = f"%{query}%"
        cur = self._conn.execute(
            "SELECT DISTINCT c.id, c.user_id, c.title, c.claude_session_id, "
            "c.created_at, c.updated_at "
            "FROM conversations c "
            "LEFT JOIN messages m ON c.id = m.conversation_id "
            "WHERE c.user_id = ? AND (c.title LIKE ? OR m.content LIKE ?) "
            "ORDER BY c.updated_at DESC",
            (user_id, pattern, pattern),
        )
        return [Conversation(*row) for row in cur.fetchall()]

    # -- user settings -------------------------------------------------------

    def get_user_settings(self, user_id: int) -> UserSettings | None:
        cur = self._conn.execute(
            "SELECT user_id, model, tools, permission_mode, system_prompt, "
            "add_dirs, ui_layout, updated_at FROM user_settings WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return UserSettings(*row) if row else None

    def save_user_settings(
        self,
        user_id: int,
        *,
        model: str,
        tools: list[str],
        permission_mode: str,
        system_prompt: str,
        add_dirs: str,
        ui_layout: str = "focus",
    ) -> UserSettings:
        tools_str = ",".join(tools)
        self._conn.execute(
            """
            INSERT INTO user_settings
                (user_id, model, tools, permission_mode, system_prompt, add_dirs, ui_layout)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                model = excluded.model,
                tools = excluded.tools,
                permission_mode = excluded.permission_mode,
                system_prompt = excluded.system_prompt,
                add_dirs = excluded.add_dirs,
                ui_layout = excluded.ui_layout,
                updated_at = datetime('now')
            """,
            (user_id, model, tools_str, permission_mode, system_prompt, add_dirs, ui_layout),
        )
        self._conn.commit()
        return self.get_user_settings(user_id)  # type: ignore[return-value]

    def get_user_layout(self, user_id: int) -> str:
        """Get user's preferred UI layout. Returns 'focus' as default."""
        cur = self._conn.execute(
            "SELECT ui_layout FROM user_settings WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return row[0] if row else "focus"

    def save_user_layout(self, user_id: int, layout: str) -> None:
        """Save user's preferred UI layout."""
        self._conn.execute(
            """
            INSERT INTO user_settings (user_id, ui_layout)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                ui_layout = excluded.ui_layout,
                updated_at = datetime('now')
            """,
            (user_id, layout),
        )
        self._conn.commit()
