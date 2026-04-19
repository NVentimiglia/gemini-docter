"""Behavioral anti-pattern detection: corrections, keep-going loops, repetition, drift, velocity."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from ..constants import (
    CORRECTION_PATTERNS,
    CORRECTION_RATE_CRITICAL,
    CORRECTION_RATE_THRESHOLD,
    CORRECTION_SCORE_MULTIPLIER,
    DRIFT_CORRECTION_WEIGHT,
    DRIFT_HIGH_THRESHOLD,
    DRIFT_LENGTH_WEIGHT,
    DRIFT_MIN_MESSAGES,
    DRIFT_NEGATIVE_THRESHOLD,
    DRIFT_SCORE_MULTIPLIER,
    HIGH_TURN_RATIO_HIGH,
    HIGH_TURN_RATIO_THRESHOLD,
    KEEP_GOING_HIGH_THRESHOLD,
    KEEP_GOING_MIN_TO_FLAG,
    KEEP_GOING_PATTERNS,
    KEEP_GOING_SCORE_MULTIPLIER,
    MAX_USER_MESSAGE_LENGTH,
    META_MESSAGE_PATTERNS,
    MIN_CORRECTIONS_TO_FLAG,
    MIN_RAPID_FOLLOWUPS_TO_FLAG,
    MIN_REPETITIONS_TO_FLAG,
    MIN_USER_TURNS_FOR_RATIO,
    RAPID_FOLLOWUP_HIGH_THRESHOLD,
    RAPID_FOLLOWUP_MAX_MS,
    RAPID_FOLLOWUP_MS,
    RAPID_FOLLOWUP_SCORE_MULTIPLIER,
    REPETITION_CRITICAL_THRESHOLD,
    REPETITION_LOOKAHEAD_WINDOW,
    REPETITION_SCORE_MULTIPLIER,
    REPETITION_SIMILARITY_THRESHOLD,
    SNIPPET_LENGTH,
    TURN_RATIO_SCORE_MULTIPLIER,
)
from ..parser import (
    TranscriptEvent,
    is_assistant_event,
    is_user_event,
    parse_transcript_file,
)


@dataclass
class SignalResult:
    signal_name: str
    severity: str  # "critical" | "high" | "medium" | "low"
    score: float
    details: str
    session_id: str
    examples: list[str] = field(default_factory=list)


@dataclass
class ConversationTurn:
    type: str  # "user" | "assistant"
    timestamp: float
    content_length: int
    is_tool_result: bool
    is_interrupt: bool
    content: str | None = None


@dataclass
class TimestampedUserMessage:
    content: str
    timestamp: float
    index: int


def _parse_timestamp(ts: str | None) -> float:
    if not ts:
        return 0.0
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.timestamp() * 1000
    except ValueError:
        return 0.0


def _is_meta_content(content: str) -> bool:
    return any(p.search(content) for p in META_MESSAGE_PATTERNS)


def _extract_conversation_turns(events: list[TranscriptEvent]) -> list[ConversationTurn]:
    turns: list[ConversationTurn] = []

    for event in events:
        ts = _parse_timestamp(event.timestamp)

        if is_user_event(event):
            if event.is_meta:
                continue
            content = event.message.get("content") if event.message else None
            is_tool_result = isinstance(content, list)
            is_interrupt = (
                isinstance(content, str) and bool(re.search(r"\[Request interrupted by user", content))
            )
            text_content = content if isinstance(content, str) else ""
            content_length = 0 if is_tool_result else len(text_content)

            if is_tool_result and not is_interrupt:
                continue

            turns.append(ConversationTurn(
                type="user",
                timestamp=ts,
                content_length=content_length,
                is_tool_result=is_tool_result,
                is_interrupt=is_interrupt,
                content=text_content,
            ))

        elif is_assistant_event(event):
            content = event.message.get("content") if event.message else None
            total_length = 0
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        total_length += len(block.get("text", ""))

            turns.append(ConversationTurn(
                type="assistant",
                timestamp=ts,
                content_length=total_length,
                is_tool_result=False,
                is_interrupt=False,
            ))

    return sorted(turns, key=lambda t: t.timestamp)


def _extract_user_turns(turns: list[ConversationTurn]) -> list[TimestampedUserMessage]:
    result: list[TimestampedUserMessage] = []
    idx = 0
    for turn in turns:
        if (
            turn.type == "user"
            and not turn.is_tool_result
            and not turn.is_interrupt
            and turn.content
            and 0 < len(turn.content) < MAX_USER_MESSAGE_LENGTH
            and not _is_meta_content(turn.content)
        ):
            result.append(TimestampedUserMessage(
                content=turn.content,
                timestamp=turn.timestamp,
                index=idx,
            ))
            idx += 1
    return result


def _word_set(text: str) -> set[str]:
    return set(re.sub(r"[^\w\s]", "", text.lower()).split())


def _jaccard_similarity(a: str, b: str) -> float:
    set_a = _word_set(a)
    set_b = _word_set(b)
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def detect_behavioral_signals(file_path: str, session_id: str) -> list[SignalResult]:
    events = parse_transcript_file(file_path)
    turns = _extract_conversation_turns(events)
    user_turns = _extract_user_turns(turns)
    signals: list[SignalResult] = []

    if not user_turns:
        return signals

    # ── Correction-heavy ─────────────────────────────────────────────────────
    correction_count = sum(
        1 for t in user_turns
        if any(p.search(t.content) for p in CORRECTION_PATTERNS)
    )
    correction_rate = correction_count / len(user_turns)

    if correction_count >= MIN_CORRECTIONS_TO_FLAG and correction_rate > CORRECTION_RATE_THRESHOLD:
        signals.append(SignalResult(
            signal_name="correction-heavy",
            severity="critical" if correction_rate > CORRECTION_RATE_CRITICAL else "high",
            score=-round(correction_count * CORRECTION_SCORE_MULTIPLIER),
            details=(
                f"{correction_count}/{len(user_turns)} user messages "
                f"({round(correction_rate * 100)}%) were corrections. "
                "The agent repeatedly misunderstands or produces wrong output."
            ),
            session_id=session_id,
            examples=[
                t.content[:SNIPPET_LENGTH]
                for t in user_turns
                if any(p.search(t.content) for p in CORRECTION_PATTERNS)
            ][:5],
        ))

    # ── Keep-going loop ──────────────────────────────────────────────────────
    keep_going_count = sum(
        1 for t in user_turns
        if any(p.search(t.content.strip()) for p in KEEP_GOING_PATTERNS)
    )

    if keep_going_count >= KEEP_GOING_MIN_TO_FLAG:
        signals.append(SignalResult(
            signal_name="keep-going-loop",
            severity="high" if keep_going_count >= KEEP_GOING_HIGH_THRESHOLD else "medium",
            score=-(keep_going_count * KEEP_GOING_SCORE_MULTIPLIER),
            details=(
                f'User said "keep going" or equivalent {keep_going_count} time(s). '
                "The agent stops prematurely or produces incomplete work."
            ),
            session_id=session_id,
            examples=[
                t.content[:SNIPPET_LENGTH]
                for t in user_turns
                if any(p.search(t.content.strip()) for p in KEEP_GOING_PATTERNS)
            ][:3],
        ))

    # ── Repeated instructions ────────────────────────────────────────────────
    repetitions: list[tuple[str, str, float]] = []
    for i in range(len(user_turns)):
        for j in range(i + 1, min(i + REPETITION_LOOKAHEAD_WINDOW, len(user_turns))):
            sim = _jaccard_similarity(user_turns[i].content, user_turns[j].content)
            if sim >= REPETITION_SIMILARITY_THRESHOLD:
                repetitions.append((user_turns[i].content, user_turns[j].content, sim))

    if len(repetitions) >= MIN_REPETITIONS_TO_FLAG:
        signals.append(SignalResult(
            signal_name="repeated-instructions",
            severity="critical" if len(repetitions) >= REPETITION_CRITICAL_THRESHOLD else "high",
            score=-(len(repetitions) * REPETITION_SCORE_MULTIPLIER),
            details=(
                f"User repeated similar instructions {len(repetitions)} time(s). "
                "The agent failed to act on the instruction correctly."
            ),
            session_id=session_id,
            examples=[
                f'"{a[:80]}" ~ "{b[:80]}" ({round(sim * 100)}% similar)'
                for a, b, sim in repetitions[:3]
            ],
        ))

    # ── Negative drift ───────────────────────────────────────────────────────
    if len(user_turns) >= DRIFT_MIN_MESSAGES:
        mid = len(user_turns) // 2
        first_half = user_turns[:mid]
        second_half = user_turns[mid:]

        def avg_length(turns: list[TimestampedUserMessage]) -> float:
            return sum(len(t.content) for t in turns) / len(turns) if turns else 0

        def correction_rate_half(turns: list[TimestampedUserMessage]) -> float:
            n = sum(1 for t in turns if any(p.search(t.content) for p in CORRECTION_PATTERNS))
            return n / len(turns) if turns else 0

        length_shrinkage = (
            (avg_length(first_half) - avg_length(second_half)) / avg_length(first_half)
            if avg_length(first_half) > 0 else 0
        )
        correction_increase = correction_rate_half(second_half) - correction_rate_half(first_half)
        drift_score = length_shrinkage * DRIFT_LENGTH_WEIGHT + correction_increase * DRIFT_CORRECTION_WEIGHT

        if drift_score > DRIFT_NEGATIVE_THRESHOLD:
            signals.append(SignalResult(
                signal_name="negative-drift",
                severity="high" if drift_score > DRIFT_HIGH_THRESHOLD else "medium",
                score=-round(drift_score * DRIFT_SCORE_MULTIPLIER),
                details=(
                    f"User messages became shorter and more corrective over the session "
                    f"(drift: {drift_score:.1f}). Indicates growing frustration."
                ),
                session_id=session_id,
            ))

    # ── Rapid corrections ────────────────────────────────────────────────────
    fast_follow_ups = 0
    for i in range(1, len(turns)):
        curr = turns[i]
        prev = turns[i - 1]
        if (
            curr.type == "user"
            and prev.type == "assistant"
            and not curr.is_tool_result
            and curr.content
            and not _is_meta_content(curr.content)
        ):
            response_time_ms = curr.timestamp - prev.timestamp
            if 0 < response_time_ms < RAPID_FOLLOWUP_MS:
                fast_follow_ups += 1

    if fast_follow_ups >= MIN_RAPID_FOLLOWUPS_TO_FLAG:
        signals.append(SignalResult(
            signal_name="rapid-corrections",
            severity="high" if fast_follow_ups >= RAPID_FOLLOWUP_HIGH_THRESHOLD else "medium",
            score=-(fast_follow_ups * RAPID_FOLLOWUP_SCORE_MULTIPLIER),
            details=(
                f"{fast_follow_ups} user messages sent within 10 seconds of the agent responding. "
                "Rapid follow-ups indicate the agent's output was immediately wrong."
            ),
            session_id=session_id,
        ))

    # ── High turn ratio ──────────────────────────────────────────────────────
    user_turn_count = sum(1 for t in turns if t.type == "user" and not t.is_tool_result)
    assistant_turn_count = sum(1 for t in turns if t.type == "assistant")

    if assistant_turn_count > 0 and user_turn_count >= MIN_USER_TURNS_FOR_RATIO:
        ratio = user_turn_count / assistant_turn_count
        if ratio > HIGH_TURN_RATIO_THRESHOLD:
            signals.append(SignalResult(
                signal_name="high-turn-ratio",
                severity="high" if ratio > HIGH_TURN_RATIO_HIGH else "medium",
                score=-round(ratio * TURN_RATIO_SCORE_MULTIPLIER),
                details=(
                    f"Turn ratio: {ratio:.1f} user messages per assistant response. "
                    "High ratio means the user keeps redirecting or correcting the agent."
                ),
                session_id=session_id,
            ))

    return signals
