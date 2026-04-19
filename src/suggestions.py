"""Map signal patterns to actionable GEMINI.md rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
    SUGGESTION_CORRECTION_MIN,
    SUGGESTION_DRIFT_MIN,
    SUGGESTION_EDIT_THRASHING_MIN,
    SUGGESTION_ERROR_LOOP_MIN,
    SUGGESTION_EXPLORATION_MIN,
    SUGGESTION_INTERRUPTS_MIN,
    SUGGESTION_KEEP_GOING_MIN,
    SUGGESTION_RAPID_MIN,
    SUGGESTION_REPETITION_MIN,
    SUGGESTION_RESTART_MIN,
    SUGGESTION_SENTIMENT_MIN,
    SUGGESTION_TURN_RATIO_MIN,
)
from .signals.behavioral import SignalResult


@dataclass
class SignalAggregation:
    signal_name: str
    count: int
    total_score: float
    worst_score: float
    affected_sessions: list[str] = field(default_factory=list)


def _aggregate_signals(signals: list[SignalResult]) -> list[SignalAggregation]:
    aggregations: dict[str, SignalAggregation] = {}
    for signal in signals:
        if signal.signal_name in aggregations:
            agg = aggregations[signal.signal_name]
            agg.count += 1
            agg.total_score += signal.score
            agg.worst_score = min(agg.worst_score, signal.score)
            if signal.session_id not in agg.affected_sessions:
                agg.affected_sessions.append(signal.session_id)
        else:
            aggregations[signal.signal_name] = SignalAggregation(
                signal_name=signal.signal_name,
                count=1,
                total_score=signal.score,
                worst_score=signal.score,
                affected_sessions=[signal.session_id],
            )
    return sorted(aggregations.values(), key=lambda a: a.total_score)


def generate_suggestions(signals: list[SignalResult]) -> list[str]:
    suggestions: list[str] = []
    aggregated = _aggregate_signals(signals)

    for agg in aggregated:
        match agg.signal_name:
            case "edit-thrashing":
                if agg.count >= SUGGESTION_EDIT_THRASHING_MIN:
                    suggestions.append(
                        "Read the full file before editing. Plan all changes, then make ONE complete edit. "
                        "If you've edited a file 3+ times, stop and re-read the user's requirements."
                    )
            case "error-loop":
                if agg.count >= SUGGESTION_ERROR_LOOP_MIN:
                    suggestions.append(
                        "After 2 consecutive tool failures, stop and change your approach entirely. "
                        "Explain what failed and try a different strategy."
                    )
            case "negative-sentiment" | "correction-heavy":
                if agg.count >= min(SUGGESTION_SENTIMENT_MIN, SUGGESTION_CORRECTION_MIN):
                    suggestions.append(
                        "When the user corrects you, stop and re-read their message. "
                        "Quote back what they asked for and confirm before proceeding."
                    )
            case "user-interrupts":
                if agg.count >= SUGGESTION_INTERRUPTS_MIN:
                    suggestions.append(
                        "Break work into small, verifiable steps. "
                        "Confirm your approach with the user before making large changes."
                    )
            case "excessive-exploration":
                if agg.count >= SUGGESTION_EXPLORATION_MIN:
                    suggestions.append(
                        "Act sooner. Don't read more than 3-5 files before making a change. "
                        "Get a basic understanding, make the change, then iterate."
                    )
            case "keep-going-loop":
                if agg.count >= SUGGESTION_KEEP_GOING_MIN:
                    suggestions.append(
                        "Complete the FULL task before stopping. "
                        "If the user asked for multiple things, implement all of them before presenting results."
                    )
            case "repeated-instructions":
                if agg.count >= SUGGESTION_REPETITION_MIN:
                    suggestions.append(
                        "Re-read the user's last message before responding. "
                        "Follow through on every instruction completely."
                    )
            case "negative-drift":
                if agg.count >= SUGGESTION_DRIFT_MIN:
                    suggestions.append(
                        "Every few turns, re-read the original request "
                        "to make sure you haven't drifted from the goal."
                    )
            case "rapid-corrections":
                if agg.count >= SUGGESTION_RAPID_MIN:
                    suggestions.append(
                        "Double-check your output before presenting it. "
                        "Verify that your changes actually address what the user asked for."
                    )
            case "high-turn-ratio":
                if agg.count >= SUGGESTION_TURN_RATIO_MIN:
                    suggestions.append(
                        "Work more autonomously. "
                        "Make reasonable decisions without asking for confirmation on every step."
                    )

    return suggestions


def generate_gemini_rules(signals: list[SignalResult], total_sessions: int) -> str:
    rules = generate_suggestions(signals)
    if not rules:
        return ""

    lines = [
        "## Rules (auto-generated by gemini-docter)",
        "",
        f"Based on analysis of {total_sessions} sessions. Paste into your GEMINI.md or AGENTS.md.",
        "",
    ]
    for rule in rules:
        lines.append(f"- {rule}")
    lines.append("")
    return "\n".join(lines)
