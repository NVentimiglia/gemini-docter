"""Parse JSONL transcript files written by the Gemini CLI hooks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import (
    INTERRUPT_PATTERN,
    MAX_USER_MESSAGE_LENGTH,
    META_MESSAGE_PATTERNS,
)


@dataclass
class TranscriptEvent:
    type: str  # "user" | "assistant" | "session_end"
    timestamp: str | None
    message: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_meta(self) -> bool:
        return self.raw.get("isMeta", False)


@dataclass
class ToolUseEntry:
    name: str
    input: dict[str, Any]
    id: str | None = None


def parse_transcript_file(file_path: str | Path) -> list[TranscriptEvent]:
    events: list[TranscriptEvent] = []
    path = Path(file_path)
    if not path.exists():
        return events
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                events.append(
                    TranscriptEvent(
                        type=raw.get("type", ""),
                        timestamp=raw.get("timestamp"),
                        message=raw.get("message"),
                        raw=raw,
                    )
                )
            except json.JSONDecodeError:
                pass
    return events


def is_user_event(event: TranscriptEvent) -> bool:
    return event.type == "user"


def is_assistant_event(event: TranscriptEvent) -> bool:
    return event.type == "assistant"


def _is_meta_content(content: str) -> bool:
    return any(p.search(content) for p in META_MESSAGE_PATTERNS)


def extract_user_messages(events: list[TranscriptEvent]) -> list[str]:
    messages: list[str] = []
    for event in events:
        if not is_user_event(event):
            continue
        if event.is_meta:
            continue
        content = event.message.get("content") if event.message else None
        if not isinstance(content, str):
            continue
        if _is_meta_content(content):
            continue
        if len(content) > MAX_USER_MESSAGE_LENGTH:
            continue
        messages.append(content)
    return messages


def extract_tool_uses(events: list[TranscriptEvent]) -> list[ToolUseEntry]:
    tool_uses: list[ToolUseEntry] = []
    for event in events:
        if not is_assistant_event(event):
            continue
        content = event.message.get("content") if event.message else None
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                tool_uses.append(
                    ToolUseEntry(
                        name=block.get("name", ""),
                        input=block.get("input", {}),
                        id=block.get("id"),
                    )
                )
    return tool_uses


def extract_tool_errors(events: list[TranscriptEvent]) -> int:
    error_count = 0
    for event in events:
        if not is_user_event(event):
            continue
        content = event.message.get("content") if event.message else None
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_result":
                continue
            if block.get("is_error"):
                error_count += 1
                continue
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                result_content = "".join(
                    b.get("text", "") for b in result_content if isinstance(b, dict)
                )
            if isinstance(result_content, str) and "<tool_use_error>" in result_content:
                error_count += 1
    return error_count


def count_interrupts(events: list[TranscriptEvent]) -> int:
    count = 0
    for event in events:
        if not is_user_event(event):
            continue
        content = event.message.get("content") if event.message else None
        if isinstance(content, str) and INTERRUPT_PATTERN.search(content):
            count += 1
    return count


def get_session_time_range(events: list[TranscriptEvent]) -> tuple[datetime, datetime]:
    times: list[float] = []
    for event in events:
        if not event.timestamp:
            continue
        try:
            ts = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            times.append(ts.timestamp())
        except ValueError:
            pass
    if not times:
        epoch = datetime.fromtimestamp(0)
        return epoch, epoch
    return datetime.fromtimestamp(min(times)), datetime.fromtimestamp(max(times))
