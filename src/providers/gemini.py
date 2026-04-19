"""Gemini provider: reads hook-captured JSONL transcripts from ~/.gemini-docter/."""

from __future__ import annotations

from pathlib import Path

from ..constants import TRANSCRIPTS_DIR
from .base import BaseProvider, SessionInfo


class GeminiProvider(BaseProvider):
    """Reads transcripts written by the AfterAgent/SessionEnd hooks."""

    @property
    def name(self) -> str:
        return "gemini"

    def _transcripts_dir(self) -> Path:
        return Path.home() / TRANSCRIPTS_DIR

    def is_available(self) -> bool:
        return self._transcripts_dir().exists()

    def discover_sessions(self, project_filter: str | None = None) -> list[SessionInfo]:
        transcripts_dir = self._transcripts_dir()
        if not transcripts_dir.exists():
            return []

        sessions: list[SessionInfo] = []
        for jsonl_file in sorted(transcripts_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
            session_id = jsonl_file.stem
            sessions.append(SessionInfo(
                session_id=session_id,
                file_path=str(jsonl_file),
                provider=self.name,
                project_name="gemini",
            ))

        return sessions
