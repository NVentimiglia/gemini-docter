"""Discover and index transcript sessions from ~/.gemini-docter/transcripts/."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .constants import TRANSCRIPTS_DIR
from .parser import (
    count_interrupts,
    extract_tool_errors,
    extract_tool_uses,
    extract_user_messages,
    get_session_time_range,
    is_assistant_event,
    parse_transcript_file,
)


@dataclass
class SessionMetadata:
    session_id: str
    file_path: str
    start_time: datetime
    end_time: datetime
    user_message_count: int
    assistant_message_count: int
    tool_call_count: int
    tool_error_count: int
    interrupt_count: int


@dataclass
class ProjectMetadata:
    project_path: str
    sessions: list[SessionMetadata] = field(default_factory=list)

    @property
    def total_sessions(self) -> int:
        return len(self.sessions)


def get_transcripts_dir() -> Path:
    return Path.home() / TRANSCRIPTS_DIR


def discover_transcript_files(transcripts_dir: Path) -> list[Path]:
    if not transcripts_dir.exists():
        return []
    return sorted(
        transcripts_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
    )


async def build_session_metadata(file_path: Path) -> SessionMetadata:
    session_id = file_path.stem
    events = parse_transcript_file(file_path)
    user_messages = extract_user_messages(events)
    tool_uses = extract_tool_uses(events)
    tool_error_count = extract_tool_errors(events)
    interrupt_count = count_interrupts(events)
    start_time, end_time = get_session_time_range(events)

    assistant_message_count = sum(1 for e in events if is_assistant_event(e))

    return SessionMetadata(
        session_id=session_id,
        file_path=str(file_path),
        start_time=start_time,
        end_time=end_time,
        user_message_count=len(user_messages),
        assistant_message_count=assistant_message_count,
        tool_call_count=len(tool_uses),
        tool_error_count=tool_error_count,
        interrupt_count=interrupt_count,
    )


def index_all_sessions(project_filter: str | None = None) -> "ProjectMetadata":
    import asyncio

    transcripts_dir = get_transcripts_dir()
    files = discover_transcript_files(transcripts_dir)

    sessions: list[SessionMetadata] = []
    for file_path in files:
        session = asyncio.run(build_session_metadata(file_path))
        sessions.append(session)

    project = ProjectMetadata(
        project_path=str(transcripts_dir),
        sessions=sessions,
    )
    return project
