"""Tests for GeminiProvider."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.providers.gemini import GeminiProvider


class TestGeminiProvider:
    def test_name(self):
        assert GeminiProvider().name == "gemini"

    def test_not_available_when_dir_missing(self):
        with patch.object(GeminiProvider, "_transcripts_dir", return_value=Path("/nonexistent/path")):
            assert not GeminiProvider().is_available()

    def test_discovers_jsonl_files(self, tmp_path):
        (tmp_path / "session1.jsonl").write_text('{"type":"user","message":{"content":"hi"}}\n')
        (tmp_path / "session2.jsonl").write_text('{"type":"user","message":{"content":"ho"}}\n')

        with patch.object(GeminiProvider, "_transcripts_dir", return_value=tmp_path):
            provider = GeminiProvider()
            sessions = provider.discover_sessions()

        assert len(sessions) == 2
        ids = {s.session_id for s in sessions}
        assert "session1" in ids
        assert "session2" in ids
        assert all(s.provider == "gemini" for s in sessions)
