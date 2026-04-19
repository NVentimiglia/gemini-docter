#!/usr/bin/env python3
"""Install gemini-docter hooks into ~/.gemini/settings.json.

Creates backups before modifying. Safe to run multiple times (idempotent).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


GEMINI_SETTINGS = Path.home() / ".gemini" / "settings.json"
HOOKS_DIR = Path(__file__).parent / "hooks"

# Use absolute Windows paths for the hook commands
AFTER_AGENT_SCRIPT = str((HOOKS_DIR / "after_agent.py").resolve())
SESSION_END_SCRIPT = str((HOOKS_DIR / "session_end.py").resolve())


def _hook_command(script_path: str) -> str:
    """Build the command string to invoke a Python hook script."""
    if sys.platform == "win32":
        return f'py "{script_path}"'
    return f'python3 "{script_path}"'


def _make_hook_entry(script_path: str) -> dict:
    return {
        "hooks": [
            {
                "type": "command",
                "command": _hook_command(script_path),
            }
        ]
    }


def _hooks_already_installed(hooks_config: dict, script_path: str) -> bool:
    """Check if a hook for this script is already present anywhere in the config."""
    script_name = Path(script_path).name
    config_str = json.dumps(hooks_config)
    return script_name in config_str


def load_settings() -> dict:
    if GEMINI_SETTINGS.exists():
        with GEMINI_SETTINGS.open(encoding="utf-8") as fh:
            try:
                return json.load(fh)
            except json.JSONDecodeError:
                print(f"Warning: {GEMINI_SETTINGS} is not valid JSON — starting fresh.", file=sys.stderr)
    return {}


def save_settings(settings: dict, dry_run: bool = False) -> None:
    if dry_run:
        print(json.dumps(settings, indent=2))
        return
    GEMINI_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    backup = GEMINI_SETTINGS.with_suffix(".json.bak")
    if GEMINI_SETTINGS.exists():
        shutil.copy2(GEMINI_SETTINGS, backup)
        print(f"Backed up settings to {backup}")
    with GEMINI_SETTINGS.open("w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
        fh.write("\n")
    print(f"Settings saved to {GEMINI_SETTINGS}")


def install_hooks(dry_run: bool = False) -> int:
    settings = load_settings()
    hooks_config: dict = settings.get("hooks", {})
    installed: list[str] = []

    # AfterAgent hook
    after_agent_key = "AfterAgent"
    if _hooks_already_installed(hooks_config, AFTER_AGENT_SCRIPT):
        print(f"  {after_agent_key}: already installed")
    else:
        hooks_config.setdefault(after_agent_key, [])
        hooks_config[after_agent_key].append(_make_hook_entry(AFTER_AGENT_SCRIPT))
        installed.append(after_agent_key)

    # SessionEnd hook
    session_end_key = "SessionEnd"
    if _hooks_already_installed(hooks_config, SESSION_END_SCRIPT):
        print(f"  {session_end_key}: already installed")
    else:
        hooks_config.setdefault(session_end_key, [])
        hooks_config[session_end_key].append(_make_hook_entry(SESSION_END_SCRIPT))
        installed.append(session_end_key)

    if not installed:
        print("All hooks already installed — nothing to do.")
        return 0

    settings["hooks"] = hooks_config

    # Also enable hooks system if it's not already on
    tools_settings = settings.get("tools", {})
    if not tools_settings.get("enableHooks"):
        tools_settings["enableHooks"] = True
        settings["tools"] = tools_settings
        print("  Enabled tools.enableHooks")

    save_settings(settings, dry_run=dry_run)

    if dry_run:
        print()
        print(f"Would install: {', '.join(installed)}")
    else:
        print()
        print(f"Installed: {', '.join(installed)}")
        print()
        print("Next steps:")
        print("  1. Restart Gemini CLI")
        print("  2. Run a Gemini session")
        print(f"  3. Check {Path.home() / '.gemini-docter' / 'transcripts'} for captured data")
        print("  4. Run: py run.py")

    return 0


def uninstall_hooks() -> int:
    settings = load_settings()
    hooks_config = settings.get("hooks", {})

    script_names = {Path(AFTER_AGENT_SCRIPT).name, Path(SESSION_END_SCRIPT).name}
    removed = 0

    for event_name in list(hooks_config.keys()):
        original_len = len(hooks_config[event_name])
        hooks_config[event_name] = [
            entry for entry in hooks_config[event_name]
            if not any(
                sn in json.dumps(entry)
                for sn in script_names
            )
        ]
        removed += original_len - len(hooks_config[event_name])
        if not hooks_config[event_name]:
            del hooks_config[event_name]

    if removed == 0:
        print("No gemini-docter hooks found to remove.")
        return 0

    settings["hooks"] = hooks_config
    save_settings(settings)
    print(f"Removed {removed} hook entry(ies).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="install_hooks",
        description="Install gemini-docter hooks into ~/.gemini/settings.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove gemini-docter hooks from settings.json",
    )
    args = parser.parse_args(argv)

    if args.uninstall:
        return uninstall_hooks()

    return install_hooks(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
