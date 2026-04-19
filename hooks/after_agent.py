#!/usr/bin/env python3
"""AfterAgent hook — appends a JSONL turn entry to the session transcript.

Receives event JSON on stdin (fields confirmed from gemini-cli-core v0.38):
  session_id, transcript_path, cwd, hook_event_name, timestamp
  Plus AfterAgent-specific fields (may vary by version — raw input is logged).

Outputs {} to stdout (no modification).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


TRANSCRIPTS_DIR = Path.home() / ".gemini-docter" / "transcripts"
DEBUG_DIR = Path.home() / ".gemini-docter" / "debug"


def _transcript_path(session_id: str) -> Path:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    return TRANSCRIPTS_DIR / f"{session_id}.jsonl"


def _append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _log_debug(session_id: str, raw: dict) -> None:
    """Write raw hook input for schema verification during initial setup."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    debug_file = DEBUG_DIR / f"{session_id}_raw.jsonl"
    with debug_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(raw, ensure_ascii=False) + "\n")


def _extract_text_content(parts: list) -> str:
    """Extract plain text from a list of Gemini API parts."""
    texts = []
    for part in parts:
        if isinstance(part, dict):
            if "text" in part:
                texts.append(part["text"])
            elif isinstance(part.get("functionCall"), dict):
                pass  # tool calls handled separately
    return "".join(texts)


def _extract_tool_calls(parts: list) -> list[dict]:
    """Extract tool calls (functionCall parts) from model response."""
    calls = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("functionCall"), dict):
            fc = part["functionCall"]
            calls.append({
                "type": "tool_use",
                "id": part.get("id") or fc.get("id", ""),
                "name": fc.get("name", ""),
                "input": fc.get("args", {}),
            })
    return calls


def _extract_tool_results(parts: list) -> list[dict]:
    """Extract tool results (functionResponse parts) from user turn."""
    results = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("functionResponse"), dict):
            fr = part["functionResponse"]
            response_value = fr.get("response", {})
            is_error = isinstance(response_value, dict) and response_value.get("error") is not None
            content_text = json.dumps(response_value) if not isinstance(response_value, str) else response_value
            results.append({
                "type": "tool_result",
                "tool_use_id": part.get("id") or fr.get("id", ""),
                "is_error": is_error,
                "content": content_text,
            })
    return results


def process_event(raw: dict) -> None:
    session_id = raw.get("session_id", "unknown")
    timestamp = raw.get("timestamp", datetime.now(timezone.utc).isoformat())
    transcript = _transcript_path(session_id)

    # Log raw input for schema verification
    _log_debug(session_id, raw)

    # ── Extract user prompt ──────────────────────────────────────────────────
    # BeforeAgent sets `prompt`; AfterAgent may set `user_prompt` or `prompt`
    user_prompt = (
        raw.get("prompt")
        or raw.get("user_prompt")
        or raw.get("user_message")
        or raw.get("userMessage")
        or ""
    )

    # Also check nested history (Gemini API format)
    history = raw.get("history") or raw.get("conversation_history") or []
    if not user_prompt and history:
        for entry in reversed(history):
            if entry.get("role") == "user":
                parts = entry.get("parts", [])
                user_prompt = _extract_text_content(parts)
                if user_prompt:
                    break

    if user_prompt:
        _append_jsonl(transcript, {
            "type": "user",
            "timestamp": timestamp,
            "message": {"content": user_prompt},
        })

    # ── Extract model response ───────────────────────────────────────────────
    response = (
        raw.get("response")
        or raw.get("model_response")
        or raw.get("modelResponse")
        or raw.get("llm_response")
    )

    model_parts = []

    if isinstance(response, dict):
        # Try Gemini API candidates format
        candidates = response.get("candidates", [])
        if candidates and isinstance(candidates, list):
            content = candidates[0].get("content", {})
            raw_parts = content.get("parts", [])
        else:
            # Flat format: {text, tool_calls}
            raw_parts = response.get("parts", [])
            if not raw_parts:
                text = response.get("text", "")
                if text:
                    raw_parts = [{"text": text}]

        text_content = _extract_text_content(raw_parts)
        tool_calls = _extract_tool_calls(raw_parts)

        if text_content:
            model_parts.append({"type": "text", "text": text_content})
        model_parts.extend(tool_calls)

    elif isinstance(response, str) and response:
        model_parts.append({"type": "text", "text": response})

    # Also check history for the most recent model turn
    if not model_parts and history:
        for entry in reversed(history):
            if entry.get("role") in ("model", "assistant"):
                raw_parts = entry.get("parts", [])
                text_content = _extract_text_content(raw_parts)
                tool_calls = _extract_tool_calls(raw_parts)
                if text_content:
                    model_parts.append({"type": "text", "text": text_content})
                model_parts.extend(tool_calls)
                break

    if model_parts:
        _append_jsonl(transcript, {
            "type": "assistant",
            "timestamp": timestamp,
            "message": {"content": model_parts},
        })

    # ── Extract tool results ─────────────────────────────────────────────────
    tool_results_raw = raw.get("tool_results") or raw.get("toolResults") or []
    if isinstance(tool_results_raw, list) and tool_results_raw:
        tool_result_blocks = []
        for tr in tool_results_raw:
            if isinstance(tr, dict):
                is_error = tr.get("is_error") or tr.get("isError") or False
                content = tr.get("output") or tr.get("result") or tr.get("content") or ""
                if not isinstance(content, str):
                    content = json.dumps(content)
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tr.get("tool_id") or tr.get("id") or "",
                    "is_error": bool(is_error),
                    "content": content,
                })
        if tool_result_blocks:
            _append_jsonl(transcript, {
                "type": "user",
                "timestamp": timestamp,
                "message": {"content": tool_result_blocks},
            })
    elif history:
        # Extract tool results from history if not provided directly
        for entry in history:
            if entry.get("role") == "user":
                parts = entry.get("parts", [])
                results = _extract_tool_results(parts)
                if results:
                    _append_jsonl(transcript, {
                        "type": "user",
                        "timestamp": timestamp,
                        "message": {"content": results},
                    })


def main() -> int:
    try:
        raw = json.loads(sys.stdin.read())
        process_event(raw)
    except Exception:  # noqa: BLE001
        pass  # Never block the agent
    print("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
