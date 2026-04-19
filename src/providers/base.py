"""BaseProvider: interface all providers must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SessionInfo:
    """Normalized session descriptor returned by any provider."""
    session_id: str
    file_path: str          # Path to the JSONL transcript (may be the original or a temp)
    provider: str           # "gemini" | "claude" | "cursor" | "copilot"
    project_name: str = ""  # Human-readable project label


class BaseProvider(ABC):
    """Abstract base class for transcript providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'gemini', 'claude'."""
        ...

    @abstractmethod
    def discover_sessions(self, project_filter: str | None = None) -> list[SessionInfo]:
        """Return all available sessions, optionally filtered by project name."""
        ...

    def is_available(self) -> bool:
        """Return True if this provider's data source exists on this machine."""
        return True
