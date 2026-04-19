"""Map signal patterns to actionable GEMINI.md rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

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


class Suggestion(NamedTuple):
    rule: str
    examples: list[str]


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


def generate_suggestions(signals: list[SignalResult]) -> list[Suggestion]:
    suggestions: list[Suggestion] = []
    aggregated = _aggregate_signals(signals)

    for agg in aggregated:
        examples = []
        for s in signals:
            if s.signal_name == agg.signal_name and s.examples:
                examples.extend(s.examples)
        
        rule = None
        match agg.signal_name:
            case "edit-thrashing":
                if agg.count >= SUGGESTION_EDIT_THRASHING_MIN:
                    rule = (
                        "Read the full file before editing. Plan all changes, then make ONE complete edit. "
                        "If you've edited a file 3+ times, stop and re-read the user's requirements."
                    )
            case "error-loop":
                if agg.count >= SUGGESTION_ERROR_LOOP_MIN:
                    rule = (
                        "After 2 consecutive tool failures, stop and change your approach entirely. "
                        "Explain what failed and try a different strategy."
                    )
            case "negative-sentiment" | "correction-heavy":
                if agg.count >= min(SUGGESTION_SENTIMENT_MIN, SUGGESTION_CORRECTION_MIN):
                    rule = (
                        "When the user corrects you, stop and re-read their message. "
                        "Quote back what they asked for and confirm before proceeding."
                    )
            case "user-interrupts":
                if agg.count >= SUGGESTION_INTERRUPTS_MIN:
                    rule = (
                        "Break work into small, verifiable steps. "
                        "Confirm your approach with the user before making large changes."
                    )
            case "excessive-exploration":
                if agg.count >= SUGGESTION_EXPLORATION_MIN:
                    rule = (
                        "Act sooner. Don't read more than 3-5 files before making a change. "
                        "Get a basic understanding, make the change, then iterate."
                    )
            case "keep-going-loop":
                if agg.count >= SUGGESTION_KEEP_GOING_MIN:
                    rule = (
                        "Complete the FULL task before stopping. "
                        "If the user asked for multiple things, implement all of them before presenting results."
                    )
            case "repeated-instructions":
                if agg.count >= SUGGESTION_REPETITION_MIN:
                    rule = "Re-read the user's last message before responding. Follow through on every instruction completely."
            case "negative-drift":
                if agg.count >= SUGGESTION_DRIFT_MIN:
                    rule = "Every few turns, re-read the original request to make sure you haven't drifted from the goal."
            case "rapid-corrections":
                if agg.count >= SUGGESTION_RAPID_MIN:
                    rule = "Double-check your output before presenting it. Verify that your changes address the user request."
            case "high-turn-ratio":
                if agg.count >= SUGGESTION_TURN_RATIO_MIN:
                    rule = "Work more autonomously. Make reasonable decisions without asking for confirmation on every step."

        if rule:
            suggestions.append(Suggestion(rule, examples[:3]))

    return suggestions


def generate_gemini_rules(signals: list[SignalResult], total_sessions: int) -> str:
    from .formatter import format_example, format_rules_block

    suggestions = generate_suggestions(signals)
    if not suggestions:
        return ""

    lines: list[str] = []
    lines.append("## AI Coding Rules")
    lines.append("")
    lines.append(f"Generated by gemini-docter from {total_sessions} session(s).")
    lines.append("")

    rules = [s.rule for s in suggestions]
    formatted = format_rules_block(rules)

    for formatted_rule, suggestion in zip(formatted, suggestions):
        lines.append(formatted_rule)
        for example in suggestion.examples[:3]:
            display, _ref = format_example(example)
            lines.append(display)

    return "\n".join(lines)
