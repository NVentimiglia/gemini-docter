"""Sentiment analysis using vaderSentiment with custom frustration tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..constants import (
    INTERRUPT_CRITICAL_THRESHOLD,
    INTERRUPT_PATTERN,
    INTERRUPT_SCORE_MULTIPLIER,
    SENTINEL_CUSTOM_TOKENS,
    SENTIMENT_CRITICAL_THRESHOLD,
    SENTIMENT_EXTREME_THRESHOLD,
    SENTIMENT_FRUSTRATION_THRESHOLD,
    SENTIMENT_HIGH_THRESHOLD,
    SENTIMENT_NEGATIVE_THRESHOLD,
)
from ..parser import TranscriptEvent, is_user_event, extract_user_messages, parse_transcript_file
from .behavioral import SignalResult

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
    _VADER_AVAILABLE = True
except ImportError:
    _vader = None
    _VADER_AVAILABLE = False

# Phrase-level negative patterns used when vaderSentiment is unavailable
_FALLBACK_NEGATIVE_PHRASES = [
    (r"\bundo\b", -3),
    (r"\brevert\b", -3),
    (r"\bwrong\b", -3),
    (r"\bincorrect\b", -3),
    (r"\brollback\b", -3),
    (r"\bstart over\b", -4),
    (r"\btry again\b", -2),
    (r"\bnot what i\b", -4),
    (r"\bthat'?s not\b", -3),
    (r"\bthats not\b", -3),
    (r"\balready told\b", -4),
    (r"\bi said\b", -3),
    (r"\bjust do\b", -2),
    (r"\bbroken\b", -2),
    (r"\bdoesn'?t work\b", -3),
    (r"\bnot working\b", -3),
    (r"\bstill broken\b", -4),
    (r"\bkeep going\b", -1),
    (r"\bshit\b", -3),
    (r"\bfuck\b", -4),
    (r"\bdamn\b", -2),
]
_FALLBACK_PATTERNS = [(re.compile(p, re.IGNORECASE), score) for p, score in _FALLBACK_NEGATIVE_PHRASES]


@dataclass
class SentimentScore:
    score: float
    message: str


@dataclass
class SessionSentiment:
    session_id: str
    average_score: float
    worst_score: float
    message_scores: list[SentimentScore]
    interrupt_count: int
    frustration_messages: list[str] = field(default_factory=list)


def _score_message(message: str) -> float:
    if _VADER_AVAILABLE:
        scores = _vader.polarity_scores(message)
        # Scale compound [-1, 1] to match claude-doctor range roughly [-5, 5]
        return scores["compound"] * 5
    # Fallback: count negative phrase hits
    total = 0.0
    for pattern, score in _FALLBACK_PATTERNS:
        if pattern.search(message):
            total += score
    return total


def analyze_session_sentiment(file_path: str, session_id: str) -> SessionSentiment:
    events = parse_transcript_file(file_path)
    user_messages = extract_user_messages(events)

    message_scores = [SentimentScore(score=_score_message(m), message=m) for m in user_messages]

    interrupt_count = sum(
        1 for event in events
        if is_user_event(event)
        and isinstance((event.message or {}).get("content"), str)
        and INTERRUPT_PATTERN.search(event.message["content"])
    )

    scores = [ms.score for ms in message_scores]
    average_score = sum(scores) / len(scores) if scores else 0.0
    worst_score = min(scores) if scores else 0.0

    frustration_messages = [
        ms.message for ms in message_scores
        if ms.score < SENTIMENT_FRUSTRATION_THRESHOLD
    ]

    return SessionSentiment(
        session_id=session_id,
        average_score=average_score,
        worst_score=worst_score,
        message_scores=message_scores,
        interrupt_count=interrupt_count,
        frustration_messages=frustration_messages,
    )


def sentiment_to_signals(sentiment: SessionSentiment) -> list[SignalResult]:
    signals: list[SignalResult] = []

    if sentiment.average_score < SENTIMENT_NEGATIVE_THRESHOLD:
        signals.append(SignalResult(
            signal_name="negative-sentiment",
            severity=(
                "critical" if sentiment.average_score < SENTIMENT_CRITICAL_THRESHOLD
                else "high" if sentiment.average_score < SENTIMENT_HIGH_THRESHOLD
                else "medium"
            ),
            score=sentiment.average_score,
            details=(
                f"Average sentiment score: {sentiment.average_score:.2f} "
                f"across {len(sentiment.message_scores)} messages"
            ),
            session_id=sentiment.session_id,
            examples=sentiment.frustration_messages[:5],
        ))

    if sentiment.interrupt_count > 0:
        signals.append(SignalResult(
            signal_name="user-interrupts",
            severity="critical" if sentiment.interrupt_count >= INTERRUPT_CRITICAL_THRESHOLD else "high",
            score=-(sentiment.interrupt_count * INTERRUPT_SCORE_MULTIPLIER),
            details=f"User interrupted the agent {sentiment.interrupt_count} time(s)",
            session_id=sentiment.session_id,
        ))

    if sentiment.worst_score < SENTIMENT_EXTREME_THRESHOLD:
        signals.append(SignalResult(
            signal_name="extreme-frustration",
            severity="critical",
            score=sentiment.worst_score,
            details=f"Worst single message score: {sentiment.worst_score:.2f}",
            session_id=sentiment.session_id,
            examples=sentiment.frustration_messages[:3],
        ))

    return signals
