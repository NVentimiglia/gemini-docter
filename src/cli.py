"""CLI entrypoint for gemini-docter."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path


def _spinner_progress(current: int, total: int, session_id: str) -> None:
    short_id = session_id[:16]
    sys.stderr.write(f"\r  Analyzing {short_id}... ({current}/{total})\x1b[K")
    sys.stderr.flush()


def _spinner_stop() -> None:
    sys.stderr.write("\r\x1b[K")
    sys.stderr.flush()


def _auto_project_filter() -> str | None:
    """Derive a project filter from the current working directory."""
    cwd = Path.cwd()
    return cwd.name  # e.g. "my-windows-app"


def _save_rules_to_gemini_md(rules_text: str, target: Path) -> None:
    """Append or replace the auto-generated block in a GEMINI.md file."""
    MARKER_START = "<!-- gemini-docter:start -->"
    MARKER_END = "<!-- gemini-docter:end -->"
    new_block = f"{MARKER_START}\n{rules_text}\n{MARKER_END}\n"

    if target.exists():
        content = target.read_text(encoding="utf-8")
        if MARKER_START in content:
            # Replace existing block
            before = content[:content.index(MARKER_START)]
            after_marker = content.index(MARKER_END) + len(MARKER_END)
            after = content[after_marker:]
            target.write_text(before + new_block + after, encoding="utf-8")
            return
        # Append to existing file
        target.write_text(content.rstrip() + "\n\n" + new_block, encoding="utf-8")
    else:
        target.write_text(new_block, encoding="utf-8")


def _cmd_analyze(args: argparse.Namespace) -> int:
    from .analyzer import format_report_json, format_report_text, generate_report
    from .suggestions import generate_gemini_rules

    providers = [p.strip() for p in args.providers.split(",")] if args.providers else None

    # Auto-derive project filter from cwd when --save is used without -p
    project_filter = args.project
    if args.save and not project_filter:
        project_filter = _auto_project_filter()
        print(f"Filtering to project: {project_filter}", file=sys.stderr)

    if args.session:
        report = generate_report(providers=providers, project_filter=project_filter)
        prefix = args.session.replace(".jsonl", "")
        match = next(
            (sa for sa in report.sessions if sa.session_id.startswith(prefix)),
            None,
        )
        if not match:
            print(f"Session '{args.session}' not found.", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(asdict(match), indent=2))
        else:
            badge_map = {"critical": "CRIT", "high": "HIGH", "medium": "MED", "low": "LOW"}
            print(f"Session: {match.session_id}")
            print(f"Score:   {match.overall_score:.1f}")
            print()
            if match.signals:
                for sig in match.signals:
                    badge = badge_map.get(sig.severity, "LOW")
                    print(f"  [{badge}] {sig.signal_name}: {sig.details}")
            else:
                print("  No signals detected - session looks healthy.")
        return 0

    sys.stderr.write("Scanning transcripts...\n")
    report = generate_report(
        on_progress=_spinner_progress,
        providers=providers,
        project_filter=project_filter,
    )
    _spinner_stop()

    if not report.total_sessions:
        print("No transcript files found.")
        if not project_filter:
            print("Install hooks with: py run.py --install")
        else:
            print(f"No sessions found for project '{project_filter}'.")
            print("Check the project name matches part of the working directory path.")
        return 0

    if args.rules or args.save:
        rules_text = generate_gemini_rules(
            [s for sa in report.sessions for s in sa.signals],
            report.total_sessions,
        )
        if not rules_text:
            print("No rules to generate - sessions look healthy.")
            return 0

        if args.save:
            target = Path(args.save) if isinstance(args.save, str) and args.save != True else Path.cwd() / "GEMINI.md"
            _save_rules_to_gemini_md(rules_text, target)
            print(f"Rules written to {target}")
            print()
            # Also print the rules
            print(rules_text)
        else:
            print(rules_text)
        return 0

    if args.json:
        print(format_report_json(report))
        return 0

    print(format_report_text(report))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    """Show hook health and available providers."""
    from .providers.gemini import GeminiProvider
    from .providers.claude import ClaudeProvider
    from .providers.cursor import CursorProvider
    from .providers.copilot import CopilotProvider

    transcripts_dir = Path.home() / ".gemini-docter" / "transcripts"
    debug_dir = Path.home() / ".gemini-docter" / "debug"
    gemini_settings = Path.home() / ".gemini" / "settings.json"

    print("gemini-docter status")
    print()

    # Hook installation
    print("Hooks:")
    if gemini_settings.exists():
        try:
            import json as _json
            settings = _json.loads(gemini_settings.read_text(encoding="utf-8"))
            hooks = settings.get("hooks", {})
            after_agent = "AfterAgent" in hooks
            session_end = "SessionEnd" in hooks
            print(f"  AfterAgent:  {'[ok]' if after_agent else '[--]'}")
            print(f"  SessionEnd:  {'[ok]' if session_end else '[--]'}")
            if not (after_agent and session_end):
                print("  -> Run: py run.py --install")
        except Exception:
            print("  Could not read ~/.gemini/settings.json")
    else:
        print("  ~/.gemini/settings.json not found")
        print("  -> Run: py run.py --install")

    print()

    # Transcript data
    print("Transcripts:")
    if transcripts_dir.exists():
        jsonl_files = list(transcripts_dir.glob("*.jsonl"))
        print(f"  {len(jsonl_files)} session(s) in {transcripts_dir}")
        if debug_dir.exists():
            debug_files = list(debug_dir.glob("*_raw.jsonl"))
            print(f"  {len(debug_files)} debug file(s) in {debug_dir}")
    else:
        print("  No transcripts yet - run a Gemini session after installing hooks")

    print()

    # Providers
    print("Providers:")
    for cls, label in [
        (GeminiProvider, "gemini (hook transcripts)"),
        (ClaudeProvider, "claude (~/.claude/projects)"),
        (CursorProvider, "cursor (SQLite)"),
        (CopilotProvider, "copilot (JSON sessions)"),
    ]:
        available = cls().is_available()
        print(f"  {label}: {'[ok]' if available else '[--]'}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gemini-docter",
        description=(
            "Diagnose your AI coding sessions. "
            "Analyzes transcripts for behavioral anti-patterns "
            "and generates rules for GEMINI.md / AGENTS.md."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    # Default analyze command (no subcommand)
    parser.add_argument("session", nargs="?", help="Session ID or .jsonl path to check")
    parser.add_argument("-p", "--project", help="Filter to sessions from this project (matched against working dir)")
    parser.add_argument("--providers", help="Comma-separated providers: gemini,claude,cursor,copilot")
    parser.add_argument("--rules", action="store_true", help="Print rules for GEMINI.md / AGENTS.md")
    parser.add_argument(
        "--save",
        nargs="?",
        const=True,
        metavar="FILE",
        help="Save rules into GEMINI.md in cwd (or FILE). Auto-filters to current project.",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Status subcommand
    sub.add_parser("status", help="Show hook health and provider availability")

    args = parser.parse_args(argv)

    if args.command == "status":
        return _cmd_status(args)

    return _cmd_analyze(args)


if __name__ == "__main__":
    raise SystemExit(main())
