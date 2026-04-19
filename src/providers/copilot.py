"""GitHub Copilot provider: reads Copilot Chat session JSON files.

Copilot Chat stores sessions in JSON files at:
  Windows: %APPDATA%/GitHub Copilot Chat/sessions/
  macOS:   ~/Library/Application Support/GitHub Copilot Chat/sessions/
  Linux:   ~/.config/github-copilot/chat/

Note: The exact paths and schema may vary across VS Code and JetBrains integrations.
Run with --debug to inspect raw session files.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .base import BaseProvider, SessionInfo


def _copilot_sessions_dirs() -> list[Path]:
    import sys
    paths: list[Path] = []
    if sys.platform == "win32":
        appdata = Path.home() / "AppData" / "Roaming"
        paths += [
            appdata / "GitHub Copilot Chat" / "sessions",
            appdata / "github-copilot" / "sessions",
        ]
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
        paths += [
            base / "GitHub Copilot Chat" / "sessions",
            base / "github-copilot" / "chat",
        ]
    else:
        config = Path.home() / ".config"
        paths += [
            config / "github-copilot" / "chat",
            config / "GitHub Copilot Chat" / "sessions",
        ]
    return [p for p in paths if p.exists()]


def _convert_copilot_session_to_jsonl(session_data: dict | list, session_id: str) -> str | None:
    """Convert Copilot session JSON to our JSONL format."""
    messages: list[dict] = []

    if isinstance(session_data, list):
        messages = session_data
    elif isinstance(session_data, dict):
        messages = (
            session_data.get("messages")
            or session_data.get("turns")
            or session_data.get("history")
            or []
        )

    records: list[dict] = []
    for msg in messages:
        role = msg.get("role") or msg.get("type") or ""
        content = msg.get("content") or msg.get("text") or msg.get("message") or ""
        if not content:
            continue
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )
        if role in ("user", "human"):
            records.append({
                "type": "user",
                "timestamp": msg.get("timestamp", ""),
                "message": {"content": content},
            })
        elif role in ("assistant", "copilot", "ai", "model"):
            records.append({
                "type": "assistant",
                "timestamp": msg.get("timestamp", ""),
                "message": {"content": [{"type": "text", "text": content}]},
            })

    if not records:
        return None

    tmp = Path(tempfile.mktemp(suffix=f"_{session_id}.jsonl"))
    with tmp.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")
    return str(tmp)


class CopilotProvider(BaseProvider):
    """Reads GitHub Copilot Chat session JSON files."""

    @property
    def name(self) -> str:
        return "copilot"

    def is_available(self) -> bool:
        return bool(_copilot_sessions_dirs())

    def discover_sessions(self, project_filter: str | None = None) -> list[SessionInfo]:
        sessions: list[SessionInfo] = []
        for sessions_dir in _copilot_sessions_dirs():
            for json_file in sorted(sessions_dir.rglob("*.json"), key=lambda p: p.stat().st_mtime):
                try:
                    with json_file.open(encoding="utf-8") as fh:
                        data = json.load(fh)
                    session_id = f"copilot_{json_file.stem}"
                    jsonl_path = _convert_copilot_session_to_jsonl(data, session_id)
                    if jsonl_path:
                        sessions.append(SessionInfo(
                            session_id=session_id,
                            file_path=jsonl_path,
                            provider=self.name,
                            project_name=f"copilot/{json_file.parent.name}",
                        ))
                except (json.JSONDecodeError, OSError):
                    continue
        return sessions
