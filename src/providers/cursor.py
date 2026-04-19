"""Cursor provider: reads Cursor AI chat sessions from its SQLite database.

Cursor stores chat history in a SQLite database at:
  Windows: %APPDATA%/Cursor/User/workspaceStorage/<hash>/state.vscdb
  macOS:   ~/Library/Application Support/Cursor/User/workspaceStorage/<hash>/state.vscdb
  Linux:   ~/.config/Cursor/User/workspaceStorage/<hash>/state.vscdb

The relevant table is `ItemTable` with key `workbench.panel.aichat.view.aichat.chatdata`.
The value is JSON containing the conversation history.

Note: Schema may vary across Cursor versions. Run with --debug to inspect raw data.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import shutil
from pathlib import Path

from .base import BaseProvider, SessionInfo


def _cursor_db_dir() -> Path:
    import sys
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "workspaceStorage"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
    else:
        base = Path.home() / ".config" / "Cursor" / "User" / "workspaceStorage"
    return base


def _convert_cursor_chat_to_jsonl(chat_data: dict, session_id: str) -> str | None:
    """Convert Cursor chat JSON to our JSONL format. Returns path to temp file or None."""
    # Cursor chat data structure (approximate — varies by version):
    # {"tabs": [{"chatTitle": "...", "bubbles": [{"type": "user"|"ai", "text": "...", ...}]}]}
    tabs = chat_data.get("tabs") or chat_data.get("conversations") or []
    if not tabs:
        return None

    records: list[dict] = []
    for tab in tabs:
        bubbles = tab.get("bubbles") or tab.get("messages") or []
        for bubble in bubbles:
            role = bubble.get("type") or bubble.get("role") or ""
            text = bubble.get("text") or bubble.get("content") or ""
            if not text:
                continue
            if role in ("user", "human"):
                records.append({
                    "type": "user",
                    "timestamp": bubble.get("timestamp", ""),
                    "message": {"content": text},
                })
            elif role in ("ai", "assistant", "model"):
                records.append({
                    "type": "assistant",
                    "timestamp": bubble.get("timestamp", ""),
                    "message": {"content": [{"type": "text", "text": text}]},
                })

    if not records:
        return None

    tmp = Path(tempfile.mktemp(suffix=f"_{session_id}.jsonl"))
    with tmp.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")
    return str(tmp)


class CursorProvider(BaseProvider):
    """Reads Cursor AI chat sessions from SQLite workspace databases."""

    @property
    def name(self) -> str:
        return "cursor"

    def is_available(self) -> bool:
        return _cursor_db_dir().exists()

    def discover_sessions(self, project_filter: str | None = None) -> list[SessionInfo]:
        db_dir = _cursor_db_dir()
        if not db_dir.exists():
            return []

        sessions: list[SessionInfo] = []
        for db_file in sorted(db_dir.rglob("state.vscdb"), key=lambda p: p.stat().st_mtime):
            try:
                conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT value FROM ItemTable WHERE key = 'workbench.panel.aichat.view.aichat.chatdata' LIMIT 1"
                )
                row = cursor.fetchone()
                conn.close()

                if not row:
                    continue

                chat_data = json.loads(row[0])
                session_id = f"cursor_{db_file.parent.name}"
                jsonl_path = _convert_cursor_chat_to_jsonl(chat_data, session_id)
                if jsonl_path:
                    sessions.append(SessionInfo(
                        session_id=session_id,
                        file_path=jsonl_path,
                        provider=self.name,
                        project_name=f"cursor/{db_file.parent.name[:8]}",
                    ))
            except (sqlite3.Error, json.JSONDecodeError, OSError):
                continue

        return sessions
