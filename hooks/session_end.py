#!/usr/bin/env python3
"""SessionEnd hook — writes session metadata to finalize the transcript.

Receives event JSON on stdin:
  session_id, transcript_path, cwd, hook_event_name, timestamp

Outputs {} to stdout (no modification).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


TRANSCRIPTS_DIR = Path.home() / ".gemini-docter" / "transcripts"


def _transcript_path(session_id: str) -> Path:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    return TRANSCRIPTS_DIR / f"{session_id}.jsonl"


def _count_turns(transcript: Path) -> tuple[int, int]:
    """Return (user_turns, assistant_turns) from existing transcript."""
    user_turns = 0
    assistant_turns = 0
    if not transcript.exists():
        return 0, 0
    with transcript.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("type") == "user":
                    content = record.get("message", {}).get("content")
                    if isinstance(content, str):
                        user_turns += 1
                elif record.get("type") == "assistant":
                    assistant_turns += 1
            except json.JSONDecodeError:
                pass
    return user_turns, assistant_turns


def main() -> int:
    try:
        raw = json.loads(sys.stdin.read())
        session_id = raw.get("session_id", "unknown")
        timestamp = raw.get("timestamp", datetime.now(timezone.utc).isoformat())
        reason = raw.get("reason") or raw.get("sessionEndReason") or "exit"

        transcript = _transcript_path(session_id)
        user_turns, assistant_turns = _count_turns(transcript)

        session_end_record = {
            "type": "session_end",
            "timestamp": timestamp,
            "session_id": session_id,
            "reason": reason,
            "turn_count": user_turns + assistant_turns,
            "user_turn_count": user_turns,
            "assistant_turn_count": assistant_turns,
        }

        with transcript.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(session_end_record, ensure_ascii=False) + "\n")

    except Exception:  # noqa: BLE001
        pass  # Never block the session end
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
