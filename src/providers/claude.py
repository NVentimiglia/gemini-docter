"""Claude provider: reads Claude Code JSONL transcripts from ~/.claude/projects/."""

from __future__ import annotations

from pathlib import Path

from .base import BaseProvider, SessionInfo

CLAUDE_PROJECTS_DIR = ".claude/projects"


class ClaudeProvider(BaseProvider):
    """Reads Claude Code session transcripts. Format is identical to our JSONL."""

    @property
    def name(self) -> str:
        return "claude"

    def _projects_dir(self) -> Path:
        return Path.home() / CLAUDE_PROJECTS_DIR

    def is_available(self) -> bool:
        return self._projects_dir().exists()

    def _decode_project_name(self, encoded: str) -> str:
        return encoded.replace("-", "/").lstrip("/")

    def discover_sessions(self, project_filter: str | None = None) -> list[SessionInfo]:
        projects_dir = self._projects_dir()
        if not projects_dir.exists():
            return []

        sessions: list[SessionInfo] = []
        for project_dir in sorted(projects_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            project_name = self._decode_project_name(project_dir.name)
            if project_filter and project_filter not in project_name:
                continue

            for jsonl_file in sorted(project_dir.glob("*.jsonl")):
                if jsonl_file.name.startswith("agent-"):
                    continue
                sessions.append(SessionInfo(
                    session_id=jsonl_file.stem,
                    file_path=str(jsonl_file),
                    provider=self.name,
                    project_name=project_name,
                ))

        return sessions
