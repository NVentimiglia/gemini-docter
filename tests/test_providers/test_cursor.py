"""Tests for CursorProvider."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.providers.cursor import CursorProvider, _convert_cursor_chat_to_jsonl


class TestCursorProvider:
    def test_name(self):
        assert CursorProvider().name == "cursor"

    def test_convert_cursor_chat_to_jsonl(self):
        chat_data = {
            "tabs": [
                {
                    "bubbles": [
                        {"type": "user", "text": "Hello assistant"},
                        {"type": "ai", "text": "Hello user"}
                    ]
                }
            ]
        }
        jsonl_path = _convert_cursor_chat_to_jsonl(chat_data, "test_session")
        assert jsonl_path is not None
        path = Path(jsonl_path)
        assert path.exists()
        
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        
        user_msg = json.loads(lines[0])
        assert user_msg["type"] == "user"
        assert user_msg["message"]["content"] == "Hello assistant"
        
        ai_msg = json.loads(lines[1])
        assert ai_msg["type"] == "assistant"
        assert ai_msg["message"]["content"][0]["text"] == "Hello user"
        
        path.unlink()

    def test_discovers_sqlite_sessions(self, tmp_path):
        db_dir = tmp_path / "workspaceStorage" / "hash123"
        db_dir.mkdir(parents=True)
        db_file = db_dir / "state.vscdb"
        
        # Create a mock SQLite DB
        conn = sqlite3.connect(db_file)
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        chat_json = json.dumps({
            "tabs": [{"bubbles": [{"type": "user", "text": "query"}]}]
        })
        conn.execute(
            "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
            ("workbench.panel.aichat.view.aichat.chatdata", chat_json)
        )
        conn.commit()
        conn.close()

        provider = CursorProvider()
        with patch("src.providers.cursor._cursor_db_dir", return_value=tmp_path / "workspaceStorage"):
            sessions = provider.discover_sessions()

        assert len(sessions) == 1
        assert sessions[0].session_id == "cursor_hash123"
        assert sessions[0].provider == "cursor"
        assert Path(sessions[0].file_path).exists()
        Path(sessions[0].file_path).unlink()
