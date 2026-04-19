"""Tests for CopilotProvider."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.providers.copilot import CopilotProvider, _convert_copilot_session_to_jsonl


class TestCopilotProvider:
    def test_name(self):
        assert CopilotProvider().name == "copilot"

    def test_convert_copilot_session_to_jsonl(self):
        session_data = {
            "messages": [
                {"role": "user", "content": "How do I test this?"},
                {"role": "assistant", "content": "Use pytest."}
            ]
        }
        jsonl_path = _convert_copilot_session_to_jsonl(session_data, "test_copilot")
        assert jsonl_path is not None
        path = Path(jsonl_path)
        assert path.exists()

        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        
        user_msg = json.loads(lines[0])
        assert user_msg["type"] == "user"
        assert user_msg["message"]["content"] == "How do I test this?"
        
        ai_msg = json.loads(lines[1])
        assert ai_msg["type"] == "assistant"
        assert ai_msg["message"]["content"][0]["text"] == "Use pytest."
        
        path.unlink()

    def test_discovers_json_sessions(self, tmp_path):
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        session_file = session_dir / "abc-123.json"
        session_file.write_text(json.dumps({
            "messages": [{"role": "user", "content": "test"}]
        }))

        provider = CopilotProvider()
        with patch("src.providers.copilot._copilot_sessions_dirs", return_value=[session_dir]):
            sessions = provider.discover_sessions()

        assert len(sessions) == 1
        assert sessions[0].session_id == "copilot_abc-123"
        assert sessions[0].provider == "copilot"
        assert Path(sessions[0].file_path).exists()
        Path(sessions[0].file_path).unlink()
