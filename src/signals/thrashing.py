"""Edit-thrashing detection: same file edited 5+ times in one session.

Also detects large-file writes (>150 lines) which suggest the agent should
have used targeted edits instead of rewriting the whole file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..constants import (
    EDIT_TOOL_NAMES,
    THRASHING_EDIT_THRESHOLD,
    THRASHING_SEVERITY_CRITICAL,
    THRASHING_SEVERITY_HIGH,
)
from ..parser import extract_tool_uses, parse_transcript_file
from .behavioral import SignalResult

LARGE_FILE_LINE_THRESHOLD = 150


@dataclass
class FileEditCount:
    file_path: str
    edit_count: int
    tool_names: list[str] = field(default_factory=list)


def _extract_file_path(input_data: dict) -> str | None:
    for key in ("file_path", "path", "filePath", "target_file", "file", "filename"):
        value = input_data.get(key)
        if isinstance(value, str):
            return value
    return None


def detect_thrashing(file_path: str, session_id: str) -> list[SignalResult]:
    events = parse_transcript_file(file_path)
    tool_uses = extract_tool_uses(events)

    edit_counts: dict[str, FileEditCount] = {}

    for tool_use in tool_uses:
        is_edit = any(
            edit_name.lower() in tool_use.name.lower()
            for edit_name in EDIT_TOOL_NAMES
        )
        if not is_edit:
            continue
        target = _extract_file_path(tool_use.input)
        if not target:
            continue

        if target in edit_counts:
            edit_counts[target].edit_count += 1
            if tool_use.name not in edit_counts[target].tool_names:
                edit_counts[target].tool_names.append(tool_use.name)
        else:
            edit_counts[target] = FileEditCount(
                file_path=target,
                edit_count=1,
                tool_names=[tool_use.name],
            )

    # ── Large-file writes ────────────────────────────────────────────────────
    large_file_writes: list[str] = []
    for tool_use in tool_uses:
        is_edit = any(e.lower() in tool_use.name.lower() for e in EDIT_TOOL_NAMES)
        if not is_edit:
            continue
        content = tool_use.input.get("content") or tool_use.input.get("new_content") or ""
        if isinstance(content, str) and content.count("\n") >= LARGE_FILE_LINE_THRESHOLD:
            target = _extract_file_path(tool_use.input) or "unknown"
            large_file_writes.append(f"{target} ({content.count(chr(10)) + 1} lines)")

    signals: list[SignalResult] = []

    if large_file_writes:
        signals.append(SignalResult(
            signal_name="large-file-write",
            severity="medium",
            score=-len(large_file_writes) * 2,
            details=(
                f"{len(large_file_writes)} write(s) of files >={LARGE_FILE_LINE_THRESHOLD} lines. "
                "Prefer targeted edits over full rewrites."
            ),
            session_id=session_id,
            examples=large_file_writes[:5],
        ))

    thrashing_files = sorted(
        [f for f in edit_counts.values() if f.edit_count >= THRASHING_EDIT_THRESHOLD],
        key=lambda f: f.edit_count,
        reverse=True,
    )

    if thrashing_files:
        worst = thrashing_files[0]
        total_edits = sum(f.edit_count for f in thrashing_files)
        signals.append(SignalResult(
            signal_name="edit-thrashing",
            severity=(
                "critical" if worst.edit_count >= THRASHING_SEVERITY_CRITICAL
                else "high" if worst.edit_count >= THRASHING_SEVERITY_HIGH
                else "medium"
            ),
            score=-total_edits,
            details=(
                f"{len(thrashing_files)} file(s) edited {THRASHING_EDIT_THRESHOLD}+ times. "
                f"Worst: {worst.file_path} ({worst.edit_count}x)"
            ),
            session_id=session_id,
            examples=[f"{f.file_path} ({f.edit_count}x)" for f in thrashing_files[:5]],
        ))

    return signals
