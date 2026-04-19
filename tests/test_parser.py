"""Tests for src/parser.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import (
    extract_tool_errors,
    extract_tool_uses,
    extract_user_messages,
    parse_transcript_file,
)


def _write_jsonl(records: list[dict]) -> str:
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    with tmp.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return str(tmp)


class TestParseTranscriptFile:
    def test_empty_file(self):
        path = _write_jsonl([])
        events = parse_transcript_file(path)
        assert events == []

    def test_parses_user_event(self):
        path = _write_jsonl([
            {"type": "user", "timestamp": "2025-01-01T00:00:00Z", "message": {"content": "hello"}}
        ])
        events = parse_transcript_file(path)
        assert len(events) == 1
        assert events[0].type == "user"
        assert events[0].message["content"] == "hello"

    def test_skips_malformed_lines(self):
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        tmp.write_text('{"type": "user"}\nNOT_JSON\n{"type": "assistant"}\n')
        events = parse_transcript_file(str(tmp))
        assert len(events) == 2

    def test_missing_file_returns_empty(self):
        events = parse_transcript_file("/nonexistent/path.jsonl")
        assert events == []


class TestExtractUserMessages:
    def test_extracts_string_content(self):
        path = _write_jsonl([
            {"type": "user", "timestamp": "2025-01-01T00:00:00Z", "message": {"content": "test msg"}},
        ])
        events = parse_transcript_file(path)
        messages = extract_user_messages(events)
        assert messages == ["test msg"]

    def test_skips_tool_result_content(self):
        path = _write_jsonl([
            {
                "type": "user",
                "timestamp": "2025-01-01T00:00:00Z",
                "message": {"content": [{"type": "tool_result", "content": "ok"}]},
            },
        ])
        events = parse_transcript_file(path)
        messages = extract_user_messages(events)
        assert messages == []

    def test_skips_meta_messages(self):
        path = _write_jsonl([
            {"type": "user", "timestamp": "t", "message": {"content": "<local-command>foo"}},
        ])
        events = parse_transcript_file(path)
        assert extract_user_messages(events) == []


class TestExtractToolUses:
    def test_extracts_tool_use_blocks(self):
        path = _write_jsonl([
            {
                "type": "assistant",
                "timestamp": "t",
                "message": {
                    "content": [
                        {"type": "text", "text": "I'll write the file"},
                        {"type": "tool_use", "id": "1", "name": "write_file", "input": {"file_path": "foo.py", "content": "x"}},
                    ]
                },
            }
        ])
        events = parse_transcript_file(path)
        uses = extract_tool_uses(events)
        assert len(uses) == 1
        assert uses[0].name == "write_file"
        assert uses[0].input["file_path"] == "foo.py"


class TestExtractToolErrors:
    def test_counts_is_error_true(self):
        path = _write_jsonl([
            {
                "type": "user",
                "timestamp": "t",
                "message": {
                    "content": [
                        {"type": "tool_result", "is_error": True, "content": "File not found"},
                    ]
                },
            }
        ])
        events = parse_transcript_file(path)
        assert extract_tool_errors(events) == 1

    def test_counts_tool_use_error_marker(self):
        path = _write_jsonl([
            {
                "type": "user",
                "timestamp": "t",
                "message": {
                    "content": [
                        {"type": "tool_result", "is_error": False, "content": "<tool_use_error>oops</tool_use_error>"},
                    ]
                },
            }
        ])
        events = parse_transcript_file(path)
        assert extract_tool_errors(events) == 1
