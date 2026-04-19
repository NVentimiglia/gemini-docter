"""Orchestrate all signal detectors across sessions and generate a report."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from .constants import (
    EXAMPLE_TRUNCATE_LENGTH,
    REPORT_PROJECT_LIMIT,
    REPORT_SIGNAL_DISPLAY_LIMIT,
    SEVERITY_WEIGHT_CRITICAL,
    SEVERITY_WEIGHT_HIGH,
    SEVERITY_WEIGHT_LOW,
    SEVERITY_WEIGHT_MEDIUM,
    TOP_SIGNALS_LIMIT,
)
from .config import get_enabled_providers, load_config
from .indexer import SessionMetadata, index_all_sessions
from .providers.base import SessionInfo
from .signals.behavioral import SignalResult, detect_behavioral_signals
from .signals.error_loops import detect_error_loops
from .signals.sentiment import analyze_session_sentiment, sentiment_to_signals
from .signals.thrashing import detect_thrashing
from .signals.tool_efficiency import detect_tool_inefficiency
from .suggestions import generate_gemini_rules, generate_suggestions

_SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": SEVERITY_WEIGHT_CRITICAL,
    "high": SEVERITY_WEIGHT_HIGH,
    "medium": SEVERITY_WEIGHT_MEDIUM,
    "low": SEVERITY_WEIGHT_LOW,
}


@dataclass
class SessionAnalysis:
    session_id: str
    signals: list[SignalResult] = field(default_factory=list)
    overall_score: float = 0.0


@dataclass
class AnalysisReport:
    generated_at: datetime
    total_sessions: int
    sessions: list[SessionAnalysis]
    top_signals: list[SignalResult]
    suggestions: list[str]


def analyze_session(session: "SessionMetadata | SessionInfo") -> SessionAnalysis:
    signals: list[SignalResult] = []

    sentiment = analyze_session_sentiment(session.file_path, session.session_id)
    signals.extend(sentiment_to_signals(sentiment))
    signals.extend(detect_thrashing(session.file_path, session.session_id))
    signals.extend(detect_error_loops(session.file_path, session.session_id))
    signals.extend(detect_tool_inefficiency(session.file_path, session.session_id))
    signals.extend(detect_behavioral_signals(session.file_path, session.session_id))

    signals.sort(key=lambda s: s.score)

    overall_score = (
        sum(s.score * _SEVERITY_WEIGHTS.get(s.severity, 1) for s in signals)
        if signals else 0.0
    )

    return SessionAnalysis(
        session_id=session.session_id,
        signals=signals,
        overall_score=overall_score,
    )


def _collect_sessions_from_providers(
    provider_names: list[str] | None = None,
    project_filter: str | None = None,
) -> list[SessionInfo]:
    """Collect sessions from all enabled providers."""
    from .providers.gemini import GeminiProvider
    from .providers.claude import ClaudeProvider
    from .providers.cursor import CursorProvider
    from .providers.copilot import CopilotProvider

    provider_map = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "cursor": CursorProvider,
        "copilot": CopilotProvider,
    }

    config = load_config()
    enabled = provider_names or get_enabled_providers(config)
    sessions: list[SessionInfo] = []

    for name in enabled:
        cls = provider_map.get(name)
        if cls is None:
            continue
        provider = cls()
        if provider.is_available():
            sessions.extend(provider.discover_sessions(project_filter=project_filter))

    return sessions


def generate_report(
    on_progress=None,
    providers: list[str] | None = None,
    project_filter: str | None = None,
) -> AnalysisReport:
    raw_sessions = _collect_sessions_from_providers(providers, project_filter)
    session_analyses: list[SessionAnalysis] = []

    for i, sess_info in enumerate(raw_sessions):
        if on_progress:
            on_progress(i + 1, len(raw_sessions), sess_info.session_id)
        analysis = analyze_session(sess_info)
        session_analyses.append(analysis)

    session_analyses.sort(key=lambda a: a.overall_score)

    all_signals = [s for sa in session_analyses for s in sa.signals]
    top_signals = sorted(all_signals, key=lambda s: s.score)[:TOP_SIGNALS_LIMIT]
    suggestions = generate_suggestions(all_signals)

    return AnalysisReport(
        generated_at=datetime.now(),
        total_sessions=len(raw_sessions),
        sessions=session_analyses,
        top_signals=top_signals,
        suggestions=suggestions,
    )


def format_report_text(report: AnalysisReport) -> str:
    lines: list[str] = []

    lines.append("# Gemini Docter Report")
    lines.append("")
    lines.append(f"Generated: {report.generated_at.isoformat()}  ")
    lines.append(f"Sessions analyzed: {report.total_sessions}")
    lines.append("")
    lines.append("## Top Signals")
    lines.append("")

    if not report.top_signals:
        lines.append("No significant signals detected.")
    else:
        for signal in report.top_signals[:REPORT_SIGNAL_DISPLAY_LIMIT]:
            badge = {"critical": "CRIT", "high": "HIGH", "medium": "MED"}.get(signal.severity, "LOW")
            lines.append(f"- **[{badge}]** {signal.signal_name}: {signal.details}")
            for example in signal.examples[:3]:
                truncated = example[:EXAMPLE_TRUNCATE_LENGTH] + "..." if len(example) > EXAMPLE_TRUNCATE_LENGTH else example
                lines.append(f"  - `{truncated}`")

    lines.append("")
    lines.append("## Sessions (worst first)")
    lines.append("")

    for sa in report.sessions[:REPORT_PROJECT_LIMIT]:
        if not sa.signals:
            continue
        critical_count = sum(1 for s in sa.signals if s.severity == "critical")
        lines.append(f"### {sa.session_id[:16]}… (score: {sa.overall_score:.1f})")
        lines.append("")
        lines.append(f"{len(sa.signals)} signals ({critical_count} critical)")
        lines.append("")
        by_type: dict[str, list[SignalResult]] = {}
        for sig in sa.signals:
            by_type.setdefault(sig.signal_name, []).append(sig)
        for name, sigs in by_type.items():
            worst = min(s.score for s in sigs)
            lines.append(f"- **{name}** x{len(sigs)} (worst: {worst})")
        lines.append("")

    if report.suggestions:
        lines.append("## Suggested rules for GEMINI.md / AGENTS.md")
        lines.append("")
        for suggestion in report.suggestions:
            rule = suggestion.rule if hasattr(suggestion, "rule") else str(suggestion)
            lines.append(f"- {rule}")
        lines.append("")

    return "\n".join(lines)


def format_report_json(report: AnalysisReport) -> str:
    def _default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(
        {
            "generated_at": report.generated_at.isoformat(),
            "total_sessions": report.total_sessions,
            "top_signals": [asdict(s) for s in report.top_signals],
            "suggestions": report.suggestions,
            "sessions": [
                {
                    "session_id": sa.session_id,
                    "overall_score": sa.overall_score,
                    "signals": [asdict(s) for s in sa.signals],
                }
                for sa in report.sessions
            ],
        },
        indent=2,
        default=_default,
    )
