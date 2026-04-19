"""Tests for common signal detection logic."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.signals.behavioral import detect_behavioral_signals
from src.signals.thrashing import detect_thrashing
from src.signals.error_loops import detect_error_loops
from src.signals.tool_efficiency import detect_tool_inefficiency


def _write_jsonl(records: list[dict]) -> str:
    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    with tmp.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return str(tmp)


def _user(content: str, ts: str = "2025-01-01T00:00:00Z") -> dict:
    return {"type": "user", "timestamp": ts, "message": {"content": content}}


def _assistant(text: str, tools: list[dict] | None = None, ts: str = "2025-01-01T00:00:01Z") -> dict:
    content = [{"type": "text", "text": text}]
    if tools:
        content.extend(tools)
    return {"type": "assistant", "timestamp": ts, "message": {"content": content}}


def _tool_use(name: str, file_path: str = "foo.py", extra: dict | None = None) -> dict:
    inp = {"file_path": file_path}
    if extra:
        inp.update(extra)
    return {"type": "tool_use", "id": "1", "name": name, "input": inp}


def _tool_result(is_error: bool = False, content: str = "ok") -> dict:
    return {
        "type": "user",
        "timestamp": "2025-01-01T00:00:02Z",
        "message": {"content": [{"type": "tool_result", "tool_use_id": "1", "is_error": is_error, "content": content}]},
    }


class TestCorrectionHeavy:
    def test_no_corrections_no_signal(self):
        path = _write_jsonl([
            _user("please implement feature X"),
            _assistant("done"),
            _user("looks good, thanks"),
        ])
        signals = detect_behavioral_signals(path, "s1")
        assert not any(s.signal_name == "correction-heavy" for s in signals)

    def test_correction_heavy_detected(self):
        # >20% corrections out of 5 messages = 2 corrections
        path = _write_jsonl([
            _user("please implement X"),
            _assistant("here"),
            _user("no, that's wrong"),
            _assistant("ok"),
            _user("wait, not like that"),
            _assistant("ok2"),
            _user("actually, try again"),
            _assistant("ok3"),
            _user("why did you do it that way"),
            _assistant("ok4"),
        ])
        signals = detect_behavioral_signals(path, "s1")
        names = [s.signal_name for s in signals]
        assert "correction-heavy" in names


class TestKeepGoingLoop:
    def test_keep_going_detected(self):
        records = []
        for _ in range(3):
            records.append(_user("keep going"))
            records.append(_assistant("continuing..."))
        path = _write_jsonl(records)
        signals = detect_behavioral_signals(path, "s1")
        assert any(s.signal_name == "keep-going-loop" for s in signals)

    def test_single_keep_going_not_flagged(self):
        path = _write_jsonl([_user("keep going"), _assistant("done")])
        signals = detect_behavioral_signals(path, "s1")
        assert not any(s.signal_name == "keep-going-loop" for s in signals)


class TestEditThrashing:
    def test_thrashing_detected_at_threshold(self):
        records = [_assistant("writing", [_tool_use("write_file", "foo.py")])]
        for _ in range(5):  # THRASHING_EDIT_THRESHOLD = 5
            records.append(_tool_result())
            records.append(_assistant("editing", [_tool_use("replace_file_content", "foo.py")]))
        path = _write_jsonl(records)
        signals = detect_thrashing(path, "s1")
        assert any(s.signal_name == "edit-thrashing" for s in signals)

    def test_no_thrashing_below_threshold(self):
        records = [
            _assistant("writing", [_tool_use("write_file", "foo.py")]),
            _tool_result(),
        ]
        path = _write_jsonl(records)
        signals = detect_thrashing(path, "s1")
        assert not any(s.signal_name == "edit-thrashing" for s in signals)


class TestLargeFileWrite:
    def test_large_file_write_detected(self):
        big_content = "\n".join(f"line {i}" for i in range(200))
        records = [
            _assistant("writing big file", [
                {"type": "tool_use", "id": "1", "name": "write_file",
                 "input": {"file_path": "big.py", "content": big_content}}
            ]),
        ]
        path = _write_jsonl(records)
        signals = detect_thrashing(path, "s1")
        assert any(s.signal_name == "large-file-write" for s in signals)


class TestErrorLoops:
    def test_error_loop_detected(self):
        records = [_assistant("running", [_tool_use("run_shell_command", "")])]
        for _ in range(3):  # ERROR_LOOP_THRESHOLD = 3
            records.append(_tool_result(is_error=True, content="command failed"))
        path = _write_jsonl(records)
        signals = detect_error_loops(path, "s1")
        assert any(s.signal_name == "error-loop" for s in signals)


class TestToolEfficiency:
    def test_excessive_exploration_detected(self):
        # 10+ reads, 1 edit → ratio >= 10
        records = []
        for i in range(11):
            records.append(_assistant(f"reading {i}", [_tool_use("read_file", f"file{i}.py")]))
            records.append(_tool_result())
        records.append(_assistant("writing", [_tool_use("write_file", "out.py")]))
        records.append(_tool_result())
        path = _write_jsonl(records)
        signals = detect_tool_inefficiency(path, "s1")
        assert any(s.signal_name == "excessive-exploration" for s in signals)
