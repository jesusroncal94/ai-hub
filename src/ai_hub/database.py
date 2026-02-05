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
