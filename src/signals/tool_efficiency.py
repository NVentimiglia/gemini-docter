"""Tool efficiency: read-to-edit ratio and read-only sessions."""

from __future__ import annotations

from ..constants import (
    EDIT_TOOL_NAMES,
    READ_ONLY_SESSION_SCORE,
    READ_ONLY_SESSION_THRESHOLD,
    READ_TO_EDIT_RATIO_HIGH,
    READ_TO_EDIT_RATIO_THRESHOLD,
    READ_TOOL_NAMES,
)
from ..parser import extract_tool_uses, parse_transcript_file
from .behavioral import SignalResult


def detect_tool_inefficiency(file_path: str, session_id: str) -> list[SignalResult]:
    events = parse_transcript_file(file_path)
    tool_uses = extract_tool_uses(events)

    read_count = 0
    edit_count = 0

    for tool_use in tool_uses:
        name_lower = tool_use.name.lower()
        if any(r.lower() in name_lower for r in READ_TOOL_NAMES):
            read_count += 1
        if any(e.lower() in name_lower for e in EDIT_TOOL_NAMES):
            edit_count += 1

    signals: list[SignalResult] = []

    if edit_count > 0:
        ratio = read_count / edit_count
        if ratio >= READ_TO_EDIT_RATIO_THRESHOLD:
            signals.append(SignalResult(
                signal_name="excessive-exploration",
                severity="high" if ratio >= READ_TO_EDIT_RATIO_HIGH else "medium",
                score=-round(ratio),
                details=(
                    f"Read-to-edit ratio: {ratio:.1f}:1 "
                    f"({read_count} reads, {edit_count} edits). "
                    "Agent explored excessively before acting."
                ),
                session_id=session_id,
            ))
    elif read_count > READ_ONLY_SESSION_THRESHOLD:
        signals.append(SignalResult(
            signal_name="read-only-session",
            severity="medium",
            score=READ_ONLY_SESSION_SCORE,
            details=f"{read_count} read operations with zero edits — agent may have been stuck or just exploring.",
            session_id=session_id,
        ))

    return signals
