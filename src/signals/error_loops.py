"""Error-loop detection: 3+ consecutive tool failures without changing approach."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..constants import (
    ERROR_LOOP_CRITICAL_THRESHOLD,
    ERROR_LOOP_THRESHOLD,
    ERROR_SNIPPET_MAX_LENGTH,
)
from ..parser import is_assistant_event, is_user_event, parse_transcript_file
from .behavioral import SignalResult


@dataclass
class ErrorSequence:
    tool_name: str
    consecutive_failures: int
    error_snippets: list[str] = field(default_factory=list)


def detect_error_loops(file_path: str, session_id: str) -> list[SignalResult]:
    events = parse_transcript_file(file_path)
    error_sequences: list[ErrorSequence] = []

    current_tool_name: str | None = None
    consecutive_failures = 0
    error_snippets: list[str] = []

    for event in events:
        if is_assistant_event(event):
            content = (event.message or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    current_tool_name = block.get("name")

        if is_user_event(event):
            content = (event.message or {}).get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue

                is_error = block.get("is_error") is True
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    result_content = "".join(
                        b.get("text", "") for b in result_content if isinstance(b, dict)
                    )
                has_error_marker = isinstance(result_content, str) and "<tool_use_error>" in result_content

                if is_error or has_error_marker:
                    consecutive_failures += 1
                    snippet = (result_content or "unknown error")[:ERROR_SNIPPET_MAX_LENGTH]
                    error_snippets.append(snippet)
                else:
                    if consecutive_failures >= ERROR_LOOP_THRESHOLD and current_tool_name:
                        error_sequences.append(ErrorSequence(
                            tool_name=current_tool_name,
                            consecutive_failures=consecutive_failures,
                            error_snippets=list(error_snippets),
                        ))
                    consecutive_failures = 0
                    error_snippets = []

    if consecutive_failures >= ERROR_LOOP_THRESHOLD and current_tool_name:
        error_sequences.append(ErrorSequence(
            tool_name=current_tool_name,
            consecutive_failures=consecutive_failures,
            error_snippets=list(error_snippets),
        ))

    signals: list[SignalResult] = []
    for seq in error_sequences:
        signals.append(SignalResult(
            signal_name="error-loop",
            severity="critical" if seq.consecutive_failures >= ERROR_LOOP_CRITICAL_THRESHOLD else "high",
            score=-seq.consecutive_failures,
            details=f'{seq.consecutive_failures} consecutive failures on tool "{seq.tool_name}"',
            session_id=session_id,
            examples=seq.error_snippets[:3],
        ))

    return signals
