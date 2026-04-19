"""Tests for ClaudeProvider."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.providers.claude import ClaudeProvider


class TestClaudeProvider:
    def test_name(self):
        assert ClaudeProvider().name == "claude"

    def test_not_available_when_dir_missing(self):
        with patch.object(ClaudeProvider, "_projects_dir", return_value=Path("/nonexistent")):
            assert not ClaudeProvider().is_available()

    def test_decodes_project_name(self):
        provider = ClaudeProvider()
        assert provider._decode_project_name("Users-foo-myproject") == "Users/foo/myproject"

    def test_discovers_jsonl_sessions(self, tmp_path):
        project_dir = tmp_path / "Users-foo-myproject"
        project_dir.mkdir()
        (project_dir / "abc123.jsonl").write_text('{"type":"user"}\n')
        (project_dir / "agent-sub.jsonl").write_text("")  # should be skipped

        with patch.object(ClaudeProvider, "_projects_dir", return_value=tmp_path):
            sessions = ClaudeProvider().discover_sessions()

        assert len(sessions) == 1
        assert sessions[0].session_id == "abc123"
        assert sessions[0].provider == "claude"
        assert sessions[0].project_name == "Users/foo/myproject"

    def test_project_filter(self, tmp_path):
        proj_a = tmp_path / "Users-foo-projectA"
        proj_b = tmp_path / "Users-foo-projectB"
        proj_a.mkdir()
        proj_b.mkdir()
        (proj_a / "s1.jsonl").write_text("")
        (proj_b / "s2.jsonl").write_text("")

        with patch.object(ClaudeProvider, "_projects_dir", return_value=tmp_path):
            sessions = ClaudeProvider().discover_sessions(project_filter="projectA")

        assert len(sessions) == 1
        assert sessions[0].session_id == "s1"
